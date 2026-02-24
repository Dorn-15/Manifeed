import { Button, Field, SelectInput, Surface, TextInput } from "@/components";

import styles from "./FeedToolbar.module.css";

export type EnabledFilter = "all" | "enabled" | "disabled";
export type SortMode = "trust_desc" | "trust_asc" | "url_asc" | "url_desc";

type FeedToolbarProps = {
  searchQuery: string;
  enabledFilter: EnabledFilter;
  sortMode: SortMode;
  onSearchQueryChange: (value: string) => void;
  onEnabledFilterChange: (value: EnabledFilter) => void;
  onSortModeChange: (value: SortMode) => void;
};

const ENABLED_FILTERS: EnabledFilter[] = ["all", "enabled", "disabled"];
const SORT_MODES: SortMode[] = ["trust_desc", "trust_asc", "url_asc", "url_desc"];

function parseSortMode(value: string): SortMode | null {
  return SORT_MODES.find((mode) => mode === value) ?? null;
}

export function FeedToolbar({
  searchQuery,
  enabledFilter,
  sortMode,
  onSearchQueryChange,
  onEnabledFilterChange,
  onSortModeChange,
}: FeedToolbarProps) {
  return (
    <Surface className={styles.toolbar}>
      <Field label="Search selected company" htmlFor="rss-search">
        <TextInput
          id="rss-search"
          value={searchQuery}
          onChange={(event) => onSearchQueryChange(event.target.value)}
          placeholder="URL, section..."
        />
      </Field>

      <div className={styles.filterRow}>
        <div className={styles.filterGroup}>
          <span className={styles.filterLabel}>Enabled</span>
          <div className={styles.filterButtons}>
            {ENABLED_FILTERS.map((filterValue) => (
              <Button
                key={filterValue}
                variant="chip"
                size="sm"
                active={enabledFilter === filterValue}
                onClick={() => onEnabledFilterChange(filterValue)}
              >
                {filterValue}
              </Button>
            ))}
          </div>
        </div>

        <div className={styles.inlineFields}>
          <Field label="Sort by" htmlFor="rss-sort" className={styles.inlineField}>
            <SelectInput
              id="rss-sort"
              value={sortMode}
              onChange={(event) => {
                const nextSortMode = parseSortMode(event.target.value);
                if (!nextSortMode) {
                  return;
                }

                onSortModeChange(nextSortMode);
              }}
            >
              <option value="trust_desc">Trust high to low</option>
              <option value="trust_asc">Trust low to high</option>
              <option value="url_asc">URL A to Z</option>
              <option value="url_desc">URL Z to A</option>
            </SelectInput>
          </Field>
        </div>
      </div>
    </Surface>
  );
}
