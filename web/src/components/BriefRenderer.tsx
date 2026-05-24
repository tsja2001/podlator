import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  markdown: string;
}

export default function BriefRenderer({ markdown }: Props) {
  const [copyStatus, setCopyStatus] = useState<"idle" | "copied" | "error">("idle");

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(markdown);
      setCopyStatus("copied");
      setTimeout(() => setCopyStatus("idle"), 2000);
    } catch {
      setCopyStatus("error");
    }
  }

  function handleDownload() {
    const blob = new Blob([markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "brief.md";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <button
          onClick={handleCopy}
          style={{
            padding: "6px 14px",
            borderRadius: 6,
            border: "1px solid var(--border)",
            backgroundColor: "var(--code-bg)",
            cursor: "pointer",
            fontSize: 13,
            color: "var(--text-h)",
          }}
        >
          {copyStatus === "copied" ? "已复制" : copyStatus === "error" ? "复制失败" : "复制"}
        </button>
        <button
          onClick={handleDownload}
          style={{
            padding: "6px 14px",
            borderRadius: 6,
            border: "1px solid var(--border)",
            backgroundColor: "var(--code-bg)",
            cursor: "pointer",
            fontSize: 13,
            color: "var(--text-h)",
          }}
        >
          下载
        </button>
      </div>
      <div
        style={{
          lineHeight: 1.8,
          textAlign: "left",
        }}
      >
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>
      </div>
    </div>
  );
}
