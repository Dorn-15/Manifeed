import type { RssFeed } from "@/types/rss";

import { RssFeedGrid } from "./RssFeedGrid";
import styles from "./FeedPanel.module.css";

type FeedPanelProps = {
  feeds: RssFeed[];
  feedsError: string | null;
  loadingFeeds: boolean;
  selectedCompanyName: string | null;
};

export function FeedPanel({ feeds, feedsError, loadingFeeds, selectedCompanyName }: FeedPanelProps) {
  if (feedsError) {
    return (
      <section className={styles.panel}>
        <p className={styles.errorText}>Feed load error: {feedsError}</p>
      </section>
    );
  }

  if (loadingFeeds) {
    return (
      <section className={styles.panel}>
        <p className={styles.loadingText}>Loading feed cards...</p>
      </section>
    );
  }

  if (selectedCompanyName === null) {
    return (
      <section className={styles.panel}>
        <section className={styles.emptyState}>
          <h2>No company detected</h2>
          <p>Run a refresh or sync to load feeds.</p>
        </section>
      </section>
    );
  }

  return (
    <section className={styles.panel}>
      <header className={styles.header}>
        <h2>{selectedCompanyName}</h2>
        <p>{feeds.length} matching feeds</p>
      </header>
      <RssFeedGrid feeds={feeds} />
    </section>
  );
}
