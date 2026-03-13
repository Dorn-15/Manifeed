import { apiRequest } from "@/services/api/client";
import type { WorkersOverviewRead } from "@/types/workers";

export async function getWorkersOverview(): Promise<WorkersOverviewRead> {
  return apiRequest<WorkersOverviewRead>("/internal/workers/overview");
}
