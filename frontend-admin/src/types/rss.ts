export type RssCompany = {
  id: number;
  name: string;
  icon_url: string | null;
  country: string | null;
  language: string | null;
  fetchprotection: number;
  enabled: boolean;
};

export type RssFeed = {
  id: number;
  url: string;
  section: string | null;
  enabled: boolean;
  trust_score: number;
  fetchprotection: number;
  company: RssCompany | null;
};

export type RssFeedEnabledToggleRead = {
  feed_id: number;
  enabled: boolean;
};

export type RssCompanyEnabledToggleRead = {
  company_id: number;
  enabled: boolean;
};

export type RssRepositoryAction = "cloned" | "update" | "up_to_date";
export type RssSyncMode = "noop" | "full_reconcile";

export type RssSyncRead = {
  repository_action: RssRepositoryAction;
  mode: RssSyncMode;
  current_revision: string | null;
  applied_from_revision: string | null;
  files_processed: number;
  companies_removed: number;
  feeds_removed: number;
};

export type RssFeedCheckResultRead = {
  feed_id: number;
  url: string;
  error: string;
  fetchprotection: number | null;
};

export type RssFeedCheckRead = RssFeedCheckResultRead[];

export type RssScrapeJobKind = "rss_scrape_check" | "rss_scrape_ingest";
export type RssScrapeJobStatus =
  | "queued"
  | "processing"
  | "completed"
  | "completed_with_errors"
  | "failed";

export type RssScrapeJobQueuedRead = {
  job_id: string;
  job_kind: RssScrapeJobKind;
  status: RssScrapeJobStatus;
  tasks_total: number;
  feeds_total: number;
};
