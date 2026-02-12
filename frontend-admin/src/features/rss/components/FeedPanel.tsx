import type { RssFeed } from "@/types/rss";
import { EnabledToggle } from "@/components/ui";

import { RssFeedGrid } from "./RssFeedGrid";
import styles from "./FeedPanel.module.css";

type FeedPanelProps = {
  feeds: RssFeed[];
  feedsError: string | null;
  toggleError: string | null;
  loadingFeeds: boolean;
  selectedCompanyName: string;
  selectedCompanyId: number | null;
  selectedCompanyEnabled: boolean;
  companyToggling: boolean;
  togglingFeedIds: Set<number>;
  onToggleFeedEnabled: (feedId: number, nextEnabled: boolean) => void | Promise<void>;
  onToggleCompanyEnabled: (companyId: number, nextEnabled: boolean) => void | Promise<void>;
};

export function FeedPanel({
  feeds,
  feedsError,
  toggleError,
  loadingFeeds,
  selectedCompanyName,
  selectedCompanyId,
  selectedCompanyEnabled,
  companyToggling,
  togglingFeedIds,
  onToggleFeedEnabled,
  onToggleCompanyEnabled,
}: FeedPanelProps) {
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

  if (!selectedCompanyName) {
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
        <div>
          <h2>{selectedCompanyName}</h2>
          <p>{feeds.length} feeds</p>
        </div>
        {selectedCompanyId !== null ? (
          <EnabledToggle
            enabled={selectedCompanyEnabled}
            loading={companyToggling}
            ariaLabel={`Toggle company ${selectedCompanyName}`}
            onChange={(nextEnabled) => onToggleCompanyEnabled(selectedCompanyId, nextEnabled)}
          />
        ) : null}
      </header>

      {toggleError ? <p className={styles.errorText}>Toggle error: {toggleError}</p> : null}

      <RssFeedGrid
        feeds={feeds}
        togglingFeedIds={togglingFeedIds}
        onToggleFeedEnabled={onToggleFeedEnabled}
      />
    </section>
  );
}
