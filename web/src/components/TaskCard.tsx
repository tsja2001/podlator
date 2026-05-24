import { Link } from "react-router-dom";
import type { Task } from "../lib/task-types";

const STATUS_COLORS: Record<string, string> = {
  pending: "#6b7280",
  running: "#3b82f6",
  completed: "#22c55e",
  failed: "#ef4444",
};

function formatCost(cost: number): string {
  if (cost === 0) return "-";
  return `$${cost.toFixed(4)}`;
}

export default function TaskCard({ task }: { task: Task }) {
  return (
    <Link
      to={`/tasks/${task.task_id}`}
      style={{
        display: "block",
        padding: "12px 16px",
        border: "1px solid var(--border)",
        borderRadius: 8,
        marginBottom: 8,
        textDecoration: "none",
        color: "inherit",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ fontWeight: 600, color: "var(--text-h)" }}>
            {task.title || task.source_url}
          </div>
          <div style={{ fontSize: 13, color: "var(--text)", marginTop: 4 }}>
            {task.task_id.slice(0, 8)} · {new Date(task.created_at).toLocaleString()}
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <span
            style={{
              display: "inline-block",
              padding: "2px 8px",
              borderRadius: 4,
              fontSize: 12,
              fontWeight: 600,
              color: STATUS_COLORS[task.status] ?? "#6b7280",
              backgroundColor: `${STATUS_COLORS[task.status] ?? "#6b7280"}15`,
            }}
          >
            {task.status}
          </span>
          <div style={{ fontSize: 12, color: "var(--text)", marginTop: 4 }}>
            {task.current_node || "-"} · {formatCost(task.cost_usd)}
          </div>
        </div>
      </div>
    </Link>
  );
}
