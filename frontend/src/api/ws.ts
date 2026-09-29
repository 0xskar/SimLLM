import type { WSEvent } from "../types";

const RECONNECT_DELAYS_MS = [500, 1000, 2000, 5000, 10000];

export interface WSHandle {
  close: () => void;
}

/**
 * Auto-reconnecting WS client. The server assigns no session identity to a
 * socket, so a fresh connection after a drop is indistinguishable from the
 * first one — onOpen fires again each time, and the caller (App.tsx) treats
 * every onOpen as a cue to re-fetch full state, since any events broadcast
 * during the gap were lost.
 */
export function connectWebSocket(
  onEvent: (event: WSEvent) => void,
  onOpen?: () => void,
  onClose?: () => void
): WSHandle {
  let socket: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let attempt = 0;
  let closedByCaller = false;

  const connect = () => {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const url = `${protocol}://${window.location.host}/ws`;
    socket = new WebSocket(url);

    socket.onopen = () => {
      attempt = 0;
      onOpen?.();
    };
    socket.onclose = () => {
      onClose?.();
      if (closedByCaller) return;
      const delay = RECONNECT_DELAYS_MS[Math.min(attempt, RECONNECT_DELAYS_MS.length - 1)];
      attempt += 1;
      reconnectTimer = setTimeout(connect, delay);
    };
    socket.onerror = () => socket?.close();
    socket.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data) as WSEvent;
        onEvent(data);
      } catch (err) {
        console.error("Failed to parse WS message", err);
      }
    };
  };

  connect();

  return {
    close: () => {
      closedByCaller = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socket?.close();
    },
  };
}
