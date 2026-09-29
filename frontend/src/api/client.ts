import type {
  AgentDetail,
  AgentMemory,
  AgentSummary,
  LogEntry,
  Relationship,
  SaveSummary,
  SimStatus,
  WorldSnapshot,
} from "../types";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export interface CreateSaveRequest {
  name: string;
  world_width?: number;
  world_height?: number;
  population_target?: number;
}

export interface OllamaModelInfo {
  name: string;
  size: number;
  parameter_size: string | null;
  family: string | null;
  recommended: boolean;
}

export const api = {
  listSaves: () => request<SaveSummary[]>("/api/saves"),
  createSave: (body: CreateSaveRequest) =>
    request<SaveSummary>("/api/saves", { method: "POST", body: JSON.stringify(body) }),
  loadSave: (name: string) =>
    request<SaveSummary>(`/api/saves/${encodeURIComponent(name)}/load`, { method: "POST" }),
  deleteSave: (name: string) =>
    request<void>(`/api/saves/${encodeURIComponent(name)}`, { method: "DELETE" }),
  getWorld: () => request<WorldSnapshot>("/api/world"),
  getSimStatus: () => request<SimStatus>("/api/sim/status"),
  startSim: () => request<SimStatus>("/api/sim/start", { method: "POST" }),
  pauseSim: () => request<SimStatus>("/api/sim/pause", { method: "POST" }),
  resumeSim: () => request<SimStatus>("/api/sim/resume", { method: "POST" }),
  stepSim: () => request<{ tick: number; sim_time: string; population: number }>(
    "/api/sim/step",
    { method: "POST" }
  ),
  getSettings: () => request<Record<string, unknown>>("/api/settings"),
  putSettings: (overrides: Record<string, unknown>) =>
    request<Record<string, unknown>>("/api/settings", {
      method: "PUT",
      body: JSON.stringify(overrides),
    }),
  listAgents: () => request<AgentSummary[]>("/api/agents"),
  getAgent: (id: number) => request<AgentDetail>(`/api/agents/${id}`),
  getAgentMemories: (id: number) => request<AgentMemory[]>(`/api/agents/${id}/memories`),
  getAgentRelationships: (id: number) => request<Relationship[]>(`/api/agents/${id}/relationships`),
  listModels: () => request<OllamaModelInfo[]>("/api/models"),
  getLogs: (category?: string, limit = 200) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (category) params.set("category", category);
    return request<LogEntry[]>(`/api/logs?${params.toString()}`);
  },
  getLogCategories: () => request<string[]>("/api/logs/categories"),
};
