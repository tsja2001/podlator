import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchTasks } from "../lib/api";
import type { TaskStatus } from "../lib/task-types";
import TaskCard from "../components/TaskCard";

const FILTERS: { label: string; value: TaskStatus | "all" }[] = [
  { label: "全部", value: "all" },
  { label: "等待中", value: "pending" },
  { label: "运行中", value: "running" },
  { label: "已完成", value: "completed" },
  { label: "失败", value: "failed" },
];

export default function QueuePage() {
  const [statusFilter, setStatusFilter] = useState<TaskStatus | "all">("all");

  const { data: tasks, isLoading, isError, refetch } = useQuery({
    queryKey: ["tasks", statusFilter],
    queryFn: () => fetchTasks(statusFilter === "all" ? undefined : statusFilter),
    refetchInterval: 3000,
  });

  return (
    <div style={{ maxWidth: 700, margin: "20px auto", textAlign: "left" }}>
      <h2>任务队列</h2>
      <div style={{ display: "flex", gap: 6, marginBottom: 16, flexWrap: "wrap" }}>
        {FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setStatusFilter(f.value)}
            style={{
              padding: "4px 12px",
              borderRadius: 6,
              border: "1px solid var(--border)",
              backgroundColor: statusFilter === f.value ? "var(--accent-bg)" : "var(--bg)",
              color: statusFilter === f.value ? "var(--accent)" : "var(--text)",
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

      {isLoading && <div style={{ color: "var(--text)" }}>加载中...</div>}
      {isError && (
        <div>
          <div style={{ color: "#ef4444", marginBottom: 8 }}>加载失败</div>
          <button onClick={() => refetch()} style={{ cursor: "pointer", color: "var(--accent)" }}>
            重试
          </button>
        </div>
      )}
      {tasks && tasks.length === 0 && (
        <div style={{ color: "var(--text)", textAlign: "center", padding: 40 }}>暂无任务</div>
      )}
      {tasks?.map((task) => (
        <TaskCard key={task.task_id} task={task} />
      ))}
    </div>
  );
}
