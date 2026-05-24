import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { createTask } from "../lib/api";

export default function SubmitPage() {
  const [url, setUrl] = useState("");
  const navigate = useNavigate();

  const mutation = useMutation({
    mutationFn: createTask,
    onSuccess: (task) => {
      navigate(`/tasks/${task.task_id}`);
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) {
      return;
    }
    try {
      new URL(trimmed);
    } catch {
      return;
    }
    mutation.mutate(trimmed);
  }

  return (
    <div style={{ maxWidth: 600, margin: "40px auto", textAlign: "left" }}>
      <h2 style={{ textAlign: "center" }}>提交播客/视频 URL</h2>
      <form onSubmit={handleSubmit} style={{ display: "flex", gap: 8, marginTop: 16 }}>
        <input
          type="url"
          placeholder="https://www.youtube.com/watch?v=..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          required
          style={{
            flex: 1,
            padding: "10px 14px",
            borderRadius: 8,
            border: "1px solid var(--border)",
            fontSize: 15,
            backgroundColor: "var(--bg)",
            color: "var(--text-h)",
          }}
        />
        <button
          type="submit"
          disabled={mutation.isPending}
          style={{
            padding: "10px 24px",
            borderRadius: 8,
            border: "none",
            backgroundColor: "var(--accent)",
            color: "#fff",
            fontSize: 15,
            fontWeight: 600,
            cursor: "pointer",
            whiteSpace: "nowrap",
          }}
        >
          {mutation.isPending ? "提交中..." : "提交"}
        </button>
      </form>
      {mutation.isError && (
        <div style={{ marginTop: 12, color: "#ef4444", fontSize: 13 }}>
          {(mutation.error as Error).message}
        </div>
      )}
      {!url.trim() && (
        <div style={{ marginTop: 12, color: "var(--text)", fontSize: 13 }}>
          支持 YouTube、播客 RSS、或任意视频链接
        </div>
      )}
    </div>
  );
}
