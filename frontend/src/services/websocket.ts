import type { WSMessage } from "../types";

type WSCallback = (message: WSMessage) => void;

export class SessionWebSocket {
  private ws: WebSocket | null = null;
  private listeners: WSCallback[] = [];
  private sessionId: string;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(sessionId: string) {
    this.sessionId = sessionId;
  }

  connect(): void {
    const baseUrl = import.meta.env.VITE_WS_URL || "ws://localhost:8000";
    this.ws = new WebSocket(`${baseUrl}/ws/sessions/${this.sessionId}`);

    this.ws.onmessage = (event) => {
      try {
        const data: WSMessage = JSON.parse(event.data);
        this.listeners.forEach((cb) => cb(data));
      } catch {
        // ignore malformed messages
      }
    };

    this.ws.onclose = () => {
      this.reconnectTimer = setTimeout(() => this.connect(), 3000);
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  onMessage(callback: WSCallback): () => void {
    this.listeners.push(callback);
    return () => {
      this.listeners = this.listeners.filter((cb) => cb !== callback);
    };
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
    this.listeners = [];
  }
}
