# Database Schema

Source of truth:
- Alembic migrations in `backend/alembic/versions/`
- Current baseline: `v1_initialization`

## Overview

Main table groups:
- RSS catalog: `rss_company`, `rss_feeds`, `rss_tags`, `rss_feed_tags`
- Feed runtime: `rss_feed_runtime`
- Sources: `rss_sources`, `rss_source_contents`, `rss_source_feeds`
- Embeddings: `embedding_models`, `rss_source_embeddings`
- Projection: `rss_source_embedding_layouts`, `rss_source_embedding_projection_states`
- Orchestration: `worker_jobs`, `worker_instances`
- RSS worker: `rss_scrape_tasks`, `rss_scrape_task_items`, `rss_scrape_task_executions`
- Embedding worker: `source_embedding_tasks`, `source_embedding_task_items`, `source_embedding_task_executions`

## Current Notes

- `rss_sources` is the unpartitioned master table with a simple `id`
- monthly partitioning is applied to `rss_source_contents` and `rss_source_feeds`
- `rss_feed_runtime.consecutive_error_count` resets to `0` on `success` or `not_modified`
- `rss_feeds.fetchprotection_override` stores the feed-level override when it differs from company defaults
- one backend enqueue request maps to exactly one `worker_jobs` row
- worker tasks are batched; per-feed or per-source membership lives in `*_task_items`
- execution metrics and failure details now live on `*_task_executions`

## Detailed Reference

For the maintained relational description, use:
- Alembic revision `v1_initialization.py`

This file is intentionally compact after the schema refactor. Older detailed table-by-table documents still describe the pre-batch worker schema and should be treated as historical context only.
