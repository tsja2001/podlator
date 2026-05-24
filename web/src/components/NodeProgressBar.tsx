import type { Task } from "../lib/task-types";

const PIPELINE_NODES = [
  "fetch_metadata",
  "download_audio",
  "transcribe",
  "diarize",
  "chapter_split",
  "summarize_chapters",
  "polish_final",
  "export_markdown",
] as const;

const NODE_LABELS: Record<string, string> = {
  fetch_metadata: "获取信息",
  download_audio: "下载音频",
  transcribe: "转写",
  diarize: "说话人分离",
  chapter_split: "章节切分",
  summarize_chapters: "章节摘要",
  polish_final: "全局润色",
  export_markdown: "导出",
};

type NodeState = "done" | "running" | "pending" | "failed";

function getNodeState(node: string, task: Task): NodeState {
  if (task.status === "failed") {
    if (node === task.current_node) return "failed";
  }
  if (task.status === "completed") return "done";

  const currentIdx = PIPELINE_NODES.indexOf(
    (task.current_node as (typeof PIPELINE_NODES)[number]) ?? "",
  );
  const nodeIdx = PIPELINE_NODES.indexOf(node as (typeof PIPELINE_NODES)[number]);

  if (nodeIdx < currentIdx) return "done";
  if (nodeIdx === currentIdx) return "running";
  return "pending";
}

const STATE_COLORS: Record<NodeState, { bg: string; border: string; text: string }> = {
  done: { bg: "#22c55e20", border: "#22c55e", text: "#16a34a" },
  running: { bg: "#3b82f620", border: "#3b82f6", text: "#2563eb" },
  pending: { bg: "#6b728015", border: "#6b7280", text: "#6b7280" },
  failed: { bg: "#ef444420", border: "#ef4444", text: "#dc2626" },
};

export default function NodeProgressBar({ task }: { task: Task }) {
  return (
    <div
      style={{
        display: "flex",
        gap: 8,
        flexWrap: "wrap",
        padding: "12px 0",
      }}
    >
      {PIPELINE_NODES.map((node) => {
        const state = getNodeState(node, task);
        const colors = STATE_COLORS[state];
        return (
          <div
            key={node}
            style={{
              flex: "1 1 100px",
              minWidth: 100,
              padding: "6px 8px",
              borderRadius: 6,
              border: `1px solid ${colors.border}`,
              backgroundColor: colors.bg,
              textAlign: "center",
              fontSize: 11,
              fontWeight: 600,
              color: colors.text,
            }}
          >
            {NODE_LABELS[node] ?? node}
          </div>
        );
      })}
    </div>
  );
}
