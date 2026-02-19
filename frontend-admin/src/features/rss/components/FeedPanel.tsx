import type { RssFeed } from "@/types/rss";
import { EmptyState, EnabledToggle, Notice, Surface } from "@/components";

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
      <Surface className={styles.panel}>
        <Notice tone="danger">Feed load error: {feedsError}</Notice>
      </Surface>
    );
  }

  if (loadingFeeds) {
    return (
      <Surface className={styles.panel}>
        <Notice className={styles.loadingNotice}>Loading feed cards...</Notice>
      </Surface>
    );
  }

  if (!selectedCompanyName) {
    return (
      <Surface className={styles.panel}>
        <EmptyState
          title="No company detected"
          description="Run a refresh or sync to load feeds."
        />
      </Surface>
    );
  }

  return (
    <Surface className={styles.panel}>
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

      {toggleError ? <Notice tone="danger">Toggle error: {toggleError}</Notice> : null}

      <RssFeedGrid
        feeds={feeds}
        togglingFeedIds={togglingFeedIds}
        onToggleFeedEnabled={onToggleFeedEnabled}
      />
    </Surface>
  );
}
