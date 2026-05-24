import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import LogViewer from "./LogViewer";
import type { LogEvent } from "../lib/task-types";

const logs: LogEvent[] = [
  { event: "node_started", task_id: "t1", level: "info", node: "fetch_metadata" },
  { event: "node_completed", task_id: "t1", level: "info", node: "fetch_metadata", duration_ms: 100 },
  { event: "node_failed", task_id: "t1", level: "error", node: "transcribe", error_msg: "test" },
];

describe("LogViewer", () => {
  it("renders log events", () => {
    render(<LogViewer logs={logs} />);
    expect(screen.getByText("node_started")).toBeDefined();
    expect(screen.getByText("node_failed")).toBeDefined();
  });

  it("shows empty state when no logs", () => {
    render(<LogViewer logs={[]} />);
    expect(screen.getByText("暂无日志")).toBeDefined();
  });
});
