import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { OllamaModelInfo } from "../api/client";
import { SETTINGS_SCHEMA, getPath, setPath } from "../settingsSchema";

export function SettingsPanel() {
  const [open, setOpen] = useState(false);
  const [settings, setSettings] = useState<Record<string, unknown> | null>(null);
  const [models, setModels] = useState<OllamaModelInfo[] | null>(null);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    api.getSettings().then(setSettings);
    api
      .listModels()
      .then((list) => {
        setModels(list);
        setModelsError(null);
      })
      .catch((e) => setModelsError(String(e)));
  }, [open]);

  if (!open) {
    return (
      <button className="settings-toggle" onClick={() => setOpen(true)}>
        Settings
      </button>
    );
  }

  if (!settings) return <div className="settings-panel">Loading settings...</div>;

  const handleFieldChange = (path: string[], value: number | string) => {
    setSettings((current) => (current ? setPath(current, path, value) : current));
    setSaved(false);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      // Send the whole object, not a diff: the backend merges overrides
      // shallowly, so a partial nested object (e.g. just one needs_decay_per_tick
      // key) would silently wipe out its siblings.
      const updated = await api.putSettings(settings);
      setSettings(updated);
      setSaved(true);
    } finally {
      setSaving(false);
    }
  };

  const currentModel = settings.ollama_model as string;

  return (
    <div className="settings-panel">
      <div className="settings-header">
        <h3>Settings</h3>
        <button onClick={() => setOpen(false)}>Close</button>
      </div>

      <details open>
        <summary>AI Model</summary>
        <label>
          Ollama model
          {modelsError && <p className="error">Couldn't reach Ollama: {modelsError}</p>}
          {!modelsError && !models && <p className="muted">Loading installed models...</p>}
          {!modelsError && models && models.length === 0 && (
            <p className="muted">No models found. Pull one with `ollama pull &lt;model&gt;`.</p>
          )}
          {!modelsError && models && models.length > 0 && (
            <select
              value={currentModel}
              onChange={(e) => handleFieldChange(["ollama_model"], e.target.value)}
            >
              {!models.some((m) => m.name === currentModel) && (
                <option value={currentModel}>{currentModel} (not installed)</option>
              )}
              {models.map((m) => (
                <option key={m.name} value={m.name}>
                  {m.name}
                  {m.parameter_size ? ` (${m.parameter_size})` : ""}
                  {m.recommended ? " — recommended" : ""}
                </option>
              ))}
            </select>
          )}
        </label>
      </details>

      {SETTINGS_SCHEMA.map((section) => (
        <details key={section.title}>
          <summary>{section.title}</summary>
          {section.fields.map((field) => {
            const value = getPath(settings, field.path);
            const key = field.path.join(".");
            const isText = field.type === "text";
            return (
              <label key={key}>
                {field.label}
                <input
                  type={isText ? "text" : "number"}
                  step={isText ? undefined : field.step ?? 1}
                  min={isText ? undefined : field.min}
                  value={value as string | number}
                  onChange={(e) =>
                    handleFieldChange(field.path, isText ? e.target.value : Number(e.target.value))
                  }
                />
              </label>
            );
          })}
        </details>
      ))}

      <div className="settings-actions">
        <button onClick={handleSave} disabled={saving}>
          {saving ? "Saving..." : "Save"}
        </button>
        {saved && <span className="saved-indicator">Saved</span>}
      </div>
    </div>
  );
}
