import { apiRequest } from "@/services/api/client";
import type {
  RssSourceDetail,
  RssSourceIngestRead,
  RssSourcePageRead,
} from "@/types/sources";

type ListRssSourcesParams = {
  limit?: number;
  offset?: number;
  feedId?: number | null;
  companyId?: number | null;
};

function buildListRssSourcesPath(params?: ListRssSourcesParams): string {
  const limit = params?.limit ?? 50;
  const offset = params?.offset ?? 0;
  const feedId = params?.feedId;
  const companyId = params?.companyId;

  let path = "/sources/";
  if (typeof feedId === "number") {
    path = `/sources/feeds/${feedId}`;
  } else if (typeof companyId === "number") {
    path = `/sources/companies/${companyId}`;
  }

  const searchParams = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return `${path}?${searchParams.toString()}`;
}

export async function listRssSources(params?: ListRssSourcesParams): Promise<RssSourcePageRead> {
  return apiRequest<RssSourcePageRead>(buildListRssSourcesPath(params));
}

export async function getRssSourceById(sourceId: number): Promise<RssSourceDetail> {
  return apiRequest<RssSourceDetail>(`/sources/${sourceId}`);
}

export async function ingestRssSources(feedIds?: number[]): Promise<RssSourceIngestRead> {
  return apiRequest<RssSourceIngestRead>("/sources/ingest", {
    method: "POST",
    body: feedIds ? JSON.stringify({ feed_ids: feedIds }) : undefined,
  });
}
