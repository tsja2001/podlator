import { useState, useRef, useEffect } from "react";
import type { LogEvent } from "../lib/task-types";

interface Props {
  logs: LogEvent[];
}

const LEVEL_COLORS: Record<string, string> = {
  debug: "#94a3b8",
  info: "#22c55e",
  warning: "#f59e0b",
  error: "#ef4444",
  critical: "#dc2626",
};

export default function LogViewer({ logs }: Props) {
  const [levelFilter, setLevelFilter] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [autoScroll, setAutoScroll] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

  const filtered = logs.filter((l) => {
    if (levelFilter !== "all" && l.level !== levelFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      return (
        l.event?.toLowerCase().includes(q) ||
        (l.message ?? "").toLowerCase().includes(q) ||
        (l.error_msg ?? "").toLowerCase().includes(q)
      );
    }
    return true;
  });

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [filtered.length, autoScroll]);

  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
        <select
          value={levelFilter}
          onChange={(e) => setLevelFilter(e.target.value)}
          style={{ padding: "4px 8px", borderRadius: 4, border: "1px solid var(--border)" }}
        >
          <option value="all">All levels</option>
          <option value="debug">DEBUG</option>
          <option value="info">INFO</option>
          <option value="warning">WARNING</option>
          <option value="error">ERROR</option>
          <option value="critical">CRITICAL</option>
        </select>
        <input
          type="text"
          placeholder="搜索..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            padding: "4px 8px",
            borderRadius: 4,
            border: "1px solid var(--border)",
            flex: 1,
            minWidth: 120,
          }}
        />
        <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12 }}>
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
          />
          自动滚动
        </label>
      </div>
      <div
        ref={containerRef}
        style={{
          maxHeight: 400,
          overflowY: "auto",
          fontFamily: "var(--mono)",
          fontSize: 12,
          border: "1px solid var(--border)",
          borderRadius: 8,
          backgroundColor: "var(--code-bg)",
        }}
      >
        {filtered.length === 0 && (
          <div style={{ padding: 16, color: "var(--text)", textAlign: "center" }}>
            暂无日志
          </div>
        )}
        {filtered.map((log, i) => (
          <div
            key={i}
            style={{
              padding: "4px 10px",
              borderBottom: "1px solid var(--border)",
              lineHeight: 1.6,
            }}
          >
            <span style={{ color: "var(--text)" }}>
              {log.timestamp?.slice(11, 19) ?? "-"}
            </span>{" "}
            <span
              style={{
                color: LEVEL_COLORS[log.level ?? "info"] ?? "#94a3b8",
                fontWeight: 600,
              }}
            >
              {log.level?.toUpperCase() ?? "INFO"}
            </span>{" "}
            <span style={{ color: "#3b82f6" }}>{log.node ?? "-"}</span>{" "}
            <span style={{ color: "var(--text-h)", fontWeight: 500 }}>
              {log.event}
            </span>{" "}
            {log.duration_ms != null && (
              <span style={{ color: "var(--text)" }}>{log.duration_ms}ms</span>
            )}
            {log.cost_usd != null && (
              <span style={{ color: "var(--text)" }}>${log.cost_usd}</span>
            )}
            {log.error_msg && (
              <span style={{ color: "#ef4444" }}>{log.error_msg}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
