import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import TaskCard from "./TaskCard";
import type { Task } from "../lib/task-types";

const task: Task = {
  task_id: "test-1234-abcd",
  source_url: "https://example.com/video",
  title: "Test Episode",
  status: "running",
  current_node: "transcribe",
  error_message: null,
  cost_usd: 0.001,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:05:00Z",
};

describe("TaskCard", () => {
  it("renders task title and status", () => {
    render(
      <MemoryRouter>
        <TaskCard task={task} />
      </MemoryRouter>,
    );
    expect(screen.getByText("Test Episode")).toBeDefined();
    expect(screen.getByText("running")).toBeDefined();
  });

  it("renders url when title is null", () => {
    const noTitleTask = { ...task, title: null };
    render(
      <MemoryRouter>
        <TaskCard task={noTitleTask} />
      </MemoryRouter>,
    );
    expect(screen.getByText("https://example.com/video")).toBeDefined();
  });
});
