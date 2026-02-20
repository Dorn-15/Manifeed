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
  className?: string;
};

function getCompanyName(companyName: string | null): string {
  return companyName ?? "Unknown company";
}

function joinClassNames(...classes: Array<string | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

export function SourceCard({
  sourceId,
  title,
  summary,
  imageUrl,
  companyName,
  publishedAt,
  onClick,
  className,
}: SourceCardProps) {
  const displayCompanyName = getCompanyName(companyName);
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
