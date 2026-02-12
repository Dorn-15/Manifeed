import { buildRssIconUrl } from "@/services/api/rss.service";
import type { RssFeed } from "@/types/rss";
import { EnabledToggle } from "@/components/ui";

import styles from "./FeedCard.module.css";

type FeedCardProps = {
  feed: RssFeed;
  toggling: boolean;
  onToggleEnabled: (feedId: number, nextEnabled: boolean) => void | Promise<void>;
};

function getTrustPercent(trustScore: number): number {
  if (trustScore <= 1) {
    return Math.round(Math.max(0, Math.min(100, trustScore * 100)));
  }

  return Math.round(Math.max(0, Math.min(100, trustScore)));
}

export function FeedCard({ feed, toggling, onToggleEnabled }: FeedCardProps) {
  const iconUrl = buildRssIconUrl(feed.icon_url);
  const trustPercent = getTrustPercent(feed.trust_score);
  const companyName = feed.company_name ?? "Unknown company";
  const section = feed.section ?? "No section";
  const language = feed.language ?? "n/a";
  const companyDisabled = feed.company_enabled === false;

  return (
    <article className={styles.card}>
      <div className={styles.identity}>
        <div className={styles.iconWrap}>
          {iconUrl ? (
            <img
              src={iconUrl}
              alt={companyName}
              loading="lazy"
              decoding="async"
            />
          ) : (
            <span className={styles.iconFallback}>{companyName.slice(0, 1)}</span>
          )}
        </div>
        <div className={styles.sectionInfo}>
          <h3>{section}</h3>
          <div className={styles.metaRow}>
            <span className={styles.languagePill}>{language}</span>
            <span className={styles.statusPill}>{feed.status}</span>
          </div>
        </div>
        <div className={styles.controls}>
          <EnabledToggle
            enabled={feed.enabled}
            loading={toggling}
            disabled={companyDisabled}
            ariaLabel={`Toggle ${feed.url}`}
            onChange={(nextEnabled) => onToggleEnabled(feed.id, nextEnabled)}
          />
        </div>
      </div>
      <div className={styles.trustBlock}>
        <div className={styles.trustHeader}>
          <span>Trust score</span>
          <strong>{feed.trust_score.toFixed(2)}</strong>
        </div>
        <div className={styles.trustTrack}>
          <span className={styles.trustBar} style={{ width: `${trustPercent}%` }} />
        </div>
      </div>

      <a href={feed.url} target="_blank" rel="noreferrer" className={styles.urlLink}>
        {feed.url}
      </a>
    </article>
  );
}
