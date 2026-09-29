import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";

const LEVEL_CLASS: Record<string, string> = {
  warning: "log-level-warning",
  error: "log-level-warning",
};

export function LogsPanel() {
  const logs = useStore((s) => s.logs);
  const [categories, setCategories] = useState<string[]>([]);
  const [filter, setFilter] = useState<string>("");

  useEffect(() => {
    api.getLogCategories().then(setCategories).catch(() => setCategories([]));
  }, []);

  const visible = logs.filter((log) => !filter || log.category === filter);

  return (
    <div className="logs-panel">
      <div className="logs-header">
        <h3>Logs</h3>
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>
      <div className="logs-list">
        {visible.length === 0 && <p className="muted">No log events yet.</p>}
        {visible
          .slice()
          .reverse()
          .map((log, i) => (
            <div key={i} className={`log-line ${LEVEL_CLASS[log.level ?? ""] ?? ""}`}>
              <span className="log-tick">{log.tick !== undefined ? `#${log.tick}` : ""}</span>
              <span className="log-category">{log.category ?? "system"}</span>
              <span>{log.message}</span>
            </div>
          ))}
      </div>
    </div>
  );
}
