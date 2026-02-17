export type RssSourceListItem = {
  id: number;
  title: string;
  summary: string | null;
  url: string;
  published_at: string | null;
  image_url: string | null;
  company_name: string | null;
};

export type RssSourcePageRead = {
  items: RssSourceListItem[];
  total: number;
  limit: number;
  offset: number;
};

export type RssSourceDetail = {
  id: number;
  title: string;
  summary: string | null;
  url: string;
  published_at: string | null;
  image_url: string | null;
  company_name: string | null;
  feed_sections: string[];
};

export type RssSourceIngestErrorRead = {
  feed_id: number;
  feed_url: string;
  error: string;
};

export type RssSourceIngestRead = {
  status: "completed";
  feeds_processed: number;
  feeds_skipped: number;
  sources_created: number;
  sources_updated: number;
  errors: RssSourceIngestErrorRead[];
  duration_ms: number;
};
