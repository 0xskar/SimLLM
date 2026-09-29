from __future__ import annotations

from simllm.agents.actions import AgentContext, apply_action
from simllm.sim.needs import NEED_FIELDS


def make_ctx(**overrides) -> AgentContext:
    defaults = dict(
        x=5,
        y=5,
        needs={key: 100.0 for key in NEED_FIELDS},
        currency=100.0,
        home_pos=(5, 5),
        world_width=20,
        world_height=20,
    )
    defaults.update(overrides)
    return AgentContext(**defaults)


def get_settings():
    # Real Settings object (needed by the eat/sleep/etc handlers), independent
    # of any save file.
    from simllm.config import default_settings

    return default_settings()


def test_idle_is_always_accepted_and_unchanged():
    ctx = make_ctx()
    outcome = apply_action("idle", {"reason": "Nothing to do."}, ctx, get_settings())

    assert outcome.accepted
    assert (outcome.x, outcome.y) == (5, 5)
    assert outcome.needs == ctx.needs
    assert outcome.currency == ctx.currency
    assert outcome.goal_text == "Nothing to do."


def test_move_to_in_bounds_is_accepted_as_a_pending_action():
    # move_to no longer teleports -- it hands back a pending_action for the
    # engine to turn into an A*-computed multi-tick path. Position is
    # unchanged here; only the engine (with world/DB access) can pathfind.
    ctx = make_ctx()
    outcome = apply_action("move_to", {"target_x": 10, "target_y": 3}, ctx, get_settings())

    assert outcome.accepted
    assert (outcome.x, outcome.y) == (5, 5)
    assert outcome.pending_action == {"type": "move_to", "target": [10, 3]}


def test_move_to_out_of_bounds_is_rejected():
    ctx = make_ctx(world_width=20, world_height=20)
    outcome = apply_action("move_to", {"target_x": 99, "target_y": 3}, ctx, get_settings())

    assert not outcome.accepted
    assert outcome.reason == "out_of_bounds"
    assert (outcome.x, outcome.y) == (5, 5)  # unchanged


def test_move_to_missing_coordinates_is_rejected():
    ctx = make_ctx()
    outcome = apply_action("move_to", {"reason": "wander"}, ctx, get_settings())

    assert not outcome.accepted
    assert outcome.reason == "out_of_bounds"


def test_eat_deducts_currency_and_restores_hunger():
    settings = get_settings()
    ctx = make_ctx(needs={**{k: 100.0 for k in NEED_FIELDS}, "hunger": 10.0}, currency=50.0)

    outcome = apply_action("eat", {"reason": "hungry"}, ctx, settings)

    assert outcome.accepted
    assert outcome.currency == 50.0 - settings.food_cost
    assert outcome.needs["hunger"] == min(100.0, 10.0 + settings.needs_restore_amount.hunger)


def test_eat_without_enough_currency_is_rejected():
    settings = get_settings()
    ctx = make_ctx(needs={**{k: 100.0 for k in NEED_FIELDS}, "hunger": 10.0}, currency=0.0)

    outcome = apply_action("eat", {}, ctx, settings)

    assert not outcome.accepted
    assert outcome.reason == "insufficient_funds"
    assert outcome.needs["hunger"] == 10.0  # unchanged


def test_sleep_restores_energy():
    settings = get_settings()
    ctx = make_ctx(needs={**{k: 100.0 for k in NEED_FIELDS}, "energy": 20.0})

    outcome = apply_action("sleep", {}, ctx, settings)

    assert outcome.accepted
    assert outcome.needs["energy"] == min(100.0, 20.0 + settings.needs_restore_amount.energy)


def test_wash_up_restores_hygiene():
    settings = get_settings()
    ctx = make_ctx(needs={**{k: 100.0 for k in NEED_FIELDS}, "hygiene": 15.0})

    outcome = apply_action("wash_up", {}, ctx, settings)

    assert outcome.accepted
    assert outcome.needs["hygiene"] == min(100.0, 15.0 + settings.needs_restore_amount.hygiene)


def test_have_fun_restores_fun():
    settings = get_settings()
    ctx = make_ctx(needs={**{k: 100.0 for k in NEED_FIELDS}, "fun": 30.0})

    outcome = apply_action("have_fun", {}, ctx, settings)

    assert outcome.accepted
    assert outcome.needs["fun"] == min(100.0, 30.0 + settings.needs_restore_amount.fun)


def test_unknown_action_is_rejected():
    ctx = make_ctx()
    outcome = apply_action("fly_to_the_moon", {}, ctx, get_settings())

    assert not outcome.accepted
    assert outcome.reason == "unknown_action"


def test_speak_with_valid_params_is_accepted_as_pending_action():
    # Like move_to, speak only does structural validation here -- whether
    # the target is actually alive/in-range/available is the engine's job
    # (it needs world/agent state this pure module doesn't have).
    ctx = make_ctx()
    outcome = apply_action(
        "speak", {"target_agent_id": 7, "message": "Hello there!"}, ctx, get_settings()
    )

    assert outcome.accepted
    assert outcome.pending_action == {"type": "speak", "target_agent_id": 7, "message": "Hello there!"}


def test_speak_without_message_is_rejected():
    ctx = make_ctx()
    outcome = apply_action("speak", {"target_agent_id": 7}, ctx, get_settings())

    assert not outcome.accepted
    assert outcome.reason == "invalid_speak_params"


def test_speak_with_blank_message_is_rejected():
    ctx = make_ctx()
    outcome = apply_action("speak", {"target_agent_id": 7, "message": "   "}, ctx, get_settings())

    assert not outcome.accepted
    assert outcome.reason == "invalid_speak_params"


def test_speak_with_non_integer_target_is_rejected():
    ctx = make_ctx()
    outcome = apply_action("speak", {"target_agent_id": "seven", "message": "Hi"}, ctx, get_settings())

    assert not outcome.accepted
    assert outcome.reason == "invalid_speak_params"


def test_take_job_with_valid_id_is_accepted_as_pending_action():
    # Like move_to/speak, take_job only does structural validation here --
    # whether the job is actually open and the agent is at the workplace is
    # the engine's job (it needs DB state this pure module doesn't have).
    ctx = make_ctx()
    outcome = apply_action("take_job", {"job_id": 3}, ctx, get_settings())

    assert outcome.accepted
    assert outcome.pending_action == {"type": "take_job", "job_id": 3}


def test_take_job_without_job_id_is_rejected():
    ctx = make_ctx()
    outcome = apply_action("take_job", {}, ctx, get_settings())

    assert not outcome.accepted
    assert outcome.reason == "invalid_job_id"


def test_take_job_with_non_integer_job_id_is_rejected():
    ctx = make_ctx()
    outcome = apply_action("take_job", {"job_id": "three"}, ctx, get_settings())

    assert not outcome.accepted
    assert outcome.reason == "invalid_job_id"


def test_work_job_is_always_accepted_as_pending_action():
    ctx = make_ctx()
    outcome = apply_action("work_job", {}, ctx, get_settings())

    assert outcome.accepted
    assert outcome.pending_action == {"type": "work_job"}
    assert outcome.needs == ctx.needs  # payment/needs effects are the engine's job
    assert outcome.currency == ctx.currency


def test_start_build_with_valid_params_is_accepted_as_pending_action():
    ctx = make_ctx()
    outcome = apply_action(
        "start_build", {"building_type": "house", "target_x": 6, "target_y": 6}, ctx, get_settings()
    )

    assert outcome.accepted
    assert outcome.pending_action == {"type": "start_build", "building_type": "house", "target": [6, 6]}
    assert outcome.currency == ctx.currency  # cost deduction is the engine's job


def test_start_build_with_invalid_building_type_is_rejected():
    ctx = make_ctx()
    outcome = apply_action(
        "start_build", {"building_type": "castle", "target_x": 6, "target_y": 6}, ctx, get_settings()
    )

    assert not outcome.accepted
    assert outcome.reason == "invalid_build_params"


def test_start_build_out_of_bounds_is_rejected():
    ctx = make_ctx(world_width=20, world_height=20)
    outcome = apply_action(
        "start_build", {"building_type": "house", "target_x": 99, "target_y": 6}, ctx, get_settings()
    )

    assert not outcome.accepted
    assert outcome.reason == "invalid_build_params"
