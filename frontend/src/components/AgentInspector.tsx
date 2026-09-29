import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import type { AgentMemory, Relationship } from "../types";

const NEED_LABELS: Record<string, string> = {
  hunger: "Hunger",
  energy: "Energy",
  social: "Social",
  shelter: "Shelter",
  hygiene: "Hygiene",
  fun: "Fun",
  purpose: "Purpose",
};

export function AgentInspector() {
  const detail = useStore((s) => s.selectedAgentDetail);
  const setSelectedAgentId = useStore((s) => s.setSelectedAgentId);
  const setSelectedAgentDetail = useStore((s) => s.setSelectedAgentDetail);
  const [memories, setMemories] = useState<AgentMemory[]>([]);
  const [relationships, setRelationships] = useState<Relationship[]>([]);

  useEffect(() => {
    if (!detail) {
      setMemories([]);
      setRelationships([]);
      return;
    }
    api.getAgentMemories(detail.id).then(setMemories);
    api.getAgentRelationships(detail.id).then(setRelationships);
    // Re-fetch whenever a new decision resolves for this agent (current_goal
    // changes each time one does, including after a conversation), so both
    // stay live without polling.
  }, [detail?.id, detail?.current_goal]);

  if (!detail) {
    return (
      <div className="agent-inspector">
        <p className="muted">Click an agent on the grid to inspect them.</p>
      </div>
    );
  }

  const close = () => {
    setSelectedAgentId(null);
    setSelectedAgentDetail(null);
  };

  return (
    <div className="agent-inspector">
      <div className="inspector-header">
        <h3>
          {detail.emoji} {detail.name}
        </h3>
        <button onClick={close}>Close</button>
      </div>

      {!detail.is_alive && (
        <p className="death-banner">
          Died at tick {detail.death_tick}
          {detail.death_cause ? ` (${detail.death_cause})` : ""}.
        </p>
      )}

      <p className="current-goal">{detail.current_goal ?? "..."}</p>
      {detail.current_action && <p className="current-action muted">doing: {detail.current_action}</p>}

      {detail.backstory && <p className="life-summary">{detail.backstory}</p>}
      {detail.life_summary && <p className="life-summary">{detail.life_summary}</p>}

      {detail.traits.length > 0 && (
        <div className="trait-list">
          {detail.traits.map((t) => (
            <span key={t.name} className="trait-chip">
              {t.name}
            </span>
          ))}
        </div>
      )}

      <div className="stat-row">
        <span>Health</span>
        <span>{detail.health.toFixed(0)}</span>
      </div>
      <div className="stat-row">
        <span>Mood</span>
        <span>{detail.mood.toFixed(0)}</span>
      </div>
      <div className="stat-row">
        <span>Currency</span>
        <span>{detail.currency.toFixed(0)}</span>
      </div>
      <div className="stat-row">
        <span>Age (ticks)</span>
        <span>
          {detail.age_ticks} / {detail.lifespan_ticks}
        </span>
      </div>
      <div className="stat-row">
        <span>Generation</span>
        <span>{detail.generation}</span>
      </div>

      <h4>Property</h4>
      {!detail.home_building && !detail.current_job && <p className="muted">Owns nothing yet.</p>}
      {detail.home_building && (
        <div className="stat-row">
          <span>Home</span>
          <span>
            {detail.home_building.status === "complete"
              ? `${detail.home_building.type} at (${detail.home_building.x}, ${detail.home_building.y})`
              : `${detail.home_building.type} under construction (${detail.home_building.construction_progress}/${detail.home_building.construction_total_ticks})`}
          </span>
        </div>
      )}
      {detail.current_job && (
        <div className="stat-row">
          <span>Job</span>
          <span>
            {detail.current_job.title} at ({detail.current_job.x}, {detail.current_job.y}), pays{" "}
            {detail.current_job.wage_per_shift.toFixed(0)}/shift
          </span>
        </div>
      )}

      <h4>Needs</h4>
      {Object.entries(detail.needs).map(([key, value]) => (
        <div key={key} className="need-bar-row">
          <span className="need-label">{NEED_LABELS[key] ?? key}</span>
          <div className="need-bar-track">
            <div className="need-bar-fill" style={{ width: `${value}%` }} />
          </div>
          <span className="need-value">{value.toFixed(0)}</span>
        </div>
      ))}

      <h4>Relationships</h4>
      {relationships.length === 0 && <p className="muted">No one they know yet.</p>}
      <div className="relationship-list">
        {relationships.map((r) => (
          <div key={r.other_agent_id} className="relationship-row">
            <span className="relationship-name">
              {r.other_emoji} {r.other_name}
            </span>
            <span className={r.affinity >= 0 ? "affinity positive" : "affinity negative"}>
              {r.affinity > 0 ? "+" : ""}
              {r.affinity.toFixed(0)}
            </span>
            <p className="relationship-note">{r.note}</p>
          </div>
        ))}
      </div>

      <h4>History</h4>
      {memories.length === 0 && <p className="muted">Nothing has happened yet.</p>}
      <div className="memory-list">
        {memories.map((m) => (
          <div key={m.id} className="memory-line">
            <span className="memory-tick">tick {m.tick}</span>
            <span>{m.content}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
