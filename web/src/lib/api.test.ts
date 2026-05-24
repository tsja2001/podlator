import { describe, it, expect, vi, beforeEach } from "vitest";
import { createTask, fetchBrief, fetchTask, fetchTasks, retryTask } from "./api";
import type { Task, TaskBrief } from "./task-types";

const mockTask: Task = {
  task_id: "test-1",
  source_url: "https://example.com",
  title: null,
  status: "pending",
  current_node: null,
  error_message: null,
  cost_usd: 0,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

function mockFetch(response: unknown, ok = true, status = 200): ReturnType<typeof vi.fn> {
  const fn = vi.fn().mockResolvedValue({ ok, status, json: () => Promise.resolve(response) });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("api client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchTasks returns task list", async () => {
    mockFetch([mockTask]);
    const tasks = await fetchTasks();
    expect(tasks).toHaveLength(1);
    expect(tasks[0].task_id).toBe("test-1");
  });

  it("fetchTask returns single task", async () => {
    mockFetch(mockTask);
    const task = await fetchTask("test-1");
    expect(task.task_id).toBe("test-1");
  });

  it("createTask sends POST with url", async () => {
    const fetch = mockFetch(mockTask);
    const task = await createTask("https://example.com");
    expect(task.task_id).toBe("test-1");
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/tasks"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("retryTask sends POST to retry endpoint", async () => {
    const completedTask = { ...mockTask, status: "pending" as const };
    mockFetch(completedTask);
    const task = await retryTask("test-1");
    expect(task.status).toBe("pending");
  });

  it("fetchBrief returns markdown brief", async () => {
    const brief: TaskBrief = {
      task_id: "test-1",
      title: "Test",
      markdown: "# Hello",
    };
    mockFetch(brief);
    const result = await fetchBrief("test-1");
    expect(result.markdown).toBe("# Hello");
  });

  it("throws on non-ok response", async () => {
    mockFetch({ detail: "Task not found" }, false, 404);
    await expect(fetchTask("bad-id")).rejects.toThrow("Task not found");
  });

  it("throws generic error when no detail in response", async () => {
    mockFetch({}, false, 500);
    await expect(fetchTask("bad-id")).rejects.toThrow("Request failed: 500");
  });
});
