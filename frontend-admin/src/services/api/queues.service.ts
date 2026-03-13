import { apiRequest } from "@/services/api/client";
import type { QueueOverviewRead, QueuePurgeRead } from "@/types/queues";

export async function getQueuesOverview(): Promise<QueueOverviewRead> {
  return apiRequest<QueueOverviewRead>("/internal/workers/queues/overview");
}

export async function purgeTaskQueue(queueName: string): Promise<QueuePurgeRead> {
  return apiRequest<QueuePurgeRead>(`/internal/workers/queues/${encodeURIComponent(queueName)}/purge`, {
    method: "POST",
  });
}
