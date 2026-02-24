import { Button, Surface } from "@/components";

import styles from "./RssSyncPanel.module.css";

type RssSyncPanelProps = {
  syncing: boolean;
  forceSyncing: boolean;
  checking: boolean;
  loadingFeeds: boolean;
  feedCount: number;
  onSync: () => void;
  onForceSync: () => void;
  onCheck: () => void;
  onRefresh: () => void;
};

export function RssSyncPanel({
  syncing,
  forceSyncing,
  checking,
  loadingFeeds,
  feedCount,
  onSync,
  onForceSync,
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
        <Button variant="primary" onClick={onSync} disabled={syncing || forceSyncing}>
          {syncing ? "Syncing..." : "Sync RSS"}
        </Button>
        <Button variant="secondary" onClick={onForceSync} disabled={forceSyncing || syncing}>
          {forceSyncing ? "Force syncing..." : "Force sync RSS"}
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
