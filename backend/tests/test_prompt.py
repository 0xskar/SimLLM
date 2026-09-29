from __future__ import annotations

from simllm.agents.prompt import assemble_prompt
from simllm.config import default_settings
from simllm.sim.needs import NEED_FIELDS


def make_agent(**overrides) -> dict:
    defaults = dict(
        name="Alex",
        emoji="🙂",
        age_ticks=42,
        x=3,
        y=4,
        health=80.0,
        currency=55.0,
        needs={key: 100.0 for key in NEED_FIELDS},
    )
    defaults.update(overrides)
    return defaults


def test_assemble_prompt_has_system_and_user_messages():
    messages = assemble_prompt(make_agent(), default_settings())

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


def test_user_message_includes_identity_and_stats():
    agent = make_agent(name="Robin", emoji="😀", x=7, y=8, health=42.0, currency=99.0)
    messages = assemble_prompt(agent, default_settings())

    content = messages[1]["content"]
    assert "Robin" in content
    assert "😀" in content
    assert "(7, 8)" in content
    assert "42" in content
    assert "99" in content


def test_critical_need_is_flagged():
    settings = default_settings()
    agent = make_agent(needs={**{k: 100.0 for k in NEED_FIELDS}, "hunger": 5.0})

    content = assemble_prompt(agent, settings)[1]["content"]

    assert "hunger: 5 (critical!)" in content
    assert "energy: 100" in content


def test_prompt_omits_life_summary_section_when_absent():
    agent = make_agent(life_summary=None)

    content = assemble_prompt(agent, default_settings())[1]["content"]

    assert "life so far" not in content


def test_prompt_includes_life_summary_when_present():
    agent = make_agent(life_summary="Alex is a cheerful baker who loves mornings.")

    content = assemble_prompt(agent, default_settings())[1]["content"]

    assert "Alex is a cheerful baker who loves mornings." in content


def test_prompt_omits_memory_section_when_no_memories():
    content = assemble_prompt(make_agent(), default_settings(), memories=[])[1]["content"]

    assert "recently happened" not in content


def test_prompt_includes_recent_memories_in_order():
    memories = [
        {"tick": 5, "content": "Had breakfast."},
        {"tick": 6, "content": "Talked a walk."},
    ]
    content = assemble_prompt(make_agent(), default_settings(), memories=memories)[1]["content"]

    assert "Had breakfast." in content
    assert "Talked a walk." in content
    assert content.index("Had breakfast.") < content.index("Talked a walk.")


def test_prompt_omits_nearby_section_when_perception_empty():
    perception = {"tiles": [], "buildings": [], "agents": []}
    content = assemble_prompt(make_agent(), default_settings(), perception=perception)[1]["content"]

    assert "nearby" not in content


def test_prompt_includes_nearby_buildings_and_agents():
    perception = {
        "tiles": [],
        "buildings": [{"id": 1, "type": "workplace", "x": 5, "y": 5}],
        "agents": [{"id": 2, "name": "Bailey", "x": 4, "y": 4, "current_goal": "Eating."}],
    }
    content = assemble_prompt(make_agent(), default_settings(), perception=perception)[1]["content"]

    assert "workplace at (5, 5)" in content
    assert "Bailey (id 2) at (4, 4), Eating." in content


def test_prompt_handles_nearby_agent_without_current_goal():
    perception = {"tiles": [], "buildings": [], "agents": [{"id": 2, "name": "Bailey", "x": 4, "y": 4, "current_goal": None}]}
    content = assemble_prompt(make_agent(), default_settings(), perception=perception)[1]["content"]

    assert "Bailey (id 2) at (4, 4)" in content


def test_prompt_omits_current_job_section_when_unemployed():
    content = assemble_prompt(make_agent(current_job=None), default_settings())[1]["content"]

    assert "You have a job" not in content


def test_prompt_includes_current_job_when_employed():
    agent = make_agent(current_job={"title": "Baker", "x": 5, "y": 5, "wage_per_shift": 30.0})
    content = assemble_prompt(agent, default_settings())[1]["content"]

    assert "Baker" in content
    assert "(5, 5)" in content
    assert "30" in content


def test_prompt_includes_open_job_listings_from_perception():
    perception = {
        "tiles": [],
        "buildings": [],
        "agents": [],
        "jobs": [{"id": 9, "title": "Worker", "x": 3, "y": 3, "wage_per_shift": 25.0, "slots": 3, "filled": 1}],
    }
    content = assemble_prompt(make_agent(), default_settings(), perception=perception)[1]["content"]

    assert "Job opening: Worker (id 9)" in content
    assert "2 slot(s) open" in content


def test_prompt_omits_full_job_listings():
    perception = {
        "tiles": [],
        "buildings": [],
        "agents": [],
        "jobs": [{"id": 9, "title": "Worker", "x": 3, "y": 3, "wage_per_shift": 25.0, "slots": 2, "filled": 2}],
    }
    content = assemble_prompt(make_agent(), default_settings(), perception=perception)[1]["content"]

    assert "Job opening" not in content
