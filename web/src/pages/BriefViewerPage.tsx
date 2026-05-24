import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchBrief } from "../lib/api";
import BriefRenderer from "../components/BriefRenderer";

export default function BriefViewerPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const {
    data: brief,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["brief", id],
    queryFn: () => fetchBrief(id!),
    enabled: !!id,
  });

  return (
    <div style={{ maxWidth: 800, margin: "20px auto", textAlign: "left" }}>
      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        <button
          onClick={() => navigate(`/tasks/${id}`)}
          style={{
            padding: "4px 12px",
            borderRadius: 6,
            border: "1px solid var(--border)",
            backgroundColor: "var(--code-bg)",
            cursor: "pointer",
            fontSize: 13,
            color: "var(--text-h)",
          }}
        >
          ← 返回任务
        </button>
        <button
          onClick={() => navigate("/queue")}
          style={{
            padding: "4px 12px",
            borderRadius: 6,
            border: "1px solid var(--border)",
            backgroundColor: "var(--code-bg)",
            cursor: "pointer",
            fontSize: 13,
            color: "var(--text-h)",
          }}
        >
          队列
        </button>
      </div>

      {isLoading && <div style={{ color: "var(--text)", textAlign: "center", padding: 40 }}>加载中...</div>}

      {isError && (
        <div style={{ color: "#ef4444", textAlign: "center", padding: 40 }}>
          {(error as Error).message}
        </div>
      )}

      {brief && (
        <>
          <h2>{brief.title || "简报"}</h2>
          <BriefRenderer markdown={brief.markdown} />
        </>
      )}
    </div>
  );
}
