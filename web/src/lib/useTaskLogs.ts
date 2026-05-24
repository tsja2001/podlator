import { useRef, useState, useEffect, useCallback } from "react";
import type { LogEvent } from "./task-types";

const WS_BASE =
  import.meta.env.VITE_WS_BASE_URL ?? "ws://localhost:8000";

const MAX_LOGS = 1000;

export type ConnectionStatus = "connecting" | "connected" | "disconnected" | "error";

export function useTaskLogs(taskId: string | undefined) {
  const [logs, setLogs] = useState<LogEvent[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("disconnected");
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const clearLogs = useCallback(() => setLogs([]), []);

  useEffect(() => {
    if (!taskId) return;

    let cancelled = false;

    function connect() {
      if (cancelled) return;

      const ws = new WebSocket(`${WS_BASE}/ws/tasks/${taskId}/logs`);
      wsRef.current = ws;
      setConnectionStatus("connecting");

      ws.onopen = () => {
        if (!cancelled) setConnectionStatus("connected");
      };

      ws.onmessage = (event) => {
        if (cancelled) return;
        try {
          const parsed = JSON.parse(event.data) as LogEvent;
          setLogs((prev) => {
            const next = [...prev, parsed];
            if (next.length > MAX_LOGS) {
              return next.slice(next.length - MAX_LOGS);
            }
            return next;
          });
        } catch {
          // 忽略解析失败的消息
        }
      };

      ws.onclose = () => {
        if (!cancelled) {
          setConnectionStatus("disconnected");
          reconnectTimer.current = setTimeout(connect, 2000);
        }
      };

      ws.onerror = () => {
        setConnectionStatus("error");
      };
    }

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
      }
      wsRef.current?.close();
    };
  }, [taskId]);

  return { logs, connectionStatus, clearLogs };
}
