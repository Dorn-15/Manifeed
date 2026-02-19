"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { CompanyCard } from "@/features/rss/components/CompanyCard";
import { FeedPanel } from "@/features/rss/components/FeedPanel";
import {
  FeedToolbar,
  type EnabledFilter,
  type SortMode,
} from "@/features/rss/components/FeedToolbar";
import { PageHeader, PageShell, PopInfo, Surface, type PopInfoType } from "@/components";
import { RssSyncPanel } from "@/features/rss/components/RssSyncPanel";
import {
  checkRssFeeds,
  listRssFeeds,
  syncRssFeeds,
  updateRssCompanyEnabled,
  updateRssFeedEnabled,
} from "@/services/api/rss.service";
import type { RssFeed, RssFeedCheckRead, RssSyncRead } from "@/types/rss";

import styles from "./page.module.css";

type CompanyGroup = {
  key: string;
  id: number | null;
  slug: string;
  name: string;
  enabled: boolean;
  feeds: RssFeed[];
};

type PopInfoState = {
  id: number;
  title: string;
  text: string;
  type: PopInfoType;
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

function buildCompanyGroupKey(feed: RssFeed, slug: string): string {
  if (feed.company_id !== null) {
    return `company:${feed.company_id}`;
  }

  return `fallback:${slug}`;
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

function formatSyncSummary(syncResult: RssSyncRead): string {
  return [
    `action=${syncResult.repository_action}`,
    `files=${syncResult.processed_files}`,
    `processed=${syncResult.processed_feeds}`,
    `created=${syncResult.created_feeds}`,
    `updated=${syncResult.updated_feeds}`,
    `deleted=${syncResult.deleted_feeds}`,
  ].join(" | ");
}

function formatCheckSummary(checkResult: RssFeedCheckRead): string {
  const summary = [
    `valid=${checkResult.valid_count}`,
    `invalid=${checkResult.invalid_count}`,
    `errors=${checkResult.results.length}`,
  ];

  if (checkResult.results.length === 0) {
    return summary.join(" | ");
  }

  const errorPreview = checkResult.results
    .slice(0, 3)
    .map((result) => `#${result.feed_id}: ${result.error}`)
    .join(" ; ");
  return `${summary.join(" | ")} | ${errorPreview}`;
}

export default function AdminRssPage() {
  const [feeds, setFeeds] = useState<RssFeed[]>([]);
  const [loadingFeeds, setLoadingFeeds] = useState<boolean>(true);
  const [feedsError, setFeedsError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState<boolean>(false);
  const [checking, setChecking] = useState<boolean>(false);
  const [popInfo, setPopInfo] = useState<PopInfoState | null>(null);

  const [searchQuery, setSearchQuery] = useState<string>("");
  const [enabledFilter, setEnabledFilter] = useState<EnabledFilter>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [sortMode, setSortMode] = useState<SortMode>("trust_desc");

  const [toggleError, setToggleError] = useState<string | null>(null);
  const [togglingFeedIds, setTogglingFeedIds] = useState<Set<number>>(new Set());
  const [togglingCompanyId, setTogglingCompanyId] = useState<number | null>(null);

  const [selectedCompanyKey, setSelectedCompanyKey] = useState<string | null>(null);

  const loadFeeds = useCallback(async () => {
    setLoadingFeeds(true);
    setFeedsError(null);
    setToggleError(null);

    try {
      const payload = await listRssFeeds();
      setFeeds(payload);
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

  const closePopInfo = useCallback(() => {
    setPopInfo(null);
  }, []);

  const showPopInfo = useCallback((title: string, text: string, type: PopInfoType) => {
    setPopInfo((current) => ({
      id: (current?.id ?? 0) + 1,
      title,
      text,
      type,
    }));
  }, []);

  const handleSync = useCallback(async () => {
    setSyncing(true);

    try {
      const payload = await syncRssFeeds();
      showPopInfo("Last sync result", formatSyncSummary(payload), "info");
      await loadFeeds();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unexpected error during sync";
      showPopInfo("Sync error", message, "alert");
    } finally {
      setSyncing(false);
    }
  }, [loadFeeds, showPopInfo]);

  const handleCheck = useCallback(async () => {
    setChecking(true);

    try {
      const payload = await checkRssFeeds();
      showPopInfo(
        "Last check result",
        formatCheckSummary(payload),
        payload.invalid_count > 0 ? "alert" : "info",
      );
      await loadFeeds();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unexpected error during check";
      showPopInfo("Check error", message, "alert");
    } finally {
      setChecking(false);
    }
  }, [loadFeeds, showPopInfo]);

  const handleFeedEnabledToggle = useCallback(async (feedId: number, nextEnabled: boolean) => {
    setToggleError(null);
    setTogglingFeedIds((currentIds) => {
      const nextIds = new Set(currentIds);
      nextIds.add(feedId);
      return nextIds;
    });

    try {
      const updatedFeed = await updateRssFeedEnabled(feedId, nextEnabled);
      setFeeds((currentFeeds) =>
        currentFeeds.map((feed) => (feed.id === feedId ? updatedFeed : feed)),
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to toggle feed";
      setToggleError(message);
    } finally {
      setTogglingFeedIds((currentIds) => {
        const nextIds = new Set(currentIds);
        nextIds.delete(feedId);
        return nextIds;
      });
    }
  }, []);

  const handleCompanyEnabledToggle = useCallback(
    async (companyId: number, nextEnabled: boolean) => {
      setToggleError(null);
      setTogglingCompanyId(companyId);

      try {
        const updatedCompany = await updateRssCompanyEnabled(companyId, nextEnabled);
        setFeeds((currentFeeds) =>
          currentFeeds.map((feed) =>
            feed.company_id === updatedCompany.id
              ? { ...feed, company_enabled: updatedCompany.enabled }
              : feed,
          ),
        );
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unable to toggle company";
        setToggleError(message);
      } finally {
        setTogglingCompanyId(null);
      }
    },
    [],
  );

  const companyGroups = useMemo(() => {
    const groupedByKey = new Map<string, CompanyGroup>();

    for (const feed of feeds) {
      const companyName = normalizeCompanyName(feed.company_name);
      const companySlug = normalizeCompanySlug(companyName);
      const groupKey = buildCompanyGroupKey(feed, companySlug);
      const currentGroup = groupedByKey.get(groupKey);

      if (currentGroup) {
        currentGroup.feeds.push(feed);
        currentGroup.enabled = currentGroup.enabled && (feed.company_enabled ?? true);
        continue;
      }

      groupedByKey.set(groupKey, {
        key: groupKey,
        id: feed.company_id,
        slug: companySlug,
        name: companyName,
        enabled: feed.company_enabled ?? true,
        feeds: [feed],
      });
    }

    const groups = Array.from(groupedByKey.values());
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
      setSelectedCompanyKey(null);
      return;
    }

    const selectionStillExists = companyGroups.some((group) => group.key === selectedCompanyKey);
    if (!selectionStillExists) {
      setSelectedCompanyKey(companyGroups[0].key);
    }
  }, [companyGroups, selectedCompanyKey]);

  const selectedCompany = useMemo(
    () => companyGroups.find((group) => group.key === selectedCompanyKey) ?? null,
    [companyGroups, selectedCompanyKey],
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

      const searchable = [feed.url, feed.section, feed.country, feed.status]
        .filter((value): value is string => Boolean(value))
        .join(" ")
        .toLowerCase();

      return searchable.includes(normalizedQuery);
    });

    return sortFeeds(nextFeeds, sortMode);
  }, [enabledFilter, searchQuery, selectedCompany, sortMode, statusFilter]);

  return (
    <PageShell className={styles.main}>
      <PageHeader
        title="RSS Company Workspace"
        description="Select a company in the left panel, then inspect its feeds."
      />

      <RssSyncPanel
        syncing={syncing}
        checking={checking}
        loadingFeeds={loadingFeeds}
        feedCount={feeds.length}
        onSync={handleSync}
        onCheck={handleCheck}
        onRefresh={loadFeeds}
      />

      {popInfo ? (
        <PopInfo
          key={popInfo.id}
          title={popInfo.title}
          text={popInfo.text}
          type={popInfo.type}
          onClose={closePopInfo}
        />
      ) : null}

      <section className={styles.workspace}>
        <Surface as="aside" className={styles.companyPanel} padding="sm">
          <div className={styles.companyRail}>
            {companyGroups.map((company) => (
              <CompanyCard
                key={company.key}
                className={styles.companyCardItem}
                companyName={company.name}
                companySlug={company.slug}
                isSelected={company.key === selectedCompanyKey}
                onSelect={() => setSelectedCompanyKey(company.key)}
              />
            ))}
          </div>
        </Surface>

        <div className={styles.workspaceContent}>
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
            toggleError={toggleError}
            loadingFeeds={loadingFeeds}
            selectedCompanyName={selectedCompany?.name ?? ""}
            selectedCompanyId={selectedCompany?.id ?? null}
            selectedCompanyEnabled={selectedCompany?.enabled ?? true}
            companyToggling={selectedCompany?.id === togglingCompanyId}
            togglingFeedIds={togglingFeedIds}
            onToggleFeedEnabled={handleFeedEnabledToggle}
            onToggleCompanyEnabled={handleCompanyEnabledToggle}
          />
        </div>
      </section>
    </PageShell>
  );
}
