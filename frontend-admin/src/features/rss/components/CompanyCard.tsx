import { useState } from "react";

import { buildRssIconUrl } from "@/services/api/rss.service";

import styles from "./CompanyCard.module.css";

type CompanyCardProps = {
  className?: string;
  companyName: string;
  companySlug: string;
  feedCount: number;
  isSelected: boolean;
  onSelect: () => void;
};

export function CompanyCard({
  className,
  companyName,
  companySlug,
  feedCount,
  isSelected,
  onSelect,
}: CompanyCardProps) {
  const [logoFailed, setLogoFailed] = useState(false);
  const logoUrl = buildRssIconUrl(`${companySlug}/${companySlug}.svg`);
  const cardClassName = [styles.card, isSelected ? styles.cardSelected : "", className ?? ""]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      type="button"
      className={cardClassName}
      onClick={onSelect}
      aria-pressed={isSelected}
      title={`${companyName} (${feedCount} feeds)`}
    >
      <div className={styles.logoWrap}>
        {logoUrl && !logoFailed ? (
          <img
            src={logoUrl}
            alt={`${companyName} logo`}
            width={38}
            height={38}
            loading="lazy"
            decoding="async"
            onError={() => setLogoFailed(true)}
          />
        ) : (
          <span>{companyName.slice(0, 1).toUpperCase()}</span>
        )}
      </div>

      <div className={styles.content}>
        <strong>{companyName}</strong>
        <span>{feedCount} feeds</span>
      </div>
    </button>
  );
}
