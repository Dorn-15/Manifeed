import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

type RssFeed = {
  id: number;
  url: string;
  company_name: string | null;
  section: string | null;
  enabled: boolean;
  status: string;
  trust_score: number;
  language: string | null;
  icon_url: string | null;
};

type RssSyncResponse = {
  repository_action: "cloned" | "pulled" | "up_to_date";
  processed_files: number;
  processed_feeds: number;
  created_companies: number;
  created_tags: number;
  created_feeds: number;
  updated_feeds: number;
  deleted_feeds: number;
};

function encodeIconPath(iconUrl: string): string {
  return iconUrl
    .split("/")
    .filter((segment) => segment.length > 0)
    .map((segment) => encodeURIComponent(segment))
    .join("/");
}

function buildIconUrl(apiUrl: string, iconUrl: string | null): string | null {
  if (!iconUrl) {
    return null;
  }
  const encodedPath = encodeIconPath(iconUrl);
  if (!encodedPath) {
    return null;
  }
  return `${apiUrl}/rss/img/${encodedPath}`;
}

export default function RssAdminPage() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  const [feeds, setFeeds] = useState<RssFeed[]>([]);
  const [loadingFeeds, setLoadingFeeds] = useState<boolean>(true);
  const [feedsError, setFeedsError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState<boolean>(false);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [syncResult, setSyncResult] = useState<RssSyncResponse | null>(null);

  const loadFeeds = useCallback(async () => {
    if (!apiUrl) {
      setFeedsError("Missing NEXT_PUBLIC_API_URL");
      setLoadingFeeds(false);
      return;
    }

    setLoadingFeeds(true);
    setFeedsError(null);
    try {
      const response = await fetch(`${apiUrl}/rss/`);
      const payload = (await response.json()) as RssFeed[] | { message?: string };
      if (!response.ok) {
        const message =
          !Array.isArray(payload) && payload.message
            ? payload.message
            : `Failed to load feeds (${response.status})`;
        throw new Error(message);
      }
      setFeeds(Array.isArray(payload) ? payload : []);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unexpected error while loading feeds";
      setFeedsError(message);
    } finally {
      setLoadingFeeds(false);
    }
  }, [apiUrl]);

  useEffect(() => {
    void loadFeeds();
  }, [loadFeeds]);

  const handleSync = useCallback(async () => {
    if (!apiUrl) {
      setSyncError("Missing NEXT_PUBLIC_API_URL");
      return;
    }

    setSyncing(true);
    setSyncError(null);
    try {
      const response = await fetch(`${apiUrl}/rss/sync`, { method: "POST" });
      const payload = (await response.json()) as RssSyncResponse | { message?: string };
      if (!response.ok) {
        const message =
          "message" in payload && payload.message
            ? payload.message
            : `Sync failed (${response.status})`;
        throw new Error(message);
      }
      setSyncResult(payload as RssSyncResponse);
      await loadFeeds();
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unexpected error during sync";
      setSyncError(message);
    } finally {
      setSyncing(false);
    }
  }, [apiUrl, loadFeeds]);

  return (
    <main style={{ fontFamily: "system-ui", padding: "2rem" }}>
      <h1>RSS Feeds Admin</h1>
      <p>
        <Link href="/">Back to home</Link>
      </p>

      <div style={{ display: "flex", gap: "0.75rem", marginBottom: "1rem" }}>
        <button onClick={handleSync} disabled={syncing || !apiUrl}>
          {syncing ? "Syncing..." : "Sync RSS (/rss/sync)"}
        </button>
        <button onClick={() => void loadFeeds()} disabled={loadingFeeds || !apiUrl}>
          {loadingFeeds ? "Loading..." : "Refresh feeds (/rss/)"}
        </button>
      </div>

      {syncError ? <p style={{ color: "#b00020" }}>Sync error: {syncError}</p> : null}
      {syncResult ? (
        <p style={{ marginBottom: "1rem" }}>
          Last sync: {syncResult.repository_action} | files={syncResult.processed_files} |
          feeds={syncResult.processed_feeds} | created={syncResult.created_feeds} |
          updated={syncResult.updated_feeds} | deleted={syncResult.deleted_feeds}
        </p>
      ) : null}

      {feedsError ? <p style={{ color: "#b00020" }}>Feed load error: {feedsError}</p> : null}
      {!feedsError && loadingFeeds ? <p>Loading feeds...</p> : null}

      {!feedsError && !loadingFeeds ? (
        <div style={{ overflowX: "auto" }}>
          <table
            style={{
              borderCollapse: "collapse",
              minWidth: "1100px",
              width: "100%",
            }}
          >
            <thead>
              <tr>
                <th style={{ border: "1px solid #ddd", padding: "0.5rem" }}>id</th>
                <th style={{ border: "1px solid #ddd", padding: "0.5rem" }}>icon</th>
                <th style={{ border: "1px solid #ddd", padding: "0.5rem" }}>url</th>
                <th style={{ border: "1px solid #ddd", padding: "0.5rem" }}>company</th>
                <th style={{ border: "1px solid #ddd", padding: "0.5rem" }}>section</th>
                <th style={{ border: "1px solid #ddd", padding: "0.5rem" }}>enabled</th>
                <th style={{ border: "1px solid #ddd", padding: "0.5rem" }}>status</th>
                <th style={{ border: "1px solid #ddd", padding: "0.5rem" }}>trust_score</th>
                <th style={{ border: "1px solid #ddd", padding: "0.5rem" }}>language</th>
                <th style={{ border: "1px solid #ddd", padding: "0.5rem" }}>icon_url</th>
              </tr>
            </thead>
            <tbody>
              {feeds.map((feed) => {
                const iconUrl = apiUrl ? buildIconUrl(apiUrl, feed.icon_url) : null;
                return (
                  <tr key={feed.id}>
                    <td style={{ border: "1px solid #ddd", padding: "0.5rem" }}>{feed.id}</td>
                    <td style={{ border: "1px solid #ddd", padding: "0.5rem" }}>
                      {iconUrl ? (
                        <img
                          src={iconUrl}
                          alt={feed.company_name ?? "icon"}
                          width={28}
                          height={28}
                        />
                      ) : (
                        "-"
                      )}
                    </td>
                    <td style={{ border: "1px solid #ddd", padding: "0.5rem" }}>
                      <a href={feed.url} target="_blank" rel="noreferrer">
                        {feed.url}
                      </a>
                    </td>
                    <td style={{ border: "1px solid #ddd", padding: "0.5rem" }}>
                      {feed.company_name ?? "-"}
                    </td>
                    <td style={{ border: "1px solid #ddd", padding: "0.5rem" }}>
                      {feed.section ?? "-"}
                    </td>
                    <td style={{ border: "1px solid #ddd", padding: "0.5rem" }}>
                      {feed.enabled ? "true" : "false"}
                    </td>
                    <td style={{ border: "1px solid #ddd", padding: "0.5rem" }}>{feed.status}</td>
                    <td style={{ border: "1px solid #ddd", padding: "0.5rem" }}>
                      {feed.trust_score}
                    </td>
                    <td style={{ border: "1px solid #ddd", padding: "0.5rem" }}>
                      {feed.language ?? "-"}
                    </td>
                    <td style={{ border: "1px solid #ddd", padding: "0.5rem" }}>
                      {feed.icon_url ?? "-"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </main>
  );
}
