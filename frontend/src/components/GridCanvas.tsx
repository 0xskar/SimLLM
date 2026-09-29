import { useEffect, useRef } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";

const CELL_SIZE = 20;

const TILE_COLORS: Record<string, string> = {
  empty: "#dcead0",
  road: "#b7b7b7",
  house: "#e8c07d",
  workplace: "#7dabe8",
  resource: "#8fce8f",
  under_construction: "#cfa5e0",
};

export function GridCanvas() {
  const world = useStore((s) => s.world);
  const agents = useStore((s) => s.agents);
  const selectedAgentId = useStore((s) => s.selectedAgentId);
  const conversationFlashes = useStore((s) => s.conversationFlashes);
  const setSelectedAgentId = useStore((s) => s.setSelectedAgentId);
  const setSelectedAgentDetail = useStore((s) => s.setSelectedAgentDetail);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !world) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    canvas.width = world.width * CELL_SIZE;
    canvas.height = world.height * CELL_SIZE;

    ctx.fillStyle = TILE_COLORS.empty;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    for (const tile of world.tiles) {
      ctx.fillStyle = TILE_COLORS[tile.tile_type] ?? "#fff";
      ctx.fillRect(tile.x * CELL_SIZE, tile.y * CELL_SIZE, CELL_SIZE, CELL_SIZE);
    }

    ctx.strokeStyle = "rgba(0,0,0,0.08)";
    for (let x = 0; x <= world.width; x++) {
      ctx.beginPath();
      ctx.moveTo(x * CELL_SIZE, 0);
      ctx.lineTo(x * CELL_SIZE, canvas.height);
      ctx.stroke();
    }
    for (let y = 0; y <= world.height; y++) {
      ctx.beginPath();
      ctx.moveTo(0, y * CELL_SIZE);
      ctx.lineTo(canvas.width, y * CELL_SIZE);
      ctx.stroke();
    }

    ctx.font = `${CELL_SIZE - 4}px sans-serif`;
    ctx.fillStyle = "#333";
    for (const b of world.buildings) {
      const icon = b.type === "house" ? "\u{1F3E0}" : b.type === "workplace" ? "\u{1F3ED}" : "\u{1F6A7}";
      ctx.fillText(icon, b.x * CELL_SIZE + 1, b.y * CELL_SIZE + CELL_SIZE - 3);

      if (b.status === "under_construction" && b.construction_total_ticks > 0) {
        const frac = Math.min(1, b.construction_progress / b.construction_total_ticks);
        const barY = b.y * CELL_SIZE + CELL_SIZE - 3;
        ctx.fillStyle = "rgba(0,0,0,0.35)";
        ctx.fillRect(b.x * CELL_SIZE + 1, barY, CELL_SIZE - 2, 3);
        ctx.fillStyle = "#8fce8f";
        ctx.fillRect(b.x * CELL_SIZE + 1, barY, (CELL_SIZE - 2) * frac, 3);
        ctx.fillStyle = "#333";
      }
    }

    for (const a of agents) {
      if (!a.is_alive) {
        ctx.save();
        ctx.globalAlpha = 0.45;
        ctx.font = `${CELL_SIZE - 4}px sans-serif`;
        ctx.fillText("\u{1FAA6}", a.x * CELL_SIZE + 1, a.y * CELL_SIZE + CELL_SIZE - 3);
        ctx.restore();
        continue;
      }

      if (a.id === selectedAgentId) {
        ctx.strokeStyle = "#ffd24a";
        ctx.lineWidth = 2;
        ctx.strokeRect(a.x * CELL_SIZE + 1, a.y * CELL_SIZE + 1, CELL_SIZE - 2, CELL_SIZE - 2);
      }

      ctx.font = `${CELL_SIZE - 2}px sans-serif`;
      ctx.fillText(a.emoji, a.x * CELL_SIZE + 1, a.y * CELL_SIZE + CELL_SIZE - 2);
    }

    if (conversationFlashes.length > 0) {
      ctx.font = `${CELL_SIZE - 6}px sans-serif`;
      for (const flash of conversationFlashes) {
        for (const id of flash.participantIds) {
          const a = agents.find((x) => x.id === id);
          if (!a) continue;
          ctx.fillText("\u{1F4AC}", a.x * CELL_SIZE + CELL_SIZE / 2, a.y * CELL_SIZE - 2);
        }
      }
    }
  }, [world, agents, selectedAgentId, conversationFlashes]);

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const cellX = Math.floor((e.clientX - rect.left) / CELL_SIZE);
    const cellY = Math.floor((e.clientY - rect.top) / CELL_SIZE);
    const agent = agents.find((a) => a.x === cellX && a.y === cellY);
    if (!agent) return;
    setSelectedAgentId(agent.id);
    api.getAgent(agent.id).then(setSelectedAgentDetail);
  };

  if (!world) return <div className="grid-canvas-placeholder">Loading world...</div>;

  return (
    <div className="grid-canvas-viewport">
      <canvas ref={canvasRef} className="grid-canvas" onClick={handleClick} />
    </div>
  );
}
