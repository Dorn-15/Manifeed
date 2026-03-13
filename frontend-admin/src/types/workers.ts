export type WorkerTypeKind = "rss_scrapper" | "source_embedding";

export type WorkerInstanceRead = {
  name: string;
  processing_tasks: number;
  idle_ms: number;
  connected: boolean;
  active: boolean;
  connection_state: string | null;
  desired_state: string | null;
  current_task_id: number | null;
  current_execution_id: number | null;
  current_task_label: string | null;
  current_feed_id: number | null;
  current_feed_url: string | null;
  last_error: string | null;
};

export type WorkerTypeOverviewRead = {
  worker_type: WorkerTypeKind;
  queue_name: string;
  queue_length: number;
  queued_tasks: number;
  processing_tasks: number;
  worker_count: number;
  connected: boolean;
  active: boolean;
  workers: WorkerInstanceRead[];
};

export type WorkersOverviewRead = {
  generated_at: string;
  connected_idle_threshold_ms: number;
  active_idle_threshold_ms: number;
  items: WorkerTypeOverviewRead[];
};
