import type { Task, TaskBrief, TaskStatus } from "./task-types";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function fetchTasks(status?: TaskStatus): Promise<Task[]> {
  const query = status ? `?status=${status}` : "";
  return request<Task[]>(`/tasks${query}`);
}

export async function fetchTask(taskId: string): Promise<Task> {
  return request<Task>(`/tasks/${taskId}`);
}

export async function createTask(url: string): Promise<Task> {
  return request<Task>("/tasks", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export async function retryTask(taskId: string): Promise<Task> {
  return request<Task>(`/tasks/${taskId}/retry`, { method: "POST" });
}

export async function fetchBrief(taskId: string): Promise<TaskBrief> {
  return request<TaskBrief>(`/tasks/${taskId}/brief`);
}
