import { useEffect, useState } from "react";
import { api } from "../api/client";
import { formatRelativeTime } from "../format";
import { useStore } from "../state/store";

export function SavesScreen() {
  const saves = useStore((s) => s.saves);
  const setSaves = useStore((s) => s.setSaves);
  const setCurrentSave = useStore((s) => s.setCurrentSave);

  const [name, setName] = useState("");
  const [population, setPopulation] = useState(8);
  const [worldSize, setWorldSize] = useState(24);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    api.listSaves().then(setSaves).catch((e) => setError(String(e)));
  };

  useEffect(refresh, []);

  const handleCreate = async () => {
    if (!name.trim()) return;
    try {
      await api.createSave({
        name: name.trim(),
        population_target: population,
        world_width: worldSize,
        world_height: worldSize,
      });
      setName("");
      refresh();
    } catch (e) {
      setError(String(e));
    }
  };

  const handleLoad = async (saveName: string) => {
    try {
      await api.loadSave(saveName);
      setCurrentSave(saveName);
    } catch (e) {
      setError(String(e));
    }
  };

  const handleDelete = async (saveName: string) => {
    if (!window.confirm(`Delete save "${saveName}"? This can't be undone.`)) return;
    try {
      await api.deleteSave(saveName);
      refresh();
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div className="saves-screen">
      <h1>SimLLM</h1>
      {error && <div className="error">{error}</div>}

      <section className="new-save">
        <h2>New city</h2>
        <label>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="my-city" />
        </label>
        <label>
          Population target
          <input
            type="number"
            min={1}
            max={100}
            value={population}
            onChange={(e) => setPopulation(Number(e.target.value))}
          />
        </label>
        <label>
          World size (grid width/height)
          <input
            type="number"
            min={8}
            max={100}
            value={worldSize}
            onChange={(e) => setWorldSize(Number(e.target.value))}
          />
        </label>
        <button onClick={handleCreate}>Create</button>
      </section>

      <section className="save-list">
        <h2>Saves</h2>
        {saves.length === 0 && <p>No saves yet.</p>}
        <ul>
          {saves.map((s) => (
            <li key={s.name}>
              <span className="save-name">{s.name}</span>
              <span className="save-meta">
                gen {s.generation} &middot; tick {s.current_tick} &middot; pop {s.population} &middot; saved{" "}
                {formatRelativeTime(s.last_saved_at)}
              </span>
              <button onClick={() => handleLoad(s.name)}>Load</button>
              <button className="danger" onClick={() => handleDelete(s.name)}>
                Delete
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
