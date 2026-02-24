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

export type RssSyncRead = {
  repository_action: RssRepositoryAction;
};

export type RssFeedCheckResultRead = {
  feed_id: number;
  url: string;
  error: string;
  fetchprotection: number | null;
};

export type RssFeedCheckRead = RssFeedCheckResultRead[];
