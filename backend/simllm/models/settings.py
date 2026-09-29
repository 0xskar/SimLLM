from __future__ import annotations

from pydantic import BaseModel


class NeedsDecayRates(BaseModel):
    hunger: float
    energy: float
    social: float
    shelter: float
    hygiene: float
    fun: float
    purpose: float


class NeedsRestoreAmounts(BaseModel):
    hunger: float
    energy: float
    social: float
    hygiene: float
    fun: float
    purpose: float


class BuildingCosts(BaseModel):
    house: float
    workplace: float


class BuildingConstructionTicks(BaseModel):
    house: int
    workplace: int


class Settings(BaseModel):
    """Every tunable knob in the simulation. Persisted as key/value JSON rows
    in a save's `settings` table, seeded from config/default_settings.json.
    """

    population_target: int
    world_width: int
    world_height: int
    tick_interval_seconds: float
    sim_minutes_per_tick: int
    worker_concurrency: int
    decision_cooldown_ticks: int
    autosave_interval_ticks: int
    ollama_model: str
    ollama_host: str
    llm_timeout_seconds: float
    llm_max_retries: int
    perception_radius: int
    conversation_range: int
    conversation_max_turns: int
    conversation_reply_max_chars: int
    memory_buffer_size: int
    life_summary_max_chars: int
    summarization_interval_ticks: int
    mood_band_width: int
    needs_critical_threshold: float
    shelter_home_regen_per_tick: float
    health_regen_per_tick: float
    health_decay_per_critical_need: float
    needs_decay_per_tick: NeedsDecayRates
    needs_restore_amount: NeedsRestoreAmounts
    starting_currency: float
    food_cost: float
    building_costs: BuildingCosts
    building_construction_ticks: BuildingConstructionTicks
    default_job_wage: float
    job_slots_per_workplace: int
    work_energy_cost: float
    workplace_interaction_range: int
    lifespan_ticks_min: int
    lifespan_ticks_max: int
    starvation_death_ticks: int
    max_action_duration_ticks: int
