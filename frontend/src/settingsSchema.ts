export interface FieldSpec {
  path: string[];
  label: string;
  step?: number;
  min?: number;
  type?: "number" | "text";
}

export interface SectionSpec {
  title: string;
  fields: FieldSpec[];
}

// Every tunable in Settings (backend/simllm/models/settings.py), organized
// for editing. ollama_model gets a dedicated model-picker dropdown instead
// of appearing here (see SettingsPanel.tsx).
export const SETTINGS_SCHEMA: SectionSpec[] = [
  {
    title: "Simulation",
    fields: [
      { path: ["population_target"], label: "Population target", min: 1 },
      { path: ["world_width"], label: "World width (tiles)", min: 4 },
      { path: ["world_height"], label: "World height (tiles)", min: 4 },
      { path: ["tick_interval_seconds"], label: "Tick interval (seconds)", step: 0.5, min: 0 },
      { path: ["sim_minutes_per_tick"], label: "Sim minutes per tick", min: 1 },
      { path: ["worker_concurrency"], label: "LLM worker concurrency", min: 1 },
      { path: ["decision_cooldown_ticks"], label: "Decision cooldown (ticks)", min: 0 },
      { path: ["autosave_interval_ticks"], label: "Autosave interval (ticks, 0 = off)", min: 0 },
    ],
  },
  {
    title: "AI Model",
    fields: [
      { path: ["ollama_host"], label: "Ollama host URL", type: "text" },
      { path: ["llm_timeout_seconds"], label: "LLM timeout (seconds)", step: 1, min: 1 },
      { path: ["llm_max_retries"], label: "LLM max retries", min: 0 },
    ],
  },
  {
    title: "Perception & Conversation",
    fields: [
      { path: ["perception_radius"], label: "Perception radius (tiles)", min: 0 },
      { path: ["conversation_range"], label: "Conversation range (tiles)", min: 0 },
      { path: ["conversation_max_turns"], label: "Conversation max turns", min: 1 },
      { path: ["conversation_reply_max_chars"], label: "Conversation reply max length", min: 20 },
    ],
  },
  {
    title: "Memory",
    fields: [
      { path: ["memory_buffer_size"], label: "Memory buffer size (recent events)", min: 0 },
      { path: ["life_summary_max_chars"], label: "Life summary max length", min: 50 },
      { path: ["summarization_interval_ticks"], label: "Summarization interval (ticks)", min: 1 },
    ],
  },
  {
    title: "Mood",
    fields: [{ path: ["mood_band_width"], label: "Mood band width", min: 1 }],
  },
  {
    title: "Needs & Health",
    fields: [
      { path: ["needs_critical_threshold"], label: "Critical need threshold", min: 0 },
      { path: ["shelter_home_regen_per_tick"], label: "Shelter regen at home (per tick)", step: 0.1 },
      { path: ["health_regen_per_tick"], label: "Health regen (per tick)", step: 0.1 },
      { path: ["health_decay_per_critical_need"], label: "Health decay per critical need", step: 0.1 },
    ],
  },
  {
    title: "Needs Decay Rates (per tick)",
    fields: [
      { path: ["needs_decay_per_tick", "hunger"], label: "Hunger", step: 0.1 },
      { path: ["needs_decay_per_tick", "energy"], label: "Energy", step: 0.1 },
      { path: ["needs_decay_per_tick", "social"], label: "Social", step: 0.1 },
      { path: ["needs_decay_per_tick", "shelter"], label: "Shelter", step: 0.1 },
      { path: ["needs_decay_per_tick", "hygiene"], label: "Hygiene", step: 0.1 },
      { path: ["needs_decay_per_tick", "fun"], label: "Fun", step: 0.1 },
      { path: ["needs_decay_per_tick", "purpose"], label: "Purpose", step: 0.1 },
    ],
  },
  {
    title: "Needs Restore Amounts",
    fields: [
      { path: ["needs_restore_amount", "hunger"], label: "Hunger (eat)", step: 1 },
      { path: ["needs_restore_amount", "energy"], label: "Energy (sleep)", step: 1 },
      { path: ["needs_restore_amount", "social"], label: "Social (conversation)", step: 1 },
      { path: ["needs_restore_amount", "hygiene"], label: "Hygiene (wash up)", step: 1 },
      { path: ["needs_restore_amount", "fun"], label: "Fun (have fun)", step: 1 },
      { path: ["needs_restore_amount", "purpose"], label: "Purpose (work)", step: 1 },
    ],
  },
  {
    title: "Economy",
    fields: [
      { path: ["starting_currency"], label: "Starting currency", min: 0 },
      { path: ["food_cost"], label: "Food cost", min: 0 },
      { path: ["default_job_wage"], label: "Default job wage (per shift)", min: 0 },
      { path: ["job_slots_per_workplace"], label: "Job slots per workplace", min: 1 },
      { path: ["work_energy_cost"], label: "Energy cost per shift", min: 0 },
      { path: ["workplace_interaction_range"], label: "Workplace interaction range (tiles)", min: 0 },
    ],
  },
  {
    title: "Buildings",
    fields: [
      { path: ["building_costs", "house"], label: "House cost", min: 0 },
      { path: ["building_costs", "workplace"], label: "Workplace cost", min: 0 },
      { path: ["building_construction_ticks", "house"], label: "House construction time (ticks)", min: 1 },
      { path: ["building_construction_ticks", "workplace"], label: "Workplace construction time (ticks)", min: 1 },
    ],
  },
  {
    title: "Lifespan & Death",
    fields: [
      { path: ["lifespan_ticks_min"], label: "Minimum lifespan (ticks)", min: 1 },
      { path: ["lifespan_ticks_max"], label: "Maximum lifespan (ticks)", min: 1 },
      { path: ["starvation_death_ticks"], label: "Starvation death threshold (ticks at 0 health)", min: 1 },
      { path: ["max_action_duration_ticks"], label: "Max action duration (ticks)", min: 1 },
    ],
  },
];

export function getPath(obj: Record<string, unknown>, path: string[]): unknown {
  let current: unknown = obj;
  for (const key of path) {
    if (current == null || typeof current !== "object") return undefined;
    current = (current as Record<string, unknown>)[key];
  }
  return current;
}

export function setPath(
  obj: Record<string, unknown>,
  path: string[],
  value: unknown
): Record<string, unknown> {
  const [head, ...rest] = path;
  if (rest.length === 0) {
    return { ...obj, [head]: value };
  }
  const child = (obj[head] as Record<string, unknown>) ?? {};
  return { ...obj, [head]: setPath(child, rest, value) };
}
