// Native WebSocket client with auto-reconnect — replaces MockSocket
// No external dependencies (socket.io-client not needed)

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export interface SocketEvents {
  subscribe: { app: string; tenant_id: string };
  unsubscribe: { app: string };
  agent_chat: { app: string; message: string; tenant_id: string };
  incident_update: {
    incident_id: string;
    status: string;
    severity?: string;
    title?: string;
  };
  alert_new: {
    alert_id: string;
    severity: string;
    title: string;
    tenant_id?: string;
  };
  agent_stream: { chunk: string; done: boolean };
  metric_update: { metric: string; value: number };
}

class AppWebSocket {
  private ws: WebSocket | null = null;
  private listeners: Map<string, Set<(data: unknown) => void>> = new Map();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private url: string;
  private _connected = false;

  constructor(url: string) {
    this.url = url;
  }

  get connected(): boolean {
    return this._connected;
  }

  connect(): void {
    if (typeof window === "undefined") return; // SSR guard
    if (this.ws?.readyState === WebSocket.OPEN) return;
    try {
      this.ws = new WebSocket(this.url);
      this.ws.onopen = () => {
        this._connected = true;
      };
      this.ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          const event = msg.event as string;
          const data = msg.data;
          const handlers = this.listeners.get(event);
          handlers?.forEach((h) => h(data));
        } catch {
          /* ignore malformed messages */
        }
      };
      this.ws.onclose = () => {
        this._connected = false;
        this.reconnectTimer = setTimeout(() => this.connect(), 3000);
      };
      this.ws.onerror = () => {
        this.ws?.close();
      };
    } catch {
      /* connection failed, will retry on close */
    }
  }

  on(event: string, handler: (data: unknown) => void): void {
    if (!this.listeners.has(event)) this.listeners.set(event, new Set());
    this.listeners.get(event)!.add(handler);
  }

  off(event: string, handler?: (data: unknown) => void): void {
    if (!handler) {
      this.listeners.delete(event);
    } else {
      this.listeners.get(event)?.delete(handler);
    }
  }

  emit(event: string, data: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ event, data }));
    }
  }

  disconnect(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this._connected = false;
    this.ws?.close();
    this.ws = null;
  }
}

// Global socket instances — one per WS endpoint
export const opsSocket = new AppWebSocket(
  `${WS_BASE}/ws/ops/incidents?tenant_id=aaop_company`
);
export const alertSocket = new AppWebSocket(
  `${WS_BASE}/ws/alerts/stream?tenant_id=aaop_company`
);
export const viewerSocket = new AppWebSocket(
  `${WS_BASE}/ws/viewer/qoe?tenant_id=aaop_company`
);
export const liveSocket = new AppWebSocket(
  `${WS_BASE}/ws/live/events?tenant_id=aaop_company`
);

// ── Compatibility hooks (same API as before) ──

import { useEffect, useRef, useState, useCallback } from "react";

interface Incident {
  incident_id?: string;
  id?: string;
  severity?: string;
  title?: string;
  status?: string;
  [key: string]: unknown;
}

interface Alert {
  alert_id?: string;
  id?: string;
  severity?: string;
  title?: string;
  sentAt?: string;
  [key: string]: unknown;
}

export function useOpsWebSocket() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const connectedRef = useRef(false);

  useEffect(() => {
    opsSocket.connect();
    connectedRef.current = true;

    const handler = (data: unknown) => {
      const inc = data as Incident;
      setIncidents((prev) => [inc, ...prev].slice(0, 100));
    };

    opsSocket.on("incident_update", handler);

    return () => {
      opsSocket.off("incident_update", handler);
    };
  }, []);

  return { incidents, connected: connectedRef.current };
}

export function useAlertWebSocket() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [stormMode, setStormMode] = useState(false);
  const counterRef = useRef({ count: 0, windowStart: Date.now() });

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
    alertSocket.connect();

    const handler = (data: unknown) => {
      const alert = data as Alert;
      checkStorm();
      setAlerts((prev) => [alert, ...prev].slice(0, 100));
    };

    alertSocket.on("alert_new", handler);

    return () => {
      alertSocket.off("alert_new", handler);
    };
  }, [checkStorm]);

  return { alerts, stormMode, connected: true };
}

// Legacy compatibility — createSocket returns a mock-like wrapper
export function createSocket() {
  return {
    url: WS_BASE,
    connected: false,
    handlers: new Map<string, ((data: unknown) => void)[]>(),
    emit: (_event: string, _data: unknown) => {},
    on: (_event: string, _handler: (data: unknown) => void) => {},
    off: (_event: string, _handler?: (data: unknown) => void) => {},
    disconnect: () => {},
  };
}
