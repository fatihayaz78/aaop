// Socket.IO client for real-time updates
// Uses a mock implementation — Socket.IO client installed separately when ready

export const SOCKET_URL = process.env.NEXT_PUBLIC_WS_URL || "http://localhost:8000";

export interface SocketEvents {
  subscribe: { app: string; tenant_id: string };
  unsubscribe: { app: string };
  agent_chat: { app: string; message: string; tenant_id: string };
  incident_update: { incident_id: string; status: string; severity?: string; title?: string };
  alert_new: { alert_id: string; severity: string; title: string; tenant_id?: string };
  agent_stream: { chunk: string; done: boolean };
  metric_update: { metric: string; value: number };
}

interface MockSocket {
  url: string;
  connected: boolean;
  handlers: Map<string, ((data: unknown) => void)[]>;
  emit: (event: string, data: unknown) => void;
  on: (event: string, handler: (data: unknown) => void) => void;
  off: (event: string, handler?: (data: unknown) => void) => void;
  disconnect: () => void;
}

export function createSocket(): MockSocket {
  const handlers = new Map<string, ((data: unknown) => void)[]>();
  return {
    url: SOCKET_URL,
    connected: false,
    handlers,
    emit: (_event: string, _data: unknown) => {},
    on: (event: string, handler: (data: unknown) => void) => {
      const list = handlers.get(event) ?? [];
      list.push(handler);
      handlers.set(event, list);
    },
    off: (event: string, handler?: (data: unknown) => void) => {
      if (!handler) {
        handlers.delete(event);
      } else {
        const list = handlers.get(event) ?? [];
        handlers.set(event, list.filter((h) => h !== handler));
      }
    },
    disconnect: () => {},
  };
}

// ── WebSocket Hooks ──

import { useEffect, useRef, useState, useCallback } from "react";
import type { Incident, Alert } from "@/types";

export function useOpsWebSocket() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const socketRef = useRef<MockSocket | null>(null);

  useEffect(() => {
    const socket = createSocket();
    socketRef.current = socket;
    socket.connected = true;

    socket.on("incident_update", (data) => {
      const inc = data as Incident;
      setIncidents((prev) => {
        const next = [inc, ...prev].slice(0, 100);
        return next;
      });
    });

    socket.emit("subscribe", { app: "ops_center", tenant_id: "bein_sports" });

    return () => {
      socket.emit("unsubscribe", { app: "ops_center" });
      socket.disconnect();
    };
  }, []);

  return { incidents, connected: socketRef.current?.connected ?? false };
}

export function useAlertWebSocket() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [stormMode, setStormMode] = useState(false);
  const counterRef = useRef({ count: 0, windowStart: Date.now() });
  const socketRef = useRef<MockSocket | null>(null);

  const checkStorm = useCallback(() => {
    const now = Date.now();
    const elapsed = now - counterRef.current.windowStart;
    if (elapsed > 60_000) {
      counterRef.current = { count: 1, windowStart: now };
      setStormMode(false);
    } else {
      counterRef.current.count += 1;
      if (counterRef.current.count > 20) {
        setStormMode(true);
      }
    }
  }, []);

  useEffect(() => {
    const socket = createSocket();
    socketRef.current = socket;
    socket.connected = true;

    socket.on("alert_new", (data) => {
      const alert = data as Alert;
      checkStorm();
      setAlerts((prev) => {
        const next = [alert, ...prev].slice(0, 100);
        return next;
      });
    });

    socket.emit("subscribe", { app: "alert_center", tenant_id: "bein_sports" });

    return () => {
      socket.emit("unsubscribe", { app: "alert_center" });
      socket.disconnect();
    };
  }, [checkStorm]);

  return { alerts, stormMode, connected: socketRef.current?.connected ?? false };
}
