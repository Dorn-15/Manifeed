import { Button, Surface } from "@/components";

import styles from "./RssSyncPanel.module.css";

type RssSyncPanelProps = {
  syncing: boolean;
  checking: boolean;
  loadingFeeds: boolean;
  feedCount: number;
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
  onSync,
  onCheck,
  onRefresh,
}: RssSyncPanelProps) {
  return (
    <Surface className={styles.panel}>
      <div className={styles.header}>
        <div>
          <h2>Control actions</h2>
          <p>Sync RSS sources, then refresh the feed cards.</p>
        </div>
        <div className={styles.meta}>
          <span>{feedCount} feeds</span>
        </div>
      </div>

      <div className={styles.actions}>
        <Button variant="primary" onClick={onSync} disabled={syncing}>
          {syncing ? "Syncing..." : "Sync RSS"}
        </Button>
        <Button onClick={onCheck} disabled={checking}>
          {checking ? "Checking..." : "Check feeds"}
        </Button>
        <Button onClick={onRefresh} disabled={loadingFeeds}>
          {loadingFeeds ? "Refreshing..." : "Refresh feeds"}
        </Button>
      </div>
    </Surface>
  );
}
