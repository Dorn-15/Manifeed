export type RssFeed = {
  id: number;
  url: string;
  company_id: number | null;
  company_name: string | null;
  company_enabled: boolean | null;
  section: string | null;
  enabled: boolean;
  status: string;
  trust_score: number;
  language: string | null;
  icon_url: string | null;
};

export type RssCompany = {
  id: number;
  name: string;
  enabled: boolean;
};

export type RssRepositoryAction = "cloned" | "pulled" | "up_to_date";

export type RssSyncRead = {
  repository_action: RssRepositoryAction;
  processed_files: number;
  processed_feeds: number;
  created_companies: number;
  created_tags: number;
  created_feeds: number;
  updated_feeds: number;
  deleted_feeds: number;
};
