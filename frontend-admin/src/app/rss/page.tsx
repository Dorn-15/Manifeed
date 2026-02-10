"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { CompanyCard } from "@/features/rss/components/CompanyCard";
import { FeedPanel } from "@/features/rss/components/FeedPanel";
import {
  FeedToolbar,
  type EnabledFilter,
  type SortMode,
} from "@/features/rss/components/FeedToolbar";
import { RssSyncPanel } from "@/features/rss/components/RssSyncPanel";
import { listRssFeeds, syncRssFeeds } from "@/services/api/rss.service";
import type { RssFeed, RssSyncRead } from "@/types/rss";

import styles from "./page.module.css";

type CompanyGroup = {
  slug: string;
  name: string;
  feeds: RssFeed[];
};

function normalizeCompanyName(companyName: string | null): string {
  const candidate = companyName?.trim();
  if (!candidate) {
    return "unknown";
  }

  return candidate;
}

function normalizeCompanySlug(companyName: string): string {
  const cleaned = companyName
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9']+/g, "");

  if (!cleaned) {
    return "unknown";
  }

  return `${cleaned[0].toLowerCase()}${cleaned.slice(1)}`;
}

function sortFeeds(feeds: RssFeed[], sortMode: SortMode): RssFeed[] {
  const nextFeeds = [...feeds];

  nextFeeds.sort((left, right) => {
    if (sortMode === "trust_desc") {
      return right.trust_score - left.trust_score;
    }

    if (sortMode === "trust_asc") {
      return left.trust_score - right.trust_score;
    }

    if (sortMode === "url_desc") {
      return right.url.localeCompare(left.url);
    }

    return left.url.localeCompare(right.url);
  });

  return nextFeeds;
}

export default function AdminRssPage() {
  const [feeds, setFeeds] = useState<RssFeed[]>([]);
  const [loadingFeeds, setLoadingFeeds] = useState<boolean>(true);
  const [feedsError, setFeedsError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState<boolean>(false);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [syncResult, setSyncResult] = useState<RssSyncRead | null>(null);
  const [lastRefreshAt, setLastRefreshAt] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState<string>("");
  const [enabledFilter, setEnabledFilter] = useState<EnabledFilter>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [sortMode, setSortMode] = useState<SortMode>("trust_desc");

  const [selectedCompanySlug, setSelectedCompanySlug] = useState<string | null>(null);
  const companyRailRef = useRef<HTMLDivElement | null>(null);
  const [canScrollCompanyLeft, setCanScrollCompanyLeft] = useState(false);
  const [canScrollCompanyRight, setCanScrollCompanyRight] = useState(false);

  const loadFeeds = useCallback(async () => {
    setLoadingFeeds(true);
    setFeedsError(null);

    try {
      const payload = await listRssFeeds();
      setFeeds(payload);
      setLastRefreshAt(new Date().toISOString());
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unexpected error while loading feeds";
      setFeedsError(message);
    } finally {
      setLoadingFeeds(false);
    }
  }, []);

  useEffect(() => {
    void loadFeeds();
  }, [loadFeeds]);

  const handleSync = useCallback(async () => {
    setSyncing(true);
    setSyncError(null);

    try {
      const payload = await syncRssFeeds();
      setSyncResult(payload);
      await loadFeeds();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unexpected error during sync";
      setSyncError(message);
    } finally {
      setSyncing(false);
    }
  }, [loadFeeds]);

  const companyGroups = useMemo(() => {
    const groupedBySlug = new Map<string, CompanyGroup>();

    for (const feed of feeds) {
      const companyName = normalizeCompanyName(feed.company_name);
      const companySlug = normalizeCompanySlug(companyName);
      const currentGroup = groupedBySlug.get(companySlug);

      if (currentGroup) {
        currentGroup.feeds.push(feed);
        continue;
      }

      groupedBySlug.set(companySlug, {
        slug: companySlug,
        name: companyName,
        feeds: [feed],
      });
    }

    const groups = Array.from(groupedBySlug.values());
    groups.sort((left, right) => {
      if (right.feeds.length !== left.feeds.length) {
        return right.feeds.length - left.feeds.length;
      }

      return left.name.localeCompare(right.name);
    });

    return groups;
  }, [feeds]);

  useEffect(() => {
    if (companyGroups.length === 0) {
      setSelectedCompanySlug(null);
      return;
    }

    const selectionStillExists = companyGroups.some((group) => group.slug === selectedCompanySlug);
    if (!selectionStillExists) {
      setSelectedCompanySlug(companyGroups[0].slug);
    }
  }, [companyGroups, selectedCompanySlug]);

  const selectedCompany = useMemo(
    () => companyGroups.find((group) => group.slug === selectedCompanySlug) ?? null,
    [companyGroups, selectedCompanySlug],
  );

  const statusOptions = useMemo(() => {
    const sourceFeeds = selectedCompany?.feeds ?? [];
    const uniqueStatuses = new Set(sourceFeeds.map((feed) => feed.status));
    return ["all", ...Array.from(uniqueStatuses).sort((a, b) => a.localeCompare(b))];
  }, [selectedCompany]);

  useEffect(() => {
    if (statusFilter !== "all" && !statusOptions.includes(statusFilter)) {
      setStatusFilter("all");
    }
  }, [statusFilter, statusOptions]);

  const filteredSelectedFeeds = useMemo(() => {
    const sourceFeeds = selectedCompany?.feeds ?? [];
    const normalizedQuery = searchQuery.trim().toLowerCase();

    const nextFeeds = sourceFeeds.filter((feed) => {
      if (enabledFilter === "enabled" && !feed.enabled) {
        return false;
      }

      if (enabledFilter === "disabled" && feed.enabled) {
        return false;
      }

      if (statusFilter !== "all" && feed.status !== statusFilter) {
        return false;
      }

      if (!normalizedQuery) {
        return true;
      }

      const searchable = [feed.url, feed.section, feed.language, feed.status]
        .filter((value): value is string => Boolean(value))
        .join(" ")
        .toLowerCase();

      return searchable.includes(normalizedQuery);
    });

    return sortFeeds(nextFeeds, sortMode);
  }, [enabledFilter, searchQuery, selectedCompany, sortMode, statusFilter]);

  const updateCompanyRailScrollState = useCallback(() => {
    const rail = companyRailRef.current;
    if (!rail) {
      setCanScrollCompanyLeft(false);
      setCanScrollCompanyRight(false);
      return;
    }

    const remainingScroll = rail.scrollWidth - rail.clientWidth - rail.scrollLeft;
    setCanScrollCompanyLeft(rail.scrollLeft > 8);
    setCanScrollCompanyRight(remainingScroll > 8);
  }, []);

  useEffect(() => {
    const rail = companyRailRef.current;
    if (!rail) {
      return;
    }

    updateCompanyRailScrollState();
    rail.addEventListener("scroll", updateCompanyRailScrollState, { passive: true });
    window.addEventListener("resize", updateCompanyRailScrollState);

    return () => {
      rail.removeEventListener("scroll", updateCompanyRailScrollState);
      window.removeEventListener("resize", updateCompanyRailScrollState);
    };
  }, [companyGroups.length, updateCompanyRailScrollState]);

  const scrollCompanies = useCallback((direction: "left" | "right") => {
    const rail = companyRailRef.current;
    if (!rail) {
      return;
    }

    const step = Math.max(rail.clientWidth * 0.75, 260);
    rail.scrollBy({
      left: direction === "left" ? -step : step,
      behavior: "smooth",
    });
  }, []);

  return (
    <main className={styles.main}>
      <header className={styles.header}>
        <div>
          <p className={styles.kicker}>Manifeed Admin</p>
          <h1>RSS Company Workspace</h1>
          <p>Select a company above, then inspect its feeds below.</p>
        </div>
        <Link className={styles.backLink} href="/">
          Back to dashboard
        </Link>
      </header>

      <RssSyncPanel
        syncing={syncing}
        loadingFeeds={loadingFeeds}
        feedCount={feeds.length}
        lastRefreshAt={lastRefreshAt}
        onSync={handleSync}
        onRefresh={loadFeeds}
      />

      {syncError ? <p className={styles.errorText}>Sync error: {syncError}</p> : null}
      {syncResult ? (
        <section className={styles.syncSummaryCard}>
          <h2>Last sync result</h2>
          <p>
            action={syncResult.repository_action} | files={syncResult.processed_files} |
            processed={syncResult.processed_feeds} | created={syncResult.created_feeds} |
            updated={syncResult.updated_feeds} | deleted={syncResult.deleted_feeds}
          </p>
        </section>
      ) : null}

      <section className={styles.workspace}>
        <section className={styles.companyPanel}>
          <div className={styles.companyPanelHeader}>
            <h2>Companies</h2>
            <p>{companyGroups.length} company cards</p>
          </div>

          <div className={styles.companyRailWrap}>
            <button
              className={styles.companyScrollButton}
              type="button"
              onClick={() => scrollCompanies("left")}
              disabled={!canScrollCompanyLeft}
              aria-label="Scroll companies to the left"
            >
              {"<"}
            </button>
            <div className={styles.companyRail} ref={companyRailRef}>
              {companyGroups.map((company) => (
                <CompanyCard
                  key={company.slug}
                  className={styles.companyCardItem}
                  companyName={company.name}
                  companySlug={company.slug}
                  feedCount={company.feeds.length}
                  isSelected={company.slug === selectedCompanySlug}
                  onSelect={() => setSelectedCompanySlug(company.slug)}
                />
              ))}
            </div>
            <button
              className={styles.companyScrollButton}
              type="button"
              onClick={() => scrollCompanies("right")}
              disabled={!canScrollCompanyRight}
              aria-label="Scroll companies to the right"
            >
              {">"}
            </button>
          </div>
        </section>

        <FeedToolbar
          searchQuery={searchQuery}
          enabledFilter={enabledFilter}
          statusFilter={statusFilter}
          sortMode={sortMode}
          statusOptions={statusOptions}
          onSearchQueryChange={setSearchQuery}
          onEnabledFilterChange={setEnabledFilter}
          onStatusFilterChange={setStatusFilter}
          onSortModeChange={setSortMode}
        />

        <FeedPanel
          feeds={filteredSelectedFeeds}
          feedsError={feedsError}
          loadingFeeds={loadingFeeds}
          selectedCompanyName={selectedCompany?.name ?? null}
        />
      </section>
    </main>
  );
}
