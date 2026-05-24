export type TaskStatus = "pending" | "running" | "completed" | "failed";

export interface Task {
  task_id: string;
  source_url: string;
  title: string | null;
  status: TaskStatus;
  current_node: string | null;
  error_message: string | null;
  cost_usd: number;
  created_at: string;
  updated_at: string;
}

export interface TaskBrief {
  task_id: string;
  title: string | null;
  markdown: string;
}

export interface LogEvent {
  timestamp?: string;
  level?: "debug" | "info" | "warning" | "error" | "critical";
  logger?: string;
  event: string;
  task_id: string;
  node?: string;
  message?: string;
  duration_ms?: number;
  cost_usd?: number;
  error_msg?: string;
  [key: string]: unknown;
}
