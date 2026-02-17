"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { PopInfo, type PopInfoType } from "@/components/ui";
import { listRssFeeds } from "@/services/api/rss.service";
import {
  getRssSourceById,
  ingestRssSources,
  listRssSources,
} from "@/services/api/sources.service";
import type { RssFeed } from "@/types/rss";
import type {
  RssSourceDetail,
  RssSourceIngestRead,
  RssSourcePageRead,
} from "@/types/sources";

import styles from "./page.module.css";

const PAGE_SIZE = 50;

type CompanyOption = {
  id: number;
  name: string;
};

type PopInfoState = {
  id: number;
  title: string;
  text: string;
  type: PopInfoType;
};

function formatTimestamp(isoDate: string | null): string {
  if (!isoDate) {
    return "never";
  }
  return new Date(isoDate).toLocaleString();
}

function formatSourceDate(isoDate: string | null): string {
  if (!isoDate) {
    return "n/a";
  }
  return new Date(isoDate).toLocaleString();
}

function formatIngestSummary(result: RssSourceIngestRead): string {
  const summary = [
    `processed=${result.feeds_processed}`,
    `skipped=${result.feeds_skipped}`,
    `created=${result.sources_created}`,
    `updated=${result.sources_updated}`,
    `errors=${result.errors.length}`,
    `duration=${result.duration_ms}ms`,
  ].join(" | ");

  if (result.errors.length === 0) {
    return summary;
  }

  const preview = result.errors
    .slice(0, 2)
    .map((error) => `#${error.feed_id}: ${error.error}`)
    .join(" ; ");
  return `${summary} | ${preview}`;
}

function getSourceCompanyName(companyName: string | null): string {
  return companyName ?? "Unknown company";
}

function getFeedLabel(feed: RssFeed): string {
  const companyName = feed.company_name ?? "Unknown company";
  const section = feed.section ? ` / ${feed.section}` : "";
  return `#${feed.id} - ${companyName}${section}`;
}

export default function AdminSourcesPage() {
  const [sourcesPage, setSourcesPage] = useState<RssSourcePageRead>({
    items: [],
    total: 0,
    limit: PAGE_SIZE,
    offset: 0,
  });
  const [feeds, setFeeds] = useState<RssFeed[]>([]);
  const [loadingSources, setLoadingSources] = useState<boolean>(true);
  const [loadingFilters, setLoadingFilters] = useState<boolean>(true);
  const [sourcesError, setSourcesError] = useState<string | null>(null);
  const [filtersError, setFiltersError] = useState<string | null>(null);
  const [ingestingSources, setIngestingSources] = useState<boolean>(false);
  const [lastRefreshAt, setLastRefreshAt] = useState<string | null>(null);
  const [selectedFeedId, setSelectedFeedId] = useState<number | null>(null);
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(null);
  const [popInfo, setPopInfo] = useState<PopInfoState | null>(null);

  const [selectedSourceId, setSelectedSourceId] = useState<number | null>(null);
  const [selectedSourceDetail, setSelectedSourceDetail] = useState<RssSourceDetail | null>(null);
  const [loadingSourceDetail, setLoadingSourceDetail] = useState<boolean>(false);
  const [sourceDetailError, setSourceDetailError] = useState<string | null>(null);

  const loadFilters = useCallback(async () => {
    setLoadingFilters(true);
    setFiltersError(null);

    try {
      const payload = await listRssFeeds();
      setFeeds(payload);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unexpected error while loading filters";
      setFiltersError(message);
    } finally {
      setLoadingFilters(false);
    }
  }, []);

  const loadSources = useCallback(
    async (offset: number) => {
      setLoadingSources(true);
      setSourcesError(null);

      try {
        const payload = await listRssSources({
          limit: PAGE_SIZE,
          offset,
          feedId: selectedFeedId,
          companyId: selectedCompanyId,
        });
        setSourcesPage(payload);
        setLastRefreshAt(new Date().toISOString());
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Unexpected error while loading sources";
        setSourcesError(message);
      } finally {
        setLoadingSources(false);
      }
    },
    [selectedCompanyId, selectedFeedId],
  );

  useEffect(() => {
    void loadFilters();
  }, [loadFilters]);

  useEffect(() => {
    void loadSources(0);
  }, [loadSources]);

  useEffect(() => {
    if (selectedSourceId === null) {
      return;
    }

    let isCancelled = false;
    setLoadingSourceDetail(true);
    setSourceDetailError(null);
    setSelectedSourceDetail(null);

    void getRssSourceById(selectedSourceId)
      .then((payload) => {
        if (isCancelled) {
          return;
        }
        setSelectedSourceDetail(payload);
      })
      .catch((error: unknown) => {
        if (isCancelled) {
          return;
        }
        const message =
          error instanceof Error ? error.message : "Unexpected error while loading source detail";
        setSourceDetailError(message);
      })
      .finally(() => {
        if (isCancelled) {
          return;
        }
        setLoadingSourceDetail(false);
      });

    return () => {
      isCancelled = true;
    };
  }, [selectedSourceId]);

  const closeSourceDetail = useCallback(() => {
    setSelectedSourceId(null);
    setSelectedSourceDetail(null);
    setSourceDetailError(null);
    setLoadingSourceDetail(false);
  }, []);

  useEffect(() => {
    if (selectedSourceId === null) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeSourceDetail();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [closeSourceDetail, selectedSourceId]);

  useEffect(() => {
    if (selectedSourceId === null) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [selectedSourceId]);

  const showPopInfo = useCallback((title: string, text: string, type: PopInfoType) => {
    setPopInfo((current) => ({
      id: (current?.id ?? 0) + 1,
      title,
      text,
      type,
    }));
  }, []);

  const closePopInfo = useCallback(() => {
    setPopInfo(null);
  }, []);

  const handleRefresh = useCallback(async () => {
    await Promise.all([loadFilters(), loadSources(sourcesPage.offset)]);
  }, [loadFilters, loadSources, sourcesPage.offset]);

  const handleIngest = useCallback(async () => {
    setIngestingSources(true);
    try {
      const payload = await ingestRssSources();
      showPopInfo(
        "Last ingest result",
        formatIngestSummary(payload),
        payload.errors.length > 0 ? "alert" : "info",
      );
      await loadSources(0);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unexpected error during ingest";
      showPopInfo("Ingest error", message, "alert");
    } finally {
      setIngestingSources(false);
    }
  }, [loadSources, showPopInfo]);

  const companyOptions = useMemo<CompanyOption[]>(() => {
    const byId = new Map<number, string>();
    for (const feed of feeds) {
      if (feed.company_id === null || !feed.company_name) {
        continue;
      }
      byId.set(feed.company_id, feed.company_name);
    }

    return Array.from(byId.entries())
      .map(([id, name]) => ({ id, name }))
      .sort((left, right) => left.name.localeCompare(right.name));
  }, [feeds]);

  const feedOptions = useMemo(() => {
    const uniqueById = new Map<number, RssFeed>();
    for (const feed of feeds) {
      uniqueById.set(feed.id, feed);
    }

    return Array.from(uniqueById.values()).sort((left, right) => left.id - right.id);
  }, [feeds]);

  const hasPreviousPage = sourcesPage.offset > 0;
  const hasNextPage = sourcesPage.offset + sourcesPage.items.length < sourcesPage.total;
  const startIndex = sourcesPage.total === 0 ? 0 : sourcesPage.offset + 1;
  const endIndex = sourcesPage.offset + sourcesPage.items.length;

  const handlePreviousPage = useCallback(() => {
    if (!hasPreviousPage || loadingSources) {
      return;
    }

    const nextOffset = Math.max(0, sourcesPage.offset - PAGE_SIZE);
    void loadSources(nextOffset);
  }, [hasPreviousPage, loadSources, loadingSources, sourcesPage.offset]);

  const handleNextPage = useCallback(() => {
    if (!hasNextPage || loadingSources) {
      return;
    }

    const nextOffset = sourcesPage.offset + PAGE_SIZE;
    void loadSources(nextOffset);
  }, [hasNextPage, loadSources, loadingSources, sourcesPage.offset]);

  const handleFeedFilterChange = useCallback((nextRawValue: string) => {
    if (!nextRawValue) {
      setSelectedFeedId(null);
      return;
    }

    const nextFeedId = Number(nextRawValue);
    if (Number.isNaN(nextFeedId)) {
      setSelectedFeedId(null);
      return;
    }

    setSelectedFeedId(nextFeedId);
    setSelectedCompanyId(null);
  }, []);

  const handleCompanyFilterChange = useCallback((nextRawValue: string) => {
    if (!nextRawValue) {
      setSelectedCompanyId(null);
      return;
    }

    const nextCompanyId = Number(nextRawValue);
    if (Number.isNaN(nextCompanyId)) {
      setSelectedCompanyId(null);
      return;
    }

    setSelectedCompanyId(nextCompanyId);
    setSelectedFeedId(null);
  }, []);

  const clearFilters = useCallback(() => {
    setSelectedFeedId(null);
    setSelectedCompanyId(null);
  }, []);

  const handleTileClick = useCallback((sourceId: number) => {
    setSelectedSourceId(sourceId);
  }, []);

  return (
    <main className={styles.main}>
      <header className={styles.header}>
        <div>
          <p className={styles.kicker}>Manifeed Admin</p>
          <h1>Sources Workspace</h1>
          <p>Filter sources by feed or company, then inspect each source details.</p>
        </div>
      </header>

      <section className={styles.actionPanel}>
        <div className={styles.meta}>
          <strong>{sourcesPage.total}</strong>
          <span>sources</span>
          <span>Last refresh {formatTimestamp(lastRefreshAt)}</span>
        </div>
        <div className={styles.actions}>
          <button className={styles.primaryButton} onClick={handleIngest} disabled={ingestingSources}>
            {ingestingSources ? "Ingesting..." : "Ingest sources"}
          </button>
          <button className={styles.secondaryButton} onClick={handleRefresh} disabled={loadingSources}>
            {loadingSources ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </section>

      <section className={styles.filterPanel}>
        <div className={styles.filterField}>
          <label htmlFor="source-feed-filter">Filter by feed</label>
          <select
            id="source-feed-filter"
            className={styles.selectInput}
            value={selectedFeedId ?? ""}
            onChange={(event) => handleFeedFilterChange(event.target.value)}
            disabled={loadingFilters}
          >
            <option value="">All feeds</option>
            {feedOptions.map((feed) => (
              <option key={feed.id} value={feed.id}>
                {getFeedLabel(feed)}
              </option>
            ))}
          </select>
        </div>

        <div className={styles.filterField}>
          <label htmlFor="source-company-filter">Filter by company</label>
          <select
            id="source-company-filter"
            className={styles.selectInput}
            value={selectedCompanyId ?? ""}
            onChange={(event) => handleCompanyFilterChange(event.target.value)}
            disabled={loadingFilters}
          >
            <option value="">All companies</option>
            {companyOptions.map((company) => (
              <option key={company.id} value={company.id}>
                {company.name}
              </option>
            ))}
          </select>
        </div>

        <button className={styles.secondaryButton} onClick={clearFilters} disabled={loadingFilters}>
          Clear filters
        </button>
      </section>

      {popInfo ? (
        <PopInfo
          key={popInfo.id}
          title={popInfo.title}
          text={popInfo.text}
          type={popInfo.type}
          onClose={closePopInfo}
        />
      ) : null}

      {filtersError ? <p className={styles.errorText}>Filter load error: {filtersError}</p> : null}
      {sourcesError ? <p className={styles.errorText}>Source load error: {sourcesError}</p> : null}

      <section className={styles.gridPanel}>
        <div className={styles.gridHeader}>
          <h2>Source tiles</h2>
          <p>
            Showing {startIndex}-{endIndex} of {sourcesPage.total}
          </p>
        </div>

        {loadingSources ? (
          <p className={styles.emptyText}>Loading sources...</p>
        ) : sourcesPage.items.length === 0 ? (
          <p className={styles.emptyText}>No source available for this filter.</p>
        ) : (
          <div className={styles.tileGrid}>
            {sourcesPage.items.map((source) => (
              <button
                key={source.id}
                type="button"
                className={styles.tileCard}
                onClick={() => handleTileClick(source.id)}
              >
                <div className={styles.tileBanner}>
                  {source.image_url ? (
                    <img src={source.image_url} alt={source.title} loading="lazy" decoding="async" />
                  ) : (
                    <div className={styles.tileBannerFallback}>
                      <span>{getSourceCompanyName(source.company_name).slice(0, 1)}</span>
                    </div>
                  )}
                </div>

                <div className={styles.tileBody}>
                  <h3>{source.title}</h3>
                  <p className={styles.tileCompany}>{getSourceCompanyName(source.company_name)}</p>
                  <p className={styles.tileSummary}>{source.summary ?? "No summary available."}</p>
                  <p className={styles.publishedAt}>Published {formatSourceDate(source.published_at)}</p>
                </div>
              </button>
            ))}
          </div>
        )}

        <div className={styles.pagination}>
          <button
            className={styles.secondaryButton}
            onClick={handlePreviousPage}
            disabled={!hasPreviousPage || loadingSources}
          >
            Previous
          </button>
          <button
            className={styles.secondaryButton}
            onClick={handleNextPage}
            disabled={!hasNextPage || loadingSources}
          >
            Next
          </button>
        </div>
      </section>

      {selectedSourceId !== null ? (
        <div
          className={styles.modalBackdrop}
          role="presentation"
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              closeSourceDetail();
            }
          }}
        >
          <section
            className={styles.modalPanel}
            role="dialog"
            aria-modal="true"
            aria-labelledby="source-detail-title"
          >
            <button type="button" className={styles.modalCloseButton} onClick={closeSourceDetail}>
              Close
            </button>

            {loadingSourceDetail ? <p className={styles.emptyText}>Loading source detail...</p> : null}
            {sourceDetailError ? (
              <p className={styles.errorText}>Source detail error: {sourceDetailError}</p>
            ) : null}

            {!loadingSourceDetail && !sourceDetailError && selectedSourceDetail ? (
              <article className={styles.modalContent}>
                <div className={styles.modalBanner}>
                  {selectedSourceDetail.image_url ? (
                    <img
                      src={selectedSourceDetail.image_url}
                      alt={selectedSourceDetail.title}
                      loading="lazy"
                      decoding="async"
                    />
                  ) : (
                    <div className={styles.tileBannerFallback}>
                      <span>{getSourceCompanyName(selectedSourceDetail.company_name).slice(0, 1)}</span>
                    </div>
                  )}
                </div>

                <h3 id="source-detail-title">{selectedSourceDetail.title}</h3>
                <p className={styles.modalCompany}>
                  {getSourceCompanyName(selectedSourceDetail.company_name)}
                </p>

                <dl className={styles.modalMeta}>
                  <div>
                    <dt>ID</dt>
                    <dd>{selectedSourceDetail.id}</dd>
                  </div>
                  <div>
                    <dt>Published</dt>
                    <dd>{formatSourceDate(selectedSourceDetail.published_at)}</dd>
                  </div>
                </dl>

                <p className={styles.modalSummary}>
                  {selectedSourceDetail.summary ?? "No summary available."}
                </p>

                <section className={styles.sectionBlock}>
                  <h4>Feed sections</h4>
                  {selectedSourceDetail.feed_sections.length === 0 ? (
                    <p className={styles.emptyText}>No section available.</p>
                  ) : (
                    <div className={styles.sectionTags}>
                      {selectedSourceDetail.feed_sections.map((section) => (
                        <span key={section}>{section}</span>
                      ))}
                    </div>
                  )}
                </section>

                <a
                  href={selectedSourceDetail.url}
                  target="_blank"
                  rel="noreferrer"
                  className={styles.urlLink}
                >
                  Open article URL
                </a>
              </article>
            ) : null}
          </section>
        </div>
      ) : null}
    </main>
  );
}
