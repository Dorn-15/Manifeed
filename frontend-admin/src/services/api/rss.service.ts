import { apiRequest, getApiBaseUrl } from "@/services/api/client";
import type {
  RssCompanyEnabledToggleRead,
  RssFeed,
  RssFeedCheckRead,
  RssFeedEnabledToggleRead,
  RssSyncRead,
} from "@/types/rss";

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

export async function syncRssFeeds(force = false): Promise<RssSyncRead> {
  const path = force ? "/rss/sync?force=true" : "/rss/sync";
  return apiRequest<RssSyncRead>(path, {
    method: "POST",
  });
}

export async function checkRssFeeds(feedIds?: number[]): Promise<RssFeedCheckRead> {
  const searchParams = new URLSearchParams();
  if (feedIds) {
    for (const feedId of feedIds) {
      searchParams.append("feed_ids", String(feedId));
    }
  }

  const queryString = searchParams.toString();
  const path = queryString ? `/rss/feeds/check?${queryString}` : "/rss/feeds/check";
  return apiRequest<RssFeedCheckRead>(path, {
    method: "POST",
  });
}

export async function updateRssFeedEnabled(
  feedId: number,
  enabled: boolean,
): Promise<RssFeedEnabledToggleRead> {
  return apiRequest<RssFeedEnabledToggleRead>(`/rss/feeds/${feedId}/enabled`, {
    method: "PATCH",
    body: JSON.stringify({ enabled }),
  });
}

export async function updateRssCompanyEnabled(
  companyId: number,
  enabled: boolean,
): Promise<RssCompanyEnabledToggleRead> {
  return apiRequest<RssCompanyEnabledToggleRead>(`/rss/companies/${companyId}/enabled`, {
    method: "PATCH",
    body: JSON.stringify({ enabled }),
  });
}
