import { useState } from "react";

import { buildRssIconUrl } from "@/services/api/rss.service";

import styles from "./CompanyCard.module.css";

type CompanyCardProps = {
  className?: string;
  companyName: string;
  companySlug: string;
  isSelected: boolean;
  onSelect: () => void;
};

export function CompanyCard({
  className,
  companyName,
  companySlug,
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
      aria-label={`Select ${companyName}`}
    >
        {logoUrl && !logoFailed ? (
          <img
            src={logoUrl}
            alt={`${companyName} logo`}
            loading="lazy"
            decoding="async"
            onError={() => setLogoFailed(true)}
          />
        ) : (
          <span>{companyName.slice(0, 1).toUpperCase()}</span>
        )}
    </button>
  );
}
