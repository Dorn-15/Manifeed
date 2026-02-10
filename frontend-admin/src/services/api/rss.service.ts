import { apiRequest, getApiBaseUrl } from "@/services/api/client";
import type { RssFeed, RssSyncRead } from "@/types/rss";

function encodeIconPath(iconUrl: string): string {
  return iconUrl
    .split("/")
    .filter((segment) => segment.length > 0)
    .map((segment) => encodeURIComponent(segment))
    .join("/");
}

export function buildRssIconUrl(iconUrl: string | null): string | null {
  if (!iconUrl) {
    return null;
  }

  const encodedPath = encodeIconPath(iconUrl);
  if (!encodedPath) {
    return null;
  }

  return `${getApiBaseUrl()}/rss/img/${encodedPath}`;
}

export async function listRssFeeds(): Promise<RssFeed[]> {
  return apiRequest<RssFeed[]>("/rss/");
}

export async function syncRssFeeds(): Promise<RssSyncRead> {
  return apiRequest<RssSyncRead>("/rss/sync", {
    method: "POST",
  });
}
