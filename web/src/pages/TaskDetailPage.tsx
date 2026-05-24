import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchTask, retryTask } from "../lib/api";
import { useTaskLogs } from "../lib/useTaskLogs";
import NodeProgressBar from "../components/NodeProgressBar";
import LogViewer from "../components/LogViewer";

export default function TaskDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const {
    data: task,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["task", id],
    queryFn: () => fetchTask(id!),
    refetchInterval: 2000,
    enabled: !!id,
  });

  const { logs, connectionStatus, clearLogs } = useTaskLogs(
    task?.status === "running" || task?.status === "pending" ? id : undefined,
  );

  const retryMutation = useMutation({
    mutationFn: () => retryTask(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["task", id] });
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
  });

  if (isLoading) {
    return <div style={{ padding: 40, textAlign: "center", color: "var(--text)" }}>加载中...</div>;
  }

  if (isError || !task) {
    return (
      <div style={{ padding: 40, textAlign: "center" }}>
        <div style={{ color: "#ef4444", marginBottom: 8 }}>加载失败</div>
        <button onClick={() => refetch()} style={{ cursor: "pointer", color: "var(--accent)" }}>
          重试
        </button>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 800, margin: "20px auto", textAlign: "left" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>{task.title || "任务详情"}</h2>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {task.status === "completed" && (
            <button
              onClick={() => navigate(`/tasks/${id}/brief`)}
              style={{
                padding: "6px 14px",
                borderRadius: 6,
                border: "1px solid var(--accent)",
                backgroundColor: "var(--accent-bg)",
                color: "var(--accent)",
                cursor: "pointer",
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              查看简报
            </button>
          )}
          {task.status === "failed" && (
            <button
              onClick={() => retryMutation.mutate()}
              disabled={retryMutation.isPending}
              style={{
                padding: "6px 14px",
                borderRadius: 6,
                border: "1px solid var(--border)",
                backgroundColor: "var(--code-bg)",
                color: "var(--text-h)",
                cursor: "pointer",
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              {retryMutation.isPending ? "重试中..." : "重试"}
            </button>
          )}
        </div>
      </div>

      <div style={{ fontSize: 13, color: "var(--text)", marginBottom: 16 }}>
        <span>ID: {task.task_id.slice(0, 8)}</span>
        <span style={{ marginLeft: 16 }}>来源: {task.source_url}</span>
        <span style={{ marginLeft: 16 }}>费用: ${task.cost_usd.toFixed(4)}</span>
      </div>

      <NodeProgressBar task={task} />

      {task.error_message && (
        <div
          style={{
            padding: 12,
            borderRadius: 8,
            backgroundColor: "#ef444420",
            color: "#dc2626",
            fontSize: 13,
            marginBottom: 16,
          }}
        >
          {task.error_message}
        </div>
      )}

      <div style={{ marginBottom: 8, fontSize: 12, color: "var(--text)" }}>
        WebSocket: {connectionStatus} · 日志: {logs.length} 条
        <button
          onClick={clearLogs}
          style={{
            marginLeft: 12,
            cursor: "pointer",
            color: "var(--accent)",
            background: "none",
            border: "none",
            fontSize: 12,
          }}
        >
          清空
        </button>
      </div>

      <LogViewer logs={logs} />
    </div>
  );
}
