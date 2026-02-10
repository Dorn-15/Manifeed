import type { RssFeed } from "@/types/rss";

import { FeedCard } from "./FeedCard";
import styles from "./RssFeedGrid.module.css";

type RssFeedGridProps = {
  feeds: RssFeed[];
};

export function RssFeedGrid({ feeds }: RssFeedGridProps) {
  if (feeds.length === 0) {
    return (
      <section className={styles.emptyState}>
        <h2>No matching feeds</h2>
        <p>Adjust the filters for the selected company.</p>
      </section>
    );
  }

  return (
    <section className={styles.grid}>
      {feeds.map((feed) => (
        <FeedCard key={feed.id} feed={feed} />
      ))}
    </section>
  );
}
