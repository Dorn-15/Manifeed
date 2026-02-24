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
import type { RssCompany, RssFeed, RssFeedCheckRead, RssSyncRead } from "@/types/rss";

import styles from "./page.module.css";

type CompanyGroup = {
  key: string;
  company: RssCompany | null;
  name: string;
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
  return `action=${syncResult.repository_action}`;
}

function formatCheckSummary(checkResult: RssFeedCheckRead): string {
  const summary = [`invalid=${checkResult.length}`];

  if (checkResult.length === 0) {
    return summary.join(" | ");
  }

  const errorPreview = checkResult
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
  const [forceSyncing, setForceSyncing] = useState<boolean>(false);
  const [checking, setChecking] = useState<boolean>(false);
  const [popInfo, setPopInfo] = useState<PopInfoState | null>(null);

  const [searchQuery, setSearchQuery] = useState<string>("");
  const [enabledFilter, setEnabledFilter] = useState<EnabledFilter>("all");
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

  const runSync = useCallback(
    async (force: boolean) => {
      if (force) {
        setForceSyncing(true);
      } else {
        setSyncing(true);
      }

      try {
        const payload = await syncRssFeeds(force);
        showPopInfo(
          force ? "Last force sync result" : "Last sync result",
          formatSyncSummary(payload),
          "info",
        );
        await loadFeeds();
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unexpected error during sync";
        showPopInfo(force ? "Force sync error" : "Sync error", message, "alert");
      } finally {
        if (force) {
          setForceSyncing(false);
        } else {
          setSyncing(false);
        }
      }
    },
    [loadFeeds, showPopInfo],
  );

  const handleSync = useCallback(() => {
    void runSync(false);
  }, [runSync]);

  const handleForceSync = useCallback(() => {
    void runSync(true);
  }, [runSync]);

  const handleCheck = useCallback(async () => {
    setChecking(true);

    try {
      const payload = await checkRssFeeds();
      showPopInfo(
        "Last check result",
        formatCheckSummary(payload),
        payload.length > 0 ? "alert" : "info",
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
        currentFeeds.map((feed) =>
          feed.id === updatedFeed.feed_id ? { ...feed, enabled: updatedFeed.enabled } : feed
        ));
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
          currentFeeds.map((feed) => ({
            ...feed,
            company:
              feed.company !== null && feed.company.id === updatedCompany.company_id
                ? {
                    ...feed.company,
                    enabled: updatedCompany.enabled,
                  }
                : feed.company,
          })),
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
      if (feed.company === null) {
        const fallbackKey = "company:unknown";
        const existingGroup = groupedByKey.get(fallbackKey);
        if (existingGroup) {
          existingGroup.feeds.push(feed);
          continue;
        }

        groupedByKey.set(fallbackKey, {
          key: fallbackKey,
          company: null,
          name: "Unknown",
          feeds: [feed],
        });
        continue;
      }

      const groupKey = `company:${feed.company.id}`;
      const existingGroup = groupedByKey.get(groupKey);
      if (existingGroup) {
        existingGroup.feeds.push(feed);
        continue;
      }

      groupedByKey.set(groupKey, {
        key: groupKey,
        company: feed.company,
        name: normalizeCompanyName(feed.company.name),
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

      if (!normalizedQuery) {
        return true;
      }

      const searchable = [feed.url, feed.section]
        .filter((value): value is string => Boolean(value))
        .join(" ")
        .toLowerCase();

      return searchable.includes(normalizedQuery);
    });

    return sortFeeds(nextFeeds, sortMode);
  }, [enabledFilter, searchQuery, selectedCompany, sortMode]);

  return (
    <PageShell className={styles.main}>
      <PageHeader
        title="RSS Company Workspace"
        description="Select a company in the left panel, then inspect its feeds."
      />

      <RssSyncPanel
        syncing={syncing}
        forceSyncing={forceSyncing}
        checking={checking}
        loadingFeeds={loadingFeeds}
        feedCount={feeds.length}
        onSync={handleSync}
        onForceSync={handleForceSync}
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
            {companyGroups.map((companyGroup) => (
              <CompanyCard
                key={companyGroup.key}
                className={styles.companyCardItem}
                companyName={companyGroup.name}
                companyIconUrl={companyGroup.company?.icon_url ?? null}
                isSelected={companyGroup.key === selectedCompanyKey}
                onSelect={() => setSelectedCompanyKey(companyGroup.key)}
              />
            ))}
          </div>
        </Surface>

        <div className={styles.workspaceContent}>
          <FeedToolbar
            searchQuery={searchQuery}
            enabledFilter={enabledFilter}
            sortMode={sortMode}
            onSearchQueryChange={setSearchQuery}
            onEnabledFilterChange={setEnabledFilter}
            onSortModeChange={setSortMode}
          />

          <FeedPanel
            feeds={filteredSelectedFeeds}
            feedsError={feedsError}
            toggleError={toggleError}
            loadingFeeds={loadingFeeds}
            selectedCompanyName={selectedCompany?.name ?? ""}
            selectedCompanyId={selectedCompany?.company?.id ?? null}
            selectedCompanyEnabled={selectedCompany?.company?.enabled ?? true}
            companyToggling={selectedCompany?.company?.id === togglingCompanyId}
            togglingFeedIds={togglingFeedIds}
            onToggleFeedEnabled={handleFeedEnabledToggle}
            onToggleCompanyEnabled={handleCompanyEnabledToggle}
          />
        </div>
      </section>
    </PageShell>
  );
}
