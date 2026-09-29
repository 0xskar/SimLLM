export interface SaveSummary {
  name: string;
  created_at: string;
  current_tick: number;
  generation: number;
  population: number;
  last_saved_at: string | null;
}

export interface Tile {
  x: number;
  y: number;
  tile_type: string;
  building_id: number | null;
}

export interface Building {
  id: number;
  type: string;
  x: number;
  y: number;
  owner_agent_id: number | null;
  status: string;
  construction_progress: number;
  construction_total_ticks: number;
  capacity: number | null;
}

export interface WorldSnapshot {
  width: number;
  height: number;
  tiles: Tile[];
  buildings: Building[];
}

export interface SimStatus {
  tick: number;
  sim_time: string;
  is_paused: boolean;
  generation: number;
  population: number;
  save_name: string | null;
  last_saved_at: string | null;
}

export interface WSEvent<T = unknown> {
  type: string;
  tick: number | null;
  sim_time: string | null;
  payload: T;
}

export interface LogEntry {
  level?: string;
  message: string;
  category?: string;
  timestamp?: string;
  tick?: number;
  agent_id?: number | null;
  [key: string]: unknown;
}

export interface AgentSummary {
  id: number;
  name: string;
  emoji: string;
  x: number;
  y: number;
  is_alive: number;
}

export interface AgentNeeds {
  hunger: number;
  energy: number;
  social: number;
  shelter: number;
  hygiene: number;
  fun: number;
  purpose: number;
}

export interface Trait {
  name: string;
  value: number;
}

export interface AgentDetail {
  id: number;
  name: string;
  emoji: string;
  traits: Trait[];
  backstory: string | null;
  age_ticks: number;
  lifespan_ticks: number;
  age_stage: string;
  x: number;
  y: number;
  home_building_id: number | null;
  currency: number;
  health: number;
  mood: number;
  mood_band: number;
  is_alive: number;
  death_tick: number | null;
  death_cause: string | null;
  generation: number;
  created_at_tick: number;
  current_action: string | null;
  next_decision_tick: number;
  current_goal: string | null;
  life_summary: string | null;
  life_summary_updated_tick: number | null;
  needs: AgentNeeds;
  current_job: JobAssignment | null;
  home_building: OwnedBuilding | null;
}

export interface JobAssignment {
  assignment_id: number;
  job_id: number;
  agent_id: number;
  started_tick: number;
  title: string;
  wage_per_shift: number;
  workplace_building_id: number;
  x: number;
  y: number;
}

export interface OwnedBuilding {
  id: number;
  type: string;
  x: number;
  y: number;
  status: string;
  construction_progress: number;
  construction_total_ticks: number;
}

export interface AgentMemory {
  id: number;
  agent_id: number;
  tick: number;
  sim_datetime: string;
  type: string;
  content: string;
  related_agent_id: number | null;
}

export interface Relationship {
  other_agent_id: number;
  other_name: string;
  other_emoji: string;
  affinity: number;
  note: string;
  updated_tick: number;
}

export interface AgentStatUpdatePayload {
  agent_id: number;
  needs: AgentNeeds;
  health: number;
  currency: number;
  current_goal: string;
  action: string;
}
