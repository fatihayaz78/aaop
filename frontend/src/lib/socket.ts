// Socket.IO client for real-time updates
// In production: import { io } from "socket.io-client";

export const SOCKET_URL = process.env.NEXT_PUBLIC_WS_URL || "http://localhost:8000";

export interface SocketEvents {
  subscribe: { app: string; tenant_id: string };
  unsubscribe: { app: string };
  agent_chat: { app: string; message: string; tenant_id: string };
  incident_update: { incident_id: string; status: string };
  alert_new: { alert_id: string; severity: string; title: string };
  agent_stream: { chunk: string; done: boolean };
  metric_update: { metric: string; value: number };
}

// Placeholder — will connect when socket.io-client is installed
export function createSocket() {
  return {
    url: SOCKET_URL,
    connected: false,
    emit: (_event: string, _data: unknown) => {},
    on: (_event: string, _handler: (data: unknown) => void) => {},
    disconnect: () => {},
  };
}
