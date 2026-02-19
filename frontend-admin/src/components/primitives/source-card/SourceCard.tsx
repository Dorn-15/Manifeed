import { formatSourceDate } from "@/utils/date";

import styles from "./SourceCard.module.css";

type SourceCardProps = {
  sourceId: number;
  title: string;
  summary: string | null;
  imageUrl: string | null;
  companyName: string | null;
  publishedAt: string | null;
  onClick: (sourceId: number) => void;
};

function getCompanyName(companyName: string | null): string {
  return companyName ?? "Unknown company";
}

export function SourceCard({
  sourceId,
  title,
  summary,
  imageUrl,
  companyName,
  publishedAt,
  onClick,
}: SourceCardProps) {
  const displayCompanyName = getCompanyName(companyName);
  const fallbackLetter = displayCompanyName.slice(0, 1);
  const publishedDate = formatSourceDate(publishedAt, "split");

  return (
    <button type="button" className={styles.card} onClick={() => onClick(sourceId)}>
      <div className={styles.banner}>
        {imageUrl ? (
          <img src={imageUrl} alt={title} loading="lazy" decoding="async" />
        ) : (
          <div className={styles.bannerFallback}>
            <span>{fallbackLetter}</span>
          </div>
        )}
      </div>

      <div className={styles.body}>
        <p className={styles.company}>{displayCompanyName}.</p>
        <h3>{title}</h3>
        <p className={styles.summary}>{summary ?? "No summary available."}</p>
        <div className={styles.publishedAt}>
          <span>{publishedDate.date}</span>
          <span>{publishedDate.time}</span>
        </div>
      </div>
    </button>
  );
}
