import type { RssSourceDetail } from "@/types/sources";
import { formatSourceDate } from "@/utils/date";

import { Notice } from "../../feedback/notice";
import { Button } from "../button";
import { Surface } from "../surface";
import styles from "./SourceModal.module.css";

type SourceModalProps = {
  sourceDetail: RssSourceDetail | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
};

function getCompanyName(companyName: string | null): string {
  return companyName ?? "Unknown company";
}

function formatCompanyLabel(companyName: string | null): string {
  const candidate = getCompanyName(companyName).trim();
  if (candidate.endsWith(".")) {
    return candidate;
  }

  return `${candidate}.`;
}

export function SourceModal({
  sourceDetail,
  loading,
  error,
  onClose,
}: SourceModalProps) {
  const publishedAt = sourceDetail ? formatSourceDate(sourceDetail.published_at, "full") : "n/a";

  return (
    <div
      className={styles.backdrop}
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <Surface
        as="section"
        className={styles.panel}
        tone="default"
        padding="none"
        blur={false}
        role="dialog"
        aria-modal="true"
        aria-labelledby="source-detail-title"
      >
        <Button className={styles.closeButton} variant="ghost" size="sm" onClick={onClose}>
          Close
        </Button>

        {loading || error ? (
          <div className={styles.statePanel}>
            {loading ? <Notice className={styles.emptyText}>Loading source detail...</Notice> : null}
            {error ? <Notice tone="danger">Source detail error: {error}</Notice> : null}
          </div>
        ) : null}

        {!loading && !error && sourceDetail ? (
          <article className={styles.content}>
            {sourceDetail.image_url ? (
            <div className={styles.banner}>
                <img
                  src={sourceDetail.image_url}
                  alt={sourceDetail.title}
                  loading="lazy"
                  decoding="async"
                />
              </div>
            ) : null}

            <div className={styles.body}>
              <p className={styles.company}>{formatCompanyLabel(sourceDetail.company_name)}</p>
              <h3 id="source-detail-title">{sourceDetail.title}</h3>

              <p className={styles.summary}>{sourceDetail.summary ?? "No summary available."}</p>

              <section className={styles.sectionBlock}>
                <h4>Feed sections</h4>
                {sourceDetail.feed_sections.length === 0 ? (
                  <p className={styles.emptyText}>No section available.</p>
                ) : (
                  <div className={styles.sectionTags}>
                    {sourceDetail.feed_sections.map((section) => (
                      <span key={section}>{section}</span>
                    ))}
                  </div>
                )}
              </section>

              <footer className={styles.footer}>
                <a href={sourceDetail.url} target="_blank" rel="noreferrer" className={styles.urlLink}>
                  Open article
                </a>
                <time className={styles.publishedAt} dateTime={sourceDetail.published_at ?? undefined}>
                  {publishedAt}
                </time>
              </footer>
            </div>
          </article>
        ) : null}
      </Surface>
    </div>
  );
}
