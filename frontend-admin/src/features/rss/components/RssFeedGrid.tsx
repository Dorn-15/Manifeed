import type { RssFeed } from "@/types/rss";
import { EmptyState } from "@/components";

import { FeedCard } from "./FeedCard";
import styles from "./RssFeedGrid.module.css";

type RssFeedGridProps = {
  feeds: RssFeed[];
  togglingFeedIds: Set<number>;
  onToggleFeedEnabled: (feedId: number, nextEnabled: boolean) => void | Promise<void>;
};

export function RssFeedGrid({ feeds, togglingFeedIds, onToggleFeedEnabled }: RssFeedGridProps) {
  if (feeds.length === 0) {
    return <EmptyState title="No matching feeds" description="Adjust the filters for the selected company." />;
  }

  return (
    <section className={styles.grid}>
      {feeds.map((feed) => (
        <FeedCard
          key={feed.id}
          feed={feed}
          toggling={togglingFeedIds.has(feed.id)}
          onToggleEnabled={onToggleFeedEnabled}
        />
      ))}
    </section>
  );
}
