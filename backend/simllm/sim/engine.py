from __future__ import annotations

import asyncio
import logging
import random
import sqlite3
import time
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Awaitable, Callable

from simllm.agents.actions import AgentContext, apply_action
from simllm.agents.conversation import (
    RELATIONSHIP_UPDATE_TOOL,
    assemble_relationship_prompt,
    assemble_reply_prompt,
)
from simllm.agents.emoji import TOOL_SPEC as EMOJI_TOOL
from simllm.agents.emoji import assemble_emoji_prompt
from simllm.agents.llm_client import decide_action, generate_text, summarize
from simllm.agents.memory import assemble_summary_prompt, should_summarize
from simllm.agents.personality import TOOL_SPEC as PERSONALITY_TOOL
from simllm.agents.personality import assemble_personality_prompt, fallback_identity, random_seed_hint
from simllm.agents.prompt import assemble_prompt
from simllm.db import agents_repo, economy_repo, memory_repo, relationships_repo, save_repo, world_repo
from simllm.logging_setup import record_log_event
from simllm.models.settings import Settings
from simllm.sim.construction import advance_construction
from simllm.sim.death import check_age_death, check_starvation_death, update_zero_health_streak
from simllm.sim.health import apply_health_delta, compute_health_delta
from simllm.sim.mood import compute_mood, compute_mood_band
from simllm.sim.needs import decay_needs
from simllm.sim.pathfinding import find_path
from simllm.sim.perception import get_local_perception
from simllm.sim.scheduling import is_agent_due

SIM_DATETIME_FMT = "%Y-%m-%dT%H:%M:%S"

BroadcastFn = Callable[..., Awaitable[None]]


class SimulationEngine:
    """Orchestrates one tick end-to-end.

    A synchronous no-LLM batch pass (needs decay, passive shelter regen, one
    step of any in-progress movement) runs over every alive agent first;
    agents that come out of that pass "due" for a real decision have their
    initial LLM decision fetched concurrently through a bounded worker pool
    (up to `worker_concurrency` at once). Those decisions are then applied
    sequentially: this is what lets `speak` safely pull a *second* due agent
    into a conversation without risking it being double-processed by its
    own concurrent worker (see _run_decisions/_resolve_conversation) -- a
    speak target must be alive, in range, AND still due-and-unresolved at
    the moment it's reached in that sequential pass, otherwise the
    initiator's speak simply fails (the target was "busy"). Every resolved
    decision is written to that agent's memory; separately, agents whose
    summarization interval has elapsed get their memories-since-last-summary
    compressed into an updated `life_summary` through the same bounded
    pool. Construction/economy/death checks join the batch pass in their
    own milestones without changing this class's external contract
    (`run_tick() -> dict`).
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        settings: Settings,
        broadcast_fn: BroadcastFn | None = None,
        logger: logging.Logger | None = None,
    ):
        self.conn = conn
        self.settings = settings
        self.broadcast_fn = broadcast_fn
        self.logger = logger

    async def run_tick(self) -> dict:
        row = self.conn.execute(
            "SELECT current_tick, sim_datetime FROM sim_clock WHERE id = 1"
        ).fetchone()
        next_tick = row["current_tick"] + 1
        sim_dt = datetime.strptime(row["sim_datetime"], SIM_DATETIME_FMT)
        sim_dt += timedelta(minutes=self.settings.sim_minutes_per_tick)
        sim_dt_str = sim_dt.strftime(SIM_DATETIME_FMT)

        tick_started = time.monotonic()
        await self._process_agents(next_tick, sim_dt_str)
        tick_duration_ms = round((time.monotonic() - tick_started) * 1000, 1)

        self.conn.execute(
            "UPDATE sim_clock SET current_tick = ?, sim_datetime = ? WHERE id = 1",
            (next_tick, sim_dt_str),
        )
        self.conn.commit()

        if self.settings.autosave_interval_ticks > 0 and next_tick % self.settings.autosave_interval_ticks == 0:
            await self._autosave(next_tick, sim_dt_str)

        population_row = self.conn.execute(
            "SELECT COUNT(*) AS c FROM agents WHERE is_alive = 1"
        ).fetchone()

        # Surfaced in the tick_complete broadcast and system log so a long
        # local run's per-tick cost against the real Ollama model is
        # observable without instrumenting anything client-side -- this is
        # what worker_concurrency/tick_interval_seconds/llm_timeout_seconds
        # get tuned against (see Milestone 18).
        await record_log_event(
            self.conn, self.logger, self.broadcast_fn,
            category="system", level="info",
            message=f"Tick {next_tick} took {tick_duration_ms:.0f}ms.",
            tick=next_tick, sim_time=sim_dt_str, tick_duration_ms=tick_duration_ms,
        )

        return {
            "tick": next_tick,
            "sim_time": sim_dt_str,
            "population": population_row["c"],
            "tick_duration_ms": tick_duration_ms,
        }

    async def _autosave(self, tick: int, sim_time: str) -> None:
        save_repo.touch_last_saved(self.conn)
        self.conn.commit()
        save_repo.checkpoint(self.conn)
        await record_log_event(
            self.conn, self.logger, self.broadcast_fn,
            category="system", level="info", message=f"Autosaved at tick {tick}.",
            tick=tick, sim_time=sim_time,
        )
        self.conn.commit()

    async def _process_agents(self, tick: int, sim_time: str) -> None:
        await self._advance_construction(tick, sim_time)

        # Scratch state for this tick only, consumed by _run_emoji_repicks at
        # the end -- safe as an instance attribute since ticks are processed
        # one at a time, never concurrently, by a given engine instance.
        self._emoji_repick_candidates: list[dict] = []

        decay_rates = self.settings.needs_decay_per_tick.model_dump()
        blocked_tiles = world_repo.get_blocked_tiles(self.conn)

        due_states: list[dict] = []

        for state in agents_repo.list_agent_tick_states(self.conn):
            needs = decay_needs(state["needs"], decay_rates)
            if state["home_pos"] is not None and (state["x"], state["y"]) == state["home_pos"]:
                needs["shelter"] = min(
                    100.0, needs["shelter"] + self.settings.shelter_home_regen_per_tick
                )

            x, y = state["x"], state["y"]
            current_action = state["current_action"]
            moved = False

            if current_action and current_action.get("type") == "move_to":
                path = [tuple(p) for p in current_action.get("path") or []]
                if path:
                    x, y = path.pop(0)
                    moved = True
                current_action = (
                    {"type": "move_to", "path": [list(p) for p in path], "target": current_action["target"]}
                    if path
                    else None
                )

            state = {**state, "needs": needs, "x": x, "y": y, "current_action": current_action, "moved": moved}

            due = is_agent_due(
                state["next_decision_tick"],
                tick,
                needs,
                self.settings.needs_critical_threshold,
            )

            if due:
                due_states.append(state)
                continue

            health_delta = compute_health_delta(
                needs,
                self.settings.needs_critical_threshold,
                self.settings.health_regen_per_tick,
                self.settings.health_decay_per_critical_need,
            )
            health = apply_health_delta(state["health"], health_delta)

            died, zero_health_ticks, cause = self._check_death(
                state["zero_health_ticks"], health, state["age_ticks"] + 1, state["lifespan_ticks"]
            )
            mood, mood_band = self._update_mood(state, needs, health)

            agents_repo.apply_tick_update(
                self.conn,
                state["id"],
                x=x,
                y=y,
                needs=needs,
                health=health,
                currency=state["currency"],
                current_action=current_action,
                current_goal=state["current_goal"],
                next_decision_tick=state["next_decision_tick"],
                zero_health_ticks=zero_health_ticks,
                mood=mood,
                mood_band=mood_band,
                tick=tick,
            )

            if died:
                await self._handle_death(state, cause, tick, sim_time)
                continue

            if self.broadcast_fn is not None:
                if moved:
                    await self.broadcast_fn(
                        "agent_moved", {"agent_id": state["id"], "x": x, "y": y}, tick=tick, sim_time=sim_time
                    )
                    await self.broadcast_fn(
                        "agent_stat_update",
                        {
                            "agent_id": state["id"],
                            "needs": needs,
                            "health": health,
                            "currency": state["currency"],
                            "current_goal": state["current_goal"],
                            "mood": mood,
                        },
                        tick=tick,
                        sim_time=sim_time,
                    )

        await self._run_decisions(due_states, blocked_tiles, tick, sim_time)
        await self._run_summarizations(tick, sim_time)
        await self._run_emoji_repicks(tick, sim_time)
        await self._maybe_spawn_newcomer(tick, sim_time)
        self.conn.commit()

    # ---- Death ----

    def _check_death(
        self, zero_health_ticks_prev: int, health: float, age_ticks_next: int, lifespan_ticks: int
    ) -> tuple[bool, int, str | None]:
        zero_health_ticks = update_zero_health_streak(health, zero_health_ticks_prev)
        if check_age_death(age_ticks_next, lifespan_ticks):
            return True, zero_health_ticks, "age"
        if check_starvation_death(zero_health_ticks, self.settings.starvation_death_ticks):
            return True, zero_health_ticks, "starvation"
        return False, zero_health_ticks, None

    async def _handle_death(self, state: dict, cause: str, tick: int, sim_time: str) -> None:
        agents_repo.mark_agent_dead(self.conn, state["id"], tick, cause)
        if state.get("home_building_id") is not None:
            world_repo.release_building_owner(self.conn, state["home_building_id"])
        economy_repo.release_job_assignment(self.conn, state["id"])

        message = f"{state.get('name', 'An agent')} died of {cause}."
        if self.broadcast_fn is not None:
            await self.broadcast_fn(
                "agent_death", {"agent_id": state["id"], "cause": cause}, tick=tick, sim_time=sim_time
            )
        await record_log_event(
            self.conn, self.logger, self.broadcast_fn,
            category="death", level="warning", message=message, tick=tick, sim_time=sim_time,
            agent_id=state["id"], cause=cause,
        )

    # ---- Mood / emoji ----

    def _update_mood(self, state: dict, needs: dict, health: float) -> tuple[float, int]:
        """Recomputes mood every tick (cheap); queues an emoji re-pick only
        when the mood BAND actually changes."""
        mood = compute_mood(needs, health)
        mood_band = compute_mood_band(mood, self.settings.mood_band_width)
        if mood_band != state.get("mood_band"):
            self._emoji_repick_candidates.append({"id": state["id"], "name": state.get("name"), "mood": mood})
        return mood, mood_band

    async def _run_emoji_repicks(self, tick: int, sim_time: str) -> None:
        candidates = self._emoji_repick_candidates
        if not candidates:
            return

        semaphore = asyncio.Semaphore(max(1, self.settings.worker_concurrency))

        async def worker(candidate: dict) -> None:
            async with semaphore:
                await self._repick_emoji_one(candidate, tick, sim_time)

        await asyncio.gather(*(worker(candidate) for candidate in candidates))

    async def _repick_emoji_one(self, candidate: dict, tick: int, sim_time: str) -> None:
        messages = assemble_emoji_prompt(candidate["name"], candidate["mood"])
        decision = await decide_action(messages, self.settings, tools=EMOJI_TOOL)

        fields = {
            "agent_id": candidate["id"],
            "mood": round(candidate["mood"], 1),
            "used_llm_fallback": decision.used_fallback,
            "llm_attempts": decision.attempts,
            "llm_latency_ms": round(decision.latency_ms, 1),
            "llm_error": decision.error,
        }

        if decision.used_fallback or decision.action != "pick_emoji":
            message = f"{candidate['name']}'s emoji re-pick failed; keeping their current emoji."
            await record_log_event(
                self.conn, self.logger, self.broadcast_fn,
                category="emoji", level="warning", message=message, tick=tick, sim_time=sim_time, **fields,
            )
            return

        emoji = decision.params.get("emoji")
        emoji = emoji.strip() if isinstance(emoji, str) else ""
        # A real emoji is never pure ASCII (text emoticons like ":)" always
        # are) and is at most a few codepoints even with skin-tone/ZWJ
        # modifiers -- reject anything else as a malformed reply rather than
        # storing garbage that won't render as a glyph.
        if not emoji or emoji.isascii() or len(emoji) > 8:
            message = (
                f"{candidate['name']}'s emoji re-pick returned something that wasn't a real "
                f"emoji ({emoji!r}); keeping their current emoji."
            )
            await record_log_event(
                self.conn, self.logger, self.broadcast_fn,
                category="emoji", level="warning", message=message, tick=tick, sim_time=sim_time, **fields,
            )
            return

        agents_repo.update_emoji(self.conn, candidate["id"], emoji)

        if self.broadcast_fn is not None:
            await self.broadcast_fn(
                "agent_stat_update",
                {"agent_id": candidate["id"], "emoji": emoji},
                tick=tick,
                sim_time=sim_time,
            )

        message = f"{candidate['name']}'s mood shifted -- now feeling {emoji}."
        await record_log_event(
            self.conn, self.logger, self.broadcast_fn,
            category="emoji", level="info", message=message, tick=tick, sim_time=sim_time,
            emoji=emoji, **fields,
        )

    # ---- Respawn ----

    async def _maybe_spawn_newcomer(self, tick: int, sim_time: str) -> None:
        population = self.conn.execute("SELECT COUNT(*) AS c FROM agents WHERE is_alive = 1").fetchone()["c"]
        if population >= self.settings.population_target:
            return

        decision = await decide_action(
            assemble_personality_prompt(random_seed_hint()), self.settings, tools=PERSONALITY_TOOL
        )
        if not decision.used_fallback and decision.action == "create_personality":
            name = decision.params.get("name") or "Newcomer"
            backstory = decision.params.get("backstory")
            traits = decision.params.get("traits")
            traits = traits if isinstance(traits, list) else []
            emoji = decision.params.get("emoji") or "🙂"
        else:
            name, emoji = fallback_identity(tick)
            backstory = None
            traits = []

        vacant_house = world_repo.find_vacant_house(self.conn)
        if vacant_house:
            x, y, home_building_id = vacant_house["x"], vacant_house["y"], vacant_house["id"]
        else:
            x, y, home_building_id = self.settings.world_width // 2, self.settings.world_height // 2, None

        clock_row = self.conn.execute("SELECT generation FROM sim_clock WHERE id = 1").fetchone()
        new_generation = clock_row["generation"] + 1
        self.conn.execute("UPDATE sim_clock SET generation = ? WHERE id = 1", (new_generation,))

        agent_id = agents_repo.create_agent(
            self.conn,
            name=name,
            emoji=emoji,
            traits=traits,
            backstory=backstory,
            x=x,
            y=y,
            home_building_id=home_building_id,
            lifespan_ticks=random.randint(self.settings.lifespan_ticks_min, self.settings.lifespan_ticks_max),
            currency=self.settings.starting_currency,
            generation=new_generation,
            created_at_tick=tick,
        )
        if home_building_id is not None:
            world_repo.set_building_owner(self.conn, home_building_id, agent_id)

        if self.broadcast_fn is not None:
            await self.broadcast_fn(
                "agent_created",
                {"id": agent_id, "name": name, "emoji": emoji, "x": x, "y": y, "is_alive": 1},
                tick=tick,
                sim_time=sim_time,
            )

        message = f"{name} {emoji} arrived in the city."
        await record_log_event(
            self.conn, self.logger, self.broadcast_fn,
            category="newcomer", level="info", message=message, tick=tick, sim_time=sim_time,
            agent_id=agent_id,
        )

    # ---- Construction ----

    async def _advance_construction(self, tick: int, sim_time: str) -> None:
        for building in world_repo.list_under_construction_buildings(self.conn):
            new_progress, completed = advance_construction(
                building["construction_progress"], building["construction_total_ticks"]
            )
            world_repo.update_construction_progress(self.conn, building["id"], new_progress)

            status = "under_construction"
            if completed:
                world_repo.complete_building(self.conn, building["id"], building["x"], building["y"], building["type"])
                status = "complete"

                if building["type"] == "workplace":
                    economy_repo.create_job(
                        self.conn, building["id"], "Worker",
                        self.settings.default_job_wage, self.settings.job_slots_per_workplace,
                    )
                if building["type"] == "house" and building["owner_agent_id"] is not None:
                    agents_repo.set_home_building(self.conn, building["owner_agent_id"], building["id"])

            if self.broadcast_fn is not None:
                await self.broadcast_fn(
                    "building_update",
                    {
                        "building_id": building["id"],
                        "type": building["type"],
                        "x": building["x"],
                        "y": building["y"],
                        "status": status,
                        "construction_progress": new_progress,
                        "construction_total_ticks": building["construction_total_ticks"],
                    },
                    tick=tick,
                    sim_time=sim_time,
                )
                if completed:
                    await self.broadcast_fn(
                        "tile_update",
                        {"x": building["x"], "y": building["y"], "tile_type": building["type"], "building_id": building["id"]},
                        tick=tick,
                        sim_time=sim_time,
                    )

    # ---- Decisions (two-phase: concurrent gather, then sequential apply) ----

    async def _run_decisions(
        self, due_states: list[dict], blocked_tiles: set[tuple[int, int]], tick: int, sim_time: str
    ) -> None:
        if not due_states:
            return

        # Fetched once per tick and shared across every due agent's
        # perception filtering below: none of this changes again until the
        # next tick's batch pass, so there's no reason to re-query per agent.
        all_tiles = world_repo.list_non_empty_tiles(self.conn)
        all_buildings = world_repo.list_buildings(self.conn)
        all_agent_snapshots = agents_repo.list_all_agent_snapshots(self.conn)
        all_jobs = economy_repo.list_jobs_with_openings(self.conn)
        due_by_id_for_snapshot = {state["id"]: state for state in due_states}
        for snap in all_agent_snapshots:
            # A due agent's DB row may still hold its PRE-batch-pass position
            # (it hasn't been persisted yet); its due_states entry already
            # has the post-movement-step position for this tick.
            due_state = due_by_id_for_snapshot.get(snap["id"])
            if due_state is not None:
                snap["x"], snap["y"] = due_state["x"], due_state["y"]

        semaphore = asyncio.Semaphore(max(1, self.settings.worker_concurrency))

        async def get_decision(state: dict) -> tuple[dict, dict, object]:
            async with semaphore:
                agent_detail = agents_repo.get_agent_detail(self.conn, state["id"])
                agent_detail["needs"] = state["needs"]
                agent_detail["x"], agent_detail["y"] = state["x"], state["y"]
                agent_detail["current_job"] = economy_repo.get_active_assignment(self.conn, state["id"])
                memories = memory_repo.get_recent_memories(self.conn, state["id"], self.settings.memory_buffer_size)
                perception = get_local_perception(
                    all_tiles, all_buildings, all_agent_snapshots, all_jobs, state["id"],
                    state["x"], state["y"], self.settings.perception_radius,
                )
                messages = assemble_prompt(agent_detail, self.settings, memories, perception)
                decision = await decide_action(messages, self.settings)
                return state, agent_detail, decision

        results = await asyncio.gather(*(get_decision(state) for state in due_states))

        due_by_id = {state["id"]: state for state in due_states}
        resolved_ids: set[int] = set()

        for state, agent_detail, decision in results:
            if state["id"] in resolved_ids:
                continue  # already consumed as a conversation partner below

            if decision.action == "speak":
                target_id = decision.params.get("target_agent_id")
                target_state = due_by_id.get(target_id)
                in_range = (
                    target_state is not None
                    and target_id != state["id"]
                    and target_id not in resolved_ids
                    and max(abs(target_state["x"] - state["x"]), abs(target_state["y"] - state["y"]))
                    <= self.settings.conversation_range
                )
                if in_range:
                    target_detail = agents_repo.get_agent_detail(self.conn, target_id)
                    await self._resolve_conversation(
                        state, agent_detail, decision, target_state, target_detail, tick, sim_time
                    )
                    resolved_ids.add(state["id"])
                    resolved_ids.add(target_id)
                    continue
                # Target unavailable (not due this tick, already resolved, or
                # out of range) -- falls through to _apply_decision, which
                # treats any unresolved "speak" pending_action as a rejection.

            await self._apply_decision(state, agent_detail, decision, blocked_tiles, tick, sim_time)
            resolved_ids.add(state["id"])

    async def _apply_decision(
        self,
        state: dict,
        agent_detail: dict,
        decision,
        blocked_tiles: set[tuple[int, int]],
        tick: int,
        sim_time: str,
    ) -> None:
        ctx = AgentContext(
            x=state["x"],
            y=state["y"],
            needs=state["needs"],
            currency=state["currency"],
            home_pos=state["home_pos"],
            world_width=self.settings.world_width,
            world_height=self.settings.world_height,
        )
        outcome = apply_action(decision.action, decision.params, ctx, self.settings)
        rejected = not outcome.accepted
        rejection_reason = outcome.reason if rejected else None
        current_action: dict | None = None

        if not rejected and outcome.pending_action:
            pending_type = outcome.pending_action.get("type")
            if pending_type == "move_to":
                target = tuple(outcome.pending_action["target"])
                path = find_path(
                    (state["x"], state["y"]), target, self.settings.world_width, self.settings.world_height,
                    blocked_tiles,
                )
                if path is None:
                    rejected = True
                    rejection_reason = "unreachable"
                elif path:
                    current_action = {"type": "move_to", "path": [list(p) for p in path], "target": list(target)}
                # path == [] means already there; falls through, goal_text kept.
            elif pending_type == "speak":
                # Only reached when _run_decisions couldn't pair this speak
                # with an available target -- always a rejection here.
                rejected = True
                rejection_reason = "target_unavailable"
            elif pending_type == "take_job":
                job_id = outcome.pending_action["job_id"]
                job = economy_repo.get_job(self.conn, job_id)
                at_workplace = job is not None and max(
                    abs(job["x"] - state["x"]), abs(job["y"] - state["y"])
                ) <= self.settings.workplace_interaction_range
                if job is None or not at_workplace:
                    rejected = True
                    rejection_reason = "not_at_workplace"
                elif economy_repo.get_active_assignment(self.conn, state["id"]) is not None:
                    rejected = True
                    rejection_reason = "already_employed"
                elif job["filled"] >= job["slots"]:
                    rejected = True
                    rejection_reason = "job_full"
                else:
                    economy_repo.assign_job(self.conn, job_id, state["id"], tick)
            elif pending_type == "work_job":
                assignment = economy_repo.get_active_assignment(self.conn, state["id"])
                if assignment is None:
                    rejected = True
                    rejection_reason = "no_job"
                elif max(
                    abs(assignment["x"] - state["x"]), abs(assignment["y"] - state["y"])
                ) > self.settings.workplace_interaction_range:
                    rejected = True
                    rejection_reason = "not_at_workplace"
                else:
                    wage = assignment["wage_per_shift"]
                    new_currency = outcome.currency + wage
                    new_needs = dict(outcome.needs)
                    new_needs["purpose"] = min(
                        100.0, new_needs["purpose"] + self.settings.needs_restore_amount.purpose
                    )
                    new_needs["energy"] = max(0.0, new_needs["energy"] - self.settings.work_energy_cost)
                    outcome = replace(outcome, needs=new_needs, currency=new_currency)
                    economy_repo.record_transaction(self.conn, state["id"], tick, wage, "wage", new_currency)
            elif pending_type == "start_build":
                building_type = outcome.pending_action["building_type"]
                target_x, target_y = outcome.pending_action["target"]
                adjacent = max(abs(target_x - state["x"]), abs(target_y - state["y"])) <= 1
                tile_type = world_repo.get_tile_type(self.conn, target_x, target_y)
                cost = getattr(self.settings.building_costs, building_type)
                if not adjacent or tile_type != "empty":
                    rejected = True
                    rejection_reason = "invalid_build_site"
                elif outcome.currency < cost:
                    rejected = True
                    rejection_reason = "insufficient_funds"
                else:
                    construction_ticks = getattr(self.settings.building_construction_ticks, building_type)
                    new_currency = outcome.currency - cost
                    owner_agent_id = state["id"] if building_type == "house" else None
                    building_id = world_repo.create_building_under_construction(
                        self.conn, building_type, target_x, target_y, state["id"], owner_agent_id,
                        construction_ticks, tick,
                    )
                    economy_repo.record_transaction(self.conn, state["id"], tick, -cost, "building_cost", new_currency)
                    outcome = replace(outcome, currency=new_currency)

                    if self.broadcast_fn is not None:
                        await self.broadcast_fn(
                            "building_update",
                            {
                                "building_id": building_id, "type": building_type, "x": target_x, "y": target_y,
                                "status": "under_construction", "construction_progress": 0,
                                "construction_total_ticks": construction_ticks,
                            },
                            tick=tick, sim_time=sim_time,
                        )
                        await self.broadcast_fn(
                            "tile_update",
                            {"x": target_x, "y": target_y, "tile_type": "under_construction", "building_id": building_id},
                            tick=tick, sim_time=sim_time,
                        )

        if rejected:
            outcome = apply_action("idle", {"reason": outcome.goal_text}, ctx, self.settings)
            current_action = None

        health_delta = compute_health_delta(
            outcome.needs,
            self.settings.needs_critical_threshold,
            self.settings.health_regen_per_tick,
            self.settings.health_decay_per_critical_need,
        )
        health = apply_health_delta(state["health"], health_delta)

        died, zero_health_ticks, cause = self._check_death(
            state["zero_health_ticks"], health, state["age_ticks"] + 1, state["lifespan_ticks"]
        )
        mood, mood_band = self._update_mood(state, outcome.needs, health)

        next_decision_tick = (
            tick + len(current_action["path"])
            if current_action is not None
            else tick + self.settings.decision_cooldown_ticks
        )

        # Persist the final effect of this action first (e.g. a wage payment
        # or spent currency) so it's never lost even if the agent dies this
        # same tick -- death is layered on top, not instead of, their last
        # living state.
        agents_repo.apply_tick_update(
            self.conn,
            state["id"],
            x=outcome.x,
            y=outcome.y,
            needs=outcome.needs,
            health=health,
            currency=outcome.currency,
            current_action=current_action,
            current_goal=outcome.goal_text,
            next_decision_tick=next_decision_tick,
            zero_health_ticks=zero_health_ticks,
            mood=mood,
            mood_band=mood_band,
            tick=tick,
        )

        if died:
            await self._handle_death(state, cause, tick, sim_time)
            return

        resolved_action = decision.action if not rejected else "idle"

        memory_repo.add_memory(
            self.conn,
            agent_id=state["id"],
            tick=tick,
            sim_datetime=sim_time,
            type="action",
            content=outcome.goal_text,
        )

        await self._log_decision(agent_detail, decision, outcome, rejected, rejection_reason, tick, sim_time)

        if self.broadcast_fn is not None:
            if state.get("moved"):
                # This agent took its final step (arriving) in this same
                # tick's batch pass, right before becoming due again -- that
                # step is otherwise never broadcast (non-due agents get
                # agent_moved from the batch pass directly; this is the one
                # case where a moved agent ends up here instead).
                await self.broadcast_fn(
                    "agent_moved",
                    {"agent_id": state["id"], "x": state["x"], "y": state["y"]},
                    tick=tick,
                    sim_time=sim_time,
                )
            await self.broadcast_fn(
                "agent_stat_update",
                {
                    "agent_id": state["id"],
                    "needs": outcome.needs,
                    "health": health,
                    "currency": outcome.currency,
                    "current_goal": outcome.goal_text,
                    "action": resolved_action,
                    "mood": mood,
                },
                tick=tick,
                sim_time=sim_time,
            )

    # ---- Conversations ----

    async def _resolve_conversation(
        self,
        state_a: dict,
        detail_a: dict,
        decision_a,
        state_b: dict,
        detail_b: dict,
        tick: int,
        sim_time: str,
    ) -> None:
        opening = (decision_a.params.get("message") or "").strip() or "..."
        transcript = [f"{detail_a['name']}: {opening}"]

        # index 0 replies first (B), then A, alternating, until the turn cap.
        participants = [(state_b, detail_b), (state_a, detail_a)]
        for turn in range(1, self.settings.conversation_max_turns):
            speaker_state, speaker_detail = participants[(turn - 1) % 2]
            listener_detail = detail_a if speaker_state["id"] == state_b["id"] else detail_b
            messages = assemble_reply_prompt(speaker_detail, listener_detail["name"], transcript)
            result = await generate_text(
                messages, self.settings, max_chars=self.settings.conversation_reply_max_chars
            )
            line = result.text if result.text else "..."
            transcript.append(f"{speaker_detail['name']}: {line}")

        await self._update_relationship(state_a, detail_a, state_b, detail_b, transcript, tick, sim_time)

        transcript_text = "\n".join(transcript)
        for state, detail, other_detail in ((state_a, detail_a, detail_b), (state_b, detail_b, detail_a)):
            needs = dict(state["needs"])
            needs["social"] = min(100.0, needs["social"] + self.settings.needs_restore_amount.social)

            health_delta = compute_health_delta(
                needs,
                self.settings.needs_critical_threshold,
                self.settings.health_regen_per_tick,
                self.settings.health_decay_per_critical_need,
            )
            health = apply_health_delta(state["health"], health_delta)
            goal_text = f"Talked with {other_detail['name']}."
            next_decision_tick = tick + self.settings.decision_cooldown_ticks

            died, zero_health_ticks, cause = self._check_death(
                state["zero_health_ticks"], health, state["age_ticks"] + 1, state["lifespan_ticks"]
            )
            mood, mood_band = self._update_mood(state, needs, health)

            agents_repo.apply_tick_update(
                self.conn,
                state["id"],
                x=state["x"],
                y=state["y"],
                needs=needs,
                health=health,
                currency=state["currency"],
                current_action=None,
                current_goal=goal_text,
                next_decision_tick=next_decision_tick,
                zero_health_ticks=zero_health_ticks,
                mood=mood,
                mood_band=mood_band,
                tick=tick,
            )

            if died:
                await self._handle_death(state, cause, tick, sim_time)
                continue

            memory_repo.add_memory(
                self.conn,
                agent_id=state["id"],
                tick=tick,
                sim_datetime=sim_time,
                type="conversation",
                content=f"Talked with {other_detail['name']}: {transcript_text}",
                related_agent_id=other_detail["id"],
            )

            if self.broadcast_fn is not None:
                if state.get("moved"):
                    await self.broadcast_fn(
                        "agent_moved",
                        {"agent_id": state["id"], "x": state["x"], "y": state["y"]},
                        tick=tick,
                        sim_time=sim_time,
                    )
                await self.broadcast_fn(
                    "agent_stat_update",
                    {
                        "agent_id": state["id"],
                        "needs": needs,
                        "health": health,
                        "currency": state["currency"],
                        "current_goal": goal_text,
                        "action": "speak",
                        "mood": mood,
                    },
                    tick=tick,
                    sim_time=sim_time,
                )

        if self.broadcast_fn is not None:
            await self.broadcast_fn(
                "conversation",
                {"participants": [state_a["id"], state_b["id"]], "transcript": transcript},
                tick=tick,
                sim_time=sim_time,
            )

        await record_log_event(
            self.conn, self.logger, self.broadcast_fn,
            category="conversation", level="info",
            message=f"{detail_a['name']} and {detail_b['name']} talked.",
            tick=tick, sim_time=sim_time,
            agent_id=state_a["id"], agent_a_id=state_a["id"], agent_b_id=state_b["id"], transcript=transcript,
        )

    async def _update_relationship(
        self, state_a: dict, detail_a: dict, state_b: dict, detail_b: dict, transcript: list[str], tick: int, sim_time: str
    ) -> None:
        """One structured LLM call, from the initiator's perspective, updates
        the single shared (undirected) relationship row for this pair."""
        existing = relationships_repo.get_relationship(self.conn, state_a["id"], state_b["id"])
        previous_affinity = existing["affinity"] if existing else 0.0
        previous_note = existing["note"] if existing else None

        rel_messages = assemble_relationship_prompt(detail_a, detail_b["name"], transcript, previous_note)
        rel_decision = await decide_action(rel_messages, self.settings, tools=RELATIONSHIP_UPDATE_TOOL)

        if rel_decision.used_fallback or rel_decision.action != "update_relationship":
            return

        try:
            delta = float(rel_decision.params.get("affinity_delta", 0))
        except (TypeError, ValueError):
            delta = 0.0
        note = rel_decision.params.get("note") or previous_note or ""
        new_affinity = relationships_repo.clamp_affinity(previous_affinity + delta)

        relationships_repo.upsert_relationship(self.conn, state_a["id"], state_b["id"], new_affinity, note, tick)

        if self.broadcast_fn is not None:
            await self.broadcast_fn(
                "relationship_update",
                {
                    "agent_a_id": min(state_a["id"], state_b["id"]),
                    "agent_b_id": max(state_a["id"], state_b["id"]),
                    "affinity": new_affinity,
                    "note": note,
                },
                tick=tick,
                sim_time=sim_time,
            )

    # ---- Life summaries ----

    async def _run_summarizations(self, tick: int, sim_time: str) -> None:
        candidates = agents_repo.list_agents_for_summary_check(self.conn)
        due = [
            agent
            for agent in candidates
            if should_summarize(
                tick,
                agent["life_summary_updated_tick"],
                agent["created_at_tick"],
                self.settings.summarization_interval_ticks,
            )
        ]
        if not due:
            return

        semaphore = asyncio.Semaphore(max(1, self.settings.worker_concurrency))

        async def worker(agent_row: dict) -> None:
            async with semaphore:
                await self._summarize_one(agent_row, tick, sim_time)

        await asyncio.gather(*(worker(agent_row) for agent_row in due))

    async def _summarize_one(self, agent_row: dict, tick: int, sim_time: str) -> None:
        since_tick = agent_row["life_summary_updated_tick"] or agent_row["created_at_tick"]
        memories = memory_repo.get_memories_since_tick(self.conn, agent_row["id"], since_tick)
        agent_detail = agents_repo.get_agent_detail(self.conn, agent_row["id"])
        messages = assemble_summary_prompt(agent_detail, memories, self.settings)

        result = await summarize(messages, self.settings)

        if result.text is not None:
            agents_repo.update_life_summary(self.conn, agent_row["id"], result.text, tick)

        message = (
            f"{agent_row['name']} reflected on their life so far."
            if result.text is not None
            else f"{agent_row['name']}'s life-summary update failed."
        )
        fields = {
            "agent_id": agent_row["id"],
            "used_llm_fallback": result.used_fallback,
            "llm_attempts": result.attempts,
            "llm_latency_ms": round(result.latency_ms, 1),
            "llm_error": result.error,
        }
        level = "info" if result.text is not None else "warning"
        await record_log_event(
            self.conn, self.logger, self.broadcast_fn,
            category="summarization", level=level, message=message, tick=tick, sim_time=sim_time, **fields,
        )

    async def _log_decision(
        self, agent_detail, decision, outcome, rejected, rejection_reason, tick, sim_time
    ) -> None:
        message = f"{agent_detail['name']} chose {decision.action}: {outcome.goal_text}"
        fields = {
            "agent_id": agent_detail["id"],
            "action": decision.action,
            "rejected": rejected,
            "rejection_reason": rejection_reason,
            "used_llm_fallback": decision.used_fallback,
            "llm_attempts": decision.attempts,
            "llm_latency_ms": round(decision.latency_ms, 1),
            "llm_error": decision.error,
        }

        level = "warning" if (rejected or decision.used_fallback) else "info"
        await record_log_event(
            self.conn, self.logger, self.broadcast_fn,
            category="llm_call", level=level, message=message, tick=tick, sim_time=sim_time, **fields,
        )
