import { formatSourceDate } from "@/utils/date";

import styles from "./SourceCard.module.css";

type SourceCardProps = {
  sourceId: number;
  title: string;
  summary: string | null;
  author: string | null;
  imageUrl: string | null;
  companyNames: string[];
  publishedAt: string | null;
  onClick: (sourceId: number) => void;
  className?: string;
};

function getCompanyName(companyNames: string[]): string {
  if (companyNames.length === 0) {
    return "Unknown company";
  }
  return companyNames.join(", ");
}

function joinClassNames(...classes: Array<string | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

export function SourceCard({
  sourceId,
  title,
  summary,
  author,
  imageUrl,
  companyNames,
  publishedAt,
  onClick,
  className,
}: SourceCardProps) {
  const displayCompanyName = getCompanyName(companyNames);
  const displayAuthor = author?.trim() ?? "";
  const publishedDate = formatSourceDate(publishedAt, "split");
  const bannerUrl = imageUrl?.trim() ?? "";
  const hasBanner = bannerUrl.length > 0;
  const cardClassName = joinClassNames(
    styles.card,
    hasBanner ? styles.cardWithBanner : styles.cardWithoutBanner,
    className,
  );

  return (
    <button type="button" className={cardClassName} onClick={() => onClick(sourceId)}>
      {hasBanner ? (
        <div className={styles.banner}>
          <img src={bannerUrl} alt={title} loading="lazy" decoding="async" />
        </div>
      ) : null}

      <div className={styles.body}>
        <p className={styles.company}>{displayCompanyName}.</p>
        {displayAuthor ? <p className={styles.author}>By {displayAuthor}.</p> : null}
        <div className={styles.contentContainer}>
          <h3>{title}</h3>
          <p className={styles.summary}>{summary ?? "No summary available."}</p>
        </div>
        <div className={styles.publishedAt}>
          <span>{publishedDate.date}</span>
          <span>{publishedDate.time}</span>
        </div>
      </div>
    </button>
  );
}
