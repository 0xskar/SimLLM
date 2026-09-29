from __future__ import annotations

import json
import random
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from simllm.config import SAVES_DIR, load_default_settings_dict
from simllm.db import agents_repo, world_repo
from simllm.db.connection import SCHEMA_VERSION, init_schema, open_connection
from simllm.models.settings import Settings
from simllm.sim.world_gen import seed_world

SIM_EPOCH = "2000-01-01T06:00:00"


class SaveAlreadyExistsError(Exception):
    pass


class SaveNotFoundError(Exception):
    pass


@dataclass
class SaveSummary:
    name: str
    created_at: str
    current_tick: int
    generation: int
    population: int
    last_saved_at: str | None


def _save_path(name: str) -> Path:
    return SAVES_DIR / f"{name}.sqlite3"


def create_save(
    name: str,
    world_width: int | None = None,
    world_height: int | None = None,
    population_target: int | None = None,
    setting_overrides: dict | None = None,
) -> Path:
    path = _save_path(name)
    if path.exists():
        raise SaveAlreadyExistsError(f"Save '{name}' already exists")

    SAVES_DIR.mkdir(parents=True, exist_ok=True)

    overrides = dict(setting_overrides or {})
    if world_width is not None:
        overrides["world_width"] = world_width
    if world_height is not None:
        overrides["world_height"] = world_height
    if population_target is not None:
        overrides["population_target"] = population_target

    merged = dict(load_default_settings_dict())
    merged.update(overrides)
    settings = Settings.model_validate(merged)

    conn = open_connection(path)
    try:
        init_schema(conn)
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO meta (id, save_name, schema_version, created_at) VALUES (1, ?, ?, ?)",
            (name, SCHEMA_VERSION, now),
        )
        conn.execute(
            "INSERT INTO sim_clock (id, current_tick, sim_datetime, is_paused, generation) "
            "VALUES (1, 0, ?, 1, 1)",
            (SIM_EPOCH,),
        )
        for key, value in settings.model_dump().items():
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?)",
                (key, json.dumps(value)),
            )
        conn.commit()
        seed_world(conn, settings)
        _spawn_starter_agent(conn, settings)
        conn.commit()
    finally:
        conn.close()

    return path


STARTER_EMOJIS = ["🙂", "😀", "🙃", "😎", "🤓", "🧐", "😇", "🥳", "🤠", "😌"]
STARTER_NAMES = [
    "Alex", "Bailey", "Casey", "Dana", "Ellis", "Frankie",
    "Gray", "Harper", "Indigo", "Jules",
]


def _spawn_starter_agent(conn: sqlite3.Connection, settings: Settings) -> None:
    """Placeholder (non-LLM) identities, one per seeded house up to
    `population_target`, to give the worker pool real agents to schedule.
    Milestone 12 (Death + respawn) introduces LLM-generated personalities
    for both the initial population and later newcomers, replacing these.
    """
    houses = conn.execute(
        "SELECT id, x, y FROM buildings WHERE type = 'house' ORDER BY id LIMIT ?",
        (settings.population_target,),
    ).fetchall()

    for i, house in enumerate(houses):
        agent_id = agents_repo.create_agent(
            conn,
            name=STARTER_NAMES[i % len(STARTER_NAMES)],
            emoji=STARTER_EMOJIS[i % len(STARTER_EMOJIS)],
            traits=[],
            backstory=None,
            x=house["x"],
            y=house["y"],
            home_building_id=house["id"],
            lifespan_ticks=random.randint(settings.lifespan_ticks_min, settings.lifespan_ticks_max),
            currency=settings.starting_currency,
            generation=1,
            created_at_tick=0,
        )
        world_repo.set_building_owner(conn, house["id"], agent_id)


def list_saves() -> list[SaveSummary]:
    if not SAVES_DIR.exists():
        return []
    summaries: list[SaveSummary] = []
    for path in sorted(SAVES_DIR.glob("*.sqlite3")):
        try:
            conn = open_connection(path)
            meta = conn.execute("SELECT save_name, created_at FROM meta WHERE id = 1").fetchone()
            clock = conn.execute(
                "SELECT current_tick, generation, last_saved_at FROM sim_clock WHERE id = 1"
            ).fetchone()
            population = conn.execute(
                "SELECT COUNT(*) AS c FROM agents WHERE is_alive = 1"
            ).fetchone()
            conn.close()
            if meta is None or clock is None:
                continue
            summaries.append(
                SaveSummary(
                    name=meta["save_name"],
                    created_at=meta["created_at"],
                    current_tick=clock["current_tick"],
                    generation=clock["generation"],
                    population=population["c"] if population else 0,
                    last_saved_at=clock["last_saved_at"],
                )
            )
        except sqlite3.DatabaseError:
            continue
    return summaries


def load_save(name: str) -> sqlite3.Connection:
    path = _save_path(name)
    if not path.exists():
        raise SaveNotFoundError(f"Save '{name}' not found")
    return open_connection(path)


def delete_save(name: str) -> None:
    path = _save_path(name)
    if not path.exists():
        raise SaveNotFoundError(f"Save '{name}' not found")
    path.unlink()
    for suffix in ("-wal", "-shm"):
        sidecar = path.with_name(path.name + suffix)
        if sidecar.exists():
            sidecar.unlink()


def load_settings(conn: sqlite3.Connection) -> Settings:
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    overrides = {row["key"]: json.loads(row["value"]) for row in rows}
    merged = dict(load_default_settings_dict())
    merged.update(overrides)
    return Settings.model_validate(merged)


def touch_last_saved(conn: sqlite3.Connection) -> str:
    """Records that the save's on-disk state is up to date as of now.
    Caller is responsible for committing."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("UPDATE sim_clock SET last_saved_at = ? WHERE id = 1", (now,))
    return now


def checkpoint(conn: sqlite3.Connection) -> None:
    """Forces WAL contents back into the main .sqlite3 file. In WAL mode
    (see db/connection.py) writes normally accumulate in a separate -wal
    file that's only merged in periodically by SQLite itself; calling this
    at deliberate save points (autosave, pause) keeps the main file
    reasonably current if the process were to be killed uncleanly."""
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")


def save_settings(conn: sqlite3.Connection, settings: Settings) -> None:
    for key, value in settings.model_dump().items():
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value)),
        )
    conn.commit()
