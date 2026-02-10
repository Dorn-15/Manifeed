import { apiRequest } from "@/services/api/client";
import type { HealthRead } from "@/types/health";

export async function getHealthStatus(): Promise<HealthRead> {
  return apiRequest<HealthRead>("/health/");
}
