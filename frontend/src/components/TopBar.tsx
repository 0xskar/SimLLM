import { api } from "../api/client";
import { formatRelativeTime } from "../format";
import { useStore } from "../state/store";

export function TopBar() {
  const simStatus = useStore((s) => s.simStatus);
  const setSimStatus = useStore((s) => s.setSimStatus);
  const connected = useStore((s) => s.connected);
  const currentSave = useStore((s) => s.currentSave);
  const setCurrentSave = useStore((s) => s.setCurrentSave);

  if (!simStatus) return null;

  const refresh = () => api.getSimStatus().then(setSimStatus);

  return (
    <div className="top-bar">
      <strong>{currentSave}</strong>
      <span>tick {simStatus.tick}</span>
      <span>{simStatus.sim_time}</span>
      <span>pop {simStatus.population}</span>
      <span>gen {simStatus.generation}</span>
      <span className="muted" title={simStatus.last_saved_at ?? undefined}>
        saved {formatRelativeTime(simStatus.last_saved_at)}
      </span>
      <span className={connected ? "ws-dot connected" : "ws-dot"} title={connected ? "connected" : "reconnecting..."} />
      {!connected && <span className="muted reconnecting">reconnecting&hellip;</span>}

      {simStatus.is_paused ? (
        <>
          <button onClick={() => api.startSim().then(setSimStatus)}>Start</button>
          <button onClick={() => api.stepSim().then(refresh)}>Step</button>
        </>
      ) : (
        <button onClick={() => api.pauseSim().then(setSimStatus)}>Pause</button>
      )}

      <button onClick={() => setCurrentSave(null)}>Back to saves</button>
    </div>
  );
}
