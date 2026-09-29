import { useEffect } from "react";
import { api } from "./api/client";
import { connectWebSocket } from "./api/ws";
import { AgentInspector } from "./components/AgentInspector";
import { GridCanvas } from "./components/GridCanvas";
import { LogsPanel } from "./components/LogsPanel";
import { SavesScreen } from "./components/SavesScreen";
import { SettingsPanel } from "./components/SettingsPanel";
import { TopBar } from "./components/TopBar";
import { useStore } from "./state/store";

export default function App() {
  const currentSave = useStore((s) => s.currentSave);
  const setWorld = useStore((s) => s.setWorld);
  const setSimStatus = useStore((s) => s.setSimStatus);
  const setConnected = useStore((s) => s.setConnected);
  const setAgents = useStore((s) => s.setAgents);
  const setLogsBackfill = useStore((s) => s.setLogsBackfill);
  const handleWSEvent = useStore((s) => s.handleWSEvent);

  useEffect(() => {
    // Every reconnect (including the first connect) re-fetches full state:
    // the socket carries no session identity, so anything broadcast while
    // disconnected would otherwise be silently missed.
    const resync = () => {
      setConnected(true);
      const { currentSave: save, selectedAgentId, setSelectedAgentDetail } = useStore.getState();
      if (!save) return;
      api.getWorld().then(setWorld);
      api.getSimStatus().then(setSimStatus);
      api.listAgents().then(setAgents);
      api.getLogs().then(setLogsBackfill);
      if (selectedAgentId !== null) {
        api.getAgent(selectedAgentId).then(setSelectedAgentDetail);
      }
    };
    const socket = connectWebSocket(handleWSEvent, resync, () => setConnected(false));
    return () => socket.close();
  }, [handleWSEvent, setConnected, setWorld, setSimStatus, setAgents, setLogsBackfill]);

  useEffect(() => {
    if (!currentSave) return;
    api.getWorld().then(setWorld);
    api.getSimStatus().then(setSimStatus);
    api.listAgents().then(setAgents);
    api.getLogs().then(setLogsBackfill);
  }, [currentSave, setWorld, setSimStatus, setAgents, setLogsBackfill]);

  if (!currentSave) {
    return <SavesScreen />;
  }

  return (
    <div className="app-shell">
      <TopBar />
      <div className="main-area">
        <GridCanvas />
        <div className="side-panel">
          <AgentInspector />
          <SettingsPanel />
          <LogsPanel />
        </div>
      </div>
    </div>
  );
}
