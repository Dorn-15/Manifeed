import styles from "./RssSyncPanel.module.css";

type RssSyncPanelProps = {
  syncing: boolean;
  checking: boolean;
  loadingFeeds: boolean;
  feedCount: number;
  lastRefreshAt: string | null;
  onSync: () => void;
  onCheck: () => void;
  onRefresh: () => void;
};

function formatTimestamp(isoDate: string | null): string {
  if (!isoDate) {
    return "never";
  }

  return new Date(isoDate).toLocaleString();
}

export function RssSyncPanel({
  syncing,
  checking,
  loadingFeeds,
  feedCount,
  lastRefreshAt,
  onSync,
  onCheck,
  onRefresh,
}: RssSyncPanelProps) {
  return (
    <section className={styles.panel}>
      <div className={styles.header}>
        <div>
          <h2>Control actions</h2>
          <p>Sync RSS sources, then refresh the feed cards.</p>
        </div>
        <div className={styles.meta}>
          <span>{feedCount} feeds</span>
          <span>Last refresh {formatTimestamp(lastRefreshAt)}</span>
        </div>
      </div>

      <div className={styles.actions}>
        <button className={styles.primaryButton} onClick={onSync} disabled={syncing}>
          {syncing ? "Syncing..." : "Sync RSS"}
        </button>
        <button className={styles.secondaryButton} onClick={onCheck} disabled={checking}>
          {checking ? "Checking..." : "Check feeds"}
        </button>
        <button className={styles.secondaryButton} onClick={onRefresh} disabled={loadingFeeds}>
          {loadingFeeds ? "Refreshing..." : "Refresh feeds"}
        </button>
      </div>
    </section>
  );
}
