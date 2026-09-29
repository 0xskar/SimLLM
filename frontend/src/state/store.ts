import { create } from "zustand";
import type {
  AgentDetail,
  AgentSummary,
  Building,
  LogEntry,
  SaveSummary,
  SimStatus,
  Tile,
  WorldSnapshot,
  WSEvent,
} from "../types";

export interface ConversationFlash {
  id: number;
  participantIds: number[];
}

interface StoreState {
  saves: SaveSummary[];
  currentSave: string | null;
  world: WorldSnapshot | null;
  simStatus: SimStatus | null;
  logs: LogEntry[];
  connected: boolean;
  agents: AgentSummary[];
  selectedAgentId: number | null;
  selectedAgentDetail: AgentDetail | null;
  conversationFlashes: ConversationFlash[];
  dismissConversationFlash: (id: number) => void;
  setSaves: (saves: SaveSummary[]) => void;
  setCurrentSave: (name: string | null) => void;
  setWorld: (world: WorldSnapshot) => void;
  setSimStatus: (status: SimStatus) => void;
  setConnected: (connected: boolean) => void;
  addLog: (entry: LogEntry) => void;
  setLogsBackfill: (entries: LogEntry[]) => void;
  setAgents: (agents: AgentSummary[]) => void;
  setSelectedAgentId: (id: number | null) => void;
  setSelectedAgentDetail: (detail: AgentDetail | null) => void;
  handleWSEvent: (event: WSEvent) => void;
}

export const useStore = create<StoreState>((set, get) => ({
  saves: [],
  currentSave: null,
  world: null,
  simStatus: null,
  logs: [],
  connected: false,
  agents: [],
  selectedAgentId: null,
  selectedAgentDetail: null,
  conversationFlashes: [],
  dismissConversationFlash: (id) =>
    set((s) => ({ conversationFlashes: s.conversationFlashes.filter((f) => f.id !== id) })),
  setSaves: (saves) => set({ saves }),
  setCurrentSave: (currentSave) => set({ currentSave }),
  setWorld: (world) => set({ world }),
  setSimStatus: (simStatus) => set({ simStatus }),
  setConnected: (connected) => set({ connected }),
  addLog: (entry) => set((s) => ({ logs: [...s.logs.slice(-499), entry] })),
  // GET /api/logs returns most-recent-first; reverse to match the
  // chronological (oldest-first) order addLog appends live entries in.
  setLogsBackfill: (entries) => set({ logs: entries.slice().reverse() }),
  setAgents: (agents) => set({ agents }),
  setSelectedAgentId: (selectedAgentId) => set({ selectedAgentId }),
  setSelectedAgentDetail: (selectedAgentDetail) => set({ selectedAgentDetail }),
  handleWSEvent: (event) => {
    const { type, payload } = event as { type: string; payload: Record<string, unknown> };
    if (type === "tick_complete") {
      set((s) =>
        s.simStatus
          ? {
              simStatus: {
                ...s.simStatus,
                tick: payload.tick as number,
                sim_time: payload.sim_time as string,
                population: payload.population as number,
              },
            }
          : {}
      );
    }
    if (type === "log") {
      const message = typeof payload.message === "string" ? payload.message : JSON.stringify(payload);
      get().addLog({ ...payload, message } as LogEntry);
    }
    if (type === "conversation") {
      const conv = payload as unknown as { participants: number[] };
      const id = Date.now() + Math.random();
      set((s) => ({
        conversationFlashes: [...s.conversationFlashes, { id, participantIds: conv.participants }],
      }));
      setTimeout(() => get().dismissConversationFlash(id), 4000);
    }
    if (type === "tile_update") {
      const tile = payload as unknown as Tile;
      set((s) => {
        if (!s.world) return {};
        const tiles = s.world.tiles.filter((t) => !(t.x === tile.x && t.y === tile.y));
        tiles.push(tile);
        return { world: { ...s.world, tiles } };
      });
    }
    if (type === "building_update") {
      const building = payload as unknown as Building;
      set((s) => {
        if (!s.world) return {};
        const buildings = s.world.buildings.filter((b) => b.id !== building.id);
        buildings.push(building);
        return { world: { ...s.world, buildings } };
      });
    }
    if (type === "agent_moved") {
      const moved = payload as unknown as { agent_id: number; x: number; y: number };
      set((s) => ({
        agents: s.agents.map((a) => (a.id === moved.agent_id ? { ...a, x: moved.x, y: moved.y } : a)),
        selectedAgentDetail:
          s.selectedAgentId === moved.agent_id && s.selectedAgentDetail
            ? { ...s.selectedAgentDetail, x: moved.x, y: moved.y }
            : s.selectedAgentDetail,
      }));
    }
    if (type === "agent_death") {
      const death = payload as unknown as { agent_id: number; cause: string };
      set((s) => ({
        agents: s.agents.map((a) => (a.id === death.agent_id ? { ...a, is_alive: 0 } : a)),
        selectedAgentDetail:
          s.selectedAgentId === death.agent_id && s.selectedAgentDetail
            ? { ...s.selectedAgentDetail, is_alive: 0, death_cause: death.cause }
            : s.selectedAgentDetail,
      }));
    }
    if (type === "agent_created") {
      const created = payload as unknown as AgentSummary;
      set((s) => ({
        agents: s.agents.some((a) => a.id === created.id) ? s.agents : [...s.agents, created],
      }));
    }
    if (type === "agent_stat_update") {
      // Fields are optional: most emissions carry the full stat set, but the
      // emoji re-pick (Milestone 13) only ever sends {agent_id, emoji} --
      // merge only what's actually present so a partial update never
      // clobbers the rest with undefined.
      const update = payload as unknown as {
        agent_id: number;
        needs?: AgentDetail["needs"];
        health?: number;
        currency?: number;
        current_goal?: string;
        mood?: number;
        emoji?: string;
      };
      set((s) => {
        const patch: Partial<AgentDetail> = {};
        if (update.needs !== undefined) patch.needs = update.needs;
        if (update.health !== undefined) patch.health = update.health;
        if (update.currency !== undefined) patch.currency = update.currency;
        if (update.current_goal !== undefined) patch.current_goal = update.current_goal;
        if (update.mood !== undefined) patch.mood = update.mood;
        if (update.emoji !== undefined) patch.emoji = update.emoji;

        const selectedAgentDetail =
          s.selectedAgentId === update.agent_id && s.selectedAgentDetail
            ? { ...s.selectedAgentDetail, ...patch }
            : s.selectedAgentDetail;

        const agents =
          update.emoji !== undefined
            ? s.agents.map((a) => (a.id === update.agent_id ? { ...a, emoji: update.emoji! } : a))
            : s.agents;

        return { selectedAgentDetail, agents };
      });
    }
  },
}));
