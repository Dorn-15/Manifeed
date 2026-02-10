import styles from "./FeedToolbar.module.css";

export type EnabledFilter = "all" | "enabled" | "disabled";
export type SortMode = "trust_desc" | "trust_asc" | "url_asc" | "url_desc";

type FeedToolbarProps = {
  searchQuery: string;
  enabledFilter: EnabledFilter;
  statusFilter: string;
  sortMode: SortMode;
  statusOptions: string[];
  onSearchQueryChange: (value: string) => void;
  onEnabledFilterChange: (value: EnabledFilter) => void;
  onStatusFilterChange: (value: string) => void;
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
  statusFilter,
  sortMode,
  statusOptions,
  onSearchQueryChange,
  onEnabledFilterChange,
  onStatusFilterChange,
  onSortModeChange,
}: FeedToolbarProps) {
  return (
    <section className={styles.toolbar}>
      <div className={styles.filterField}>
        <label htmlFor="rss-search">Search selected company</label>
        <input
          id="rss-search"
          value={searchQuery}
          onChange={(event) => onSearchQueryChange(event.target.value)}
          placeholder="URL, section, language, status..."
        />
      </div>

      <div className={styles.filterRow}>
        <div className={styles.filterGroup}>
          <span className={styles.filterLabel}>Enabled</span>
          <div className={styles.filterButtons}>
            {ENABLED_FILTERS.map((filterValue) => (
              <button
                key={filterValue}
                className={
                  enabledFilter === filterValue
                    ? `${styles.filterButton} ${styles.filterButtonActive}`
                    : styles.filterButton
                }
                onClick={() => onEnabledFilterChange(filterValue)}
                type="button"
              >
                {filterValue}
              </button>
            ))}
          </div>
        </div>

        <div className={styles.inlineFields}>
          <label htmlFor="rss-status">
            Status
            <select
              id="rss-status"
              value={statusFilter}
              onChange={(event) => onStatusFilterChange(event.target.value)}
            >
              {statusOptions.map((statusOption) => (
                <option key={statusOption} value={statusOption}>
                  {statusOption}
                </option>
              ))}
            </select>
          </label>

          <label htmlFor="rss-sort">
            Sort by
            <select
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
            </select>
          </label>
        </div>
      </div>
    </section>
  );
}
