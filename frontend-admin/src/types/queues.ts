export type TaskLeaseRead = {
  task_id: string;
  worker_name: string | null;
  idle_ms: number;
  attempts: number;
};

export type QueueWorkerRead = {
  name: string;
  processing_tasks: number;
  idle_ms: number;
  connected: boolean;
  active: boolean;
};

export type TaskQueueOverviewRead = {
  queue_name: string;
  purpose: string;
  worker_type: string;
  queue_exists: boolean;
  queue_length: number;
  queued_tasks: number;
  processing_tasks: number;
  last_task_id: string | null;
  connected_workers: number;
  active_workers: number;
  blocked: boolean;
  blocked_reasons: string[];
  error: string | null;
  workers: QueueWorkerRead[];
  leased_tasks: TaskLeaseRead[];
};

export type QueueOverviewRead = {
  generated_at: string;
  connected_idle_threshold_ms: number;
  active_idle_threshold_ms: number;
  stuck_pending_threshold_ms: number;
  queue_backend_available: boolean;
  queue_backend_error: string | null;
  blocked_queues: number;
  items: TaskQueueOverviewRead[];
};

export type QueuePurgeRead = {
  queue_name: string;
  deleted: boolean;
  purged_at: string;
};
