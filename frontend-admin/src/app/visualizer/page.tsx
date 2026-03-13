"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  Button,
  Field,
  Notice,
  PageHeader,
  PageShell,
  SourceModal,
  Surface,
  TextInput,
} from "@/components";
import { cx } from "@/components/lib/cx";
import {
  getRssSourceById,
  getRssSourceEmbeddingMap,
  getRssSourceEmbeddingNeighbors,
} from "@/services/api/sources.service";
import type {
  RssSourceDetail,
  RssSourceEmbeddingMapPoint,
  RssSourceEmbeddingMapRead,
  RssSourceEmbeddingNeighborhoodRead,
} from "@/types/sources";
import { formatSourceDate } from "@/utils/date";

import styles from "./page.module.css";

const VIEWBOX_WIDTH = 1120;
const VIEWBOX_HEIGHT = 700;
const VIEWBOX_PADDING = 52;
const DEFAULT_NEIGHBOR_LIMIT = 8;
const DEFAULT_LOOKBACK_DAYS = 14;

type PlotPoint = RssSourceEmbeddingMapPoint & {
  plotX: number;
  plotY: number;
};

function buildPlotPoints(items: RssSourceEmbeddingMapPoint[]): PlotPoint[] {
  if (items.length === 0) {
    return [];
  }

  const xs = items.map((item) => item.x);
  const ys = items.map((item) => item.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);

  const chartWidth = VIEWBOX_WIDTH - VIEWBOX_PADDING * 2;
  const chartHeight = VIEWBOX_HEIGHT - VIEWBOX_PADDING * 2;
  const xRange = maxX - minX || 1;
  const yRange = maxY - minY || 1;

  return items.map((item) => ({
    ...item,
    plotX: VIEWBOX_PADDING + ((item.x - minX) / xRange) * chartWidth,
    plotY: VIEWBOX_HEIGHT - VIEWBOX_PADDING - ((item.y - minY) / yRange) * chartHeight,
  }));
}

function truncateLabel(value: string, maxLength = 22): string {
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, maxLength - 1)}…`;
}

function formatSimilarity(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function formatCompanyLabel(companyNames: string[]): string {
  if (companyNames.length === 0) {
    return "Unknown company";
  }
  return companyNames.join(", ");
}

function toDateInputValue(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function getDefaultDateRange(): { dateFrom: string; dateTo: string } {
  const currentDate = new Date();
  const startDate = new Date(currentDate);
  startDate.setUTCDate(startDate.getUTCDate() - DEFAULT_LOOKBACK_DAYS);
  return {
    dateFrom: toDateInputValue(startDate),
    dateTo: toDateInputValue(currentDate),
  };
}

export default function SourcesVisualizerPage() {
  const [dateRange, setDateRange] = useState<{ dateFrom: string; dateTo: string }>(getDefaultDateRange);
  const [mapPayload, setMapPayload] = useState<RssSourceEmbeddingMapRead>({
    items: [],
    total: 0,
    date_from: null,
    date_to: null,
    embedding_model_name: "intfloat/multilingual-e5-large",
    projection_version: "ipca_umap_cosine_v3",
  });
  const [selectedSourceId, setSelectedSourceId] = useState<number | null>(null);
  const [selectedNeighborhood, setSelectedNeighborhood] =
    useState<RssSourceEmbeddingNeighborhoodRead | null>(null);
  const [loadingMap, setLoadingMap] = useState<boolean>(true);
  const [loadingNeighbors, setLoadingNeighbors] = useState<boolean>(false);
  const [mapError, setMapError] = useState<string | null>(null);
  const [neighborsError, setNeighborsError] = useState<string | null>(null);

  const [modalSourceId, setModalSourceId] = useState<number | null>(null);
  const [modalSourceDetail, setModalSourceDetail] = useState<RssSourceDetail | null>(null);
  const [loadingModalSource, setLoadingModalSource] = useState<boolean>(false);
  const [modalSourceError, setModalSourceError] = useState<string | null>(null);

  const loadMap = useCallback(async () => {
    setLoadingMap(true);
    setMapError(null);

    try {
      const payload = await getRssSourceEmbeddingMap({
        dateFrom: dateRange.dateFrom,
        dateTo: dateRange.dateTo,
      });
      setMapPayload(payload);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unexpected error while loading the visualizer";
      setMapError(message);
      setMapPayload((current) => ({
        ...current,
        items: [],
        total: 0,
        date_from: dateRange.dateFrom,
        date_to: dateRange.dateTo,
      }));
    } finally {
      setLoadingMap(false);
    }
  }, [dateRange.dateFrom, dateRange.dateTo]);

  const loadNeighbors = useCallback(
    async (sourceId: number) => {
      setLoadingNeighbors(true);
      setNeighborsError(null);

      try {
        const payload = await getRssSourceEmbeddingNeighbors(sourceId, {
          neighborLimit: DEFAULT_NEIGHBOR_LIMIT,
          dateFrom: dateRange.dateFrom,
          dateTo: dateRange.dateTo,
        });
        setSelectedNeighborhood(payload);
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Unexpected error while loading neighbors";
        setNeighborsError(message);
        setSelectedNeighborhood(null);
      } finally {
        setLoadingNeighbors(false);
      }
    },
    [dateRange.dateFrom, dateRange.dateTo],
  );

  useEffect(() => {
    void loadMap();
  }, [loadMap]);

  useEffect(() => {
    if (mapPayload.items.length === 0) {
      setSelectedSourceId(null);
      setSelectedNeighborhood(null);
      return;
    }

    const hasSelectedSource = mapPayload.items.some((item) => item.source_id === selectedSourceId);
    if (!hasSelectedSource) {
      setSelectedSourceId(mapPayload.items[0].source_id);
    }
  }, [mapPayload.items, selectedSourceId]);

  useEffect(() => {
    if (selectedSourceId === null) {
      setSelectedNeighborhood(null);
      setNeighborsError(null);
      return;
    }

    void loadNeighbors(selectedSourceId);
  }, [loadNeighbors, selectedSourceId]);

  useEffect(() => {
    if (modalSourceId === null) {
      setModalSourceDetail(null);
      setModalSourceError(null);
      setLoadingModalSource(false);
      return;
    }

    let cancelled = false;
    setLoadingModalSource(true);
    setModalSourceError(null);
    setModalSourceDetail(null);

    void getRssSourceById(modalSourceId)
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setModalSourceDetail(payload);
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }
        const message =
          error instanceof Error ? error.message : "Unexpected error while loading source detail";
        setModalSourceError(message);
      })
      .finally(() => {
        if (cancelled) {
          return;
        }
        setLoadingModalSource(false);
      });

    return () => {
      cancelled = true;
    };
  }, [modalSourceId]);

  useEffect(() => {
    if (modalSourceId === null) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [modalSourceId]);

  const plotPoints = useMemo(() => buildPlotPoints(mapPayload.items), [mapPayload.items]);
  const plotPointBySourceId = useMemo(
    () => new Map(plotPoints.map((point) => [point.source_id, point])),
    [plotPoints],
  );

  const selectedPoint = selectedSourceId === null ? null : plotPointBySourceId.get(selectedSourceId) ?? null;
  const neighborIds = useMemo(
    () => new Set(selectedNeighborhood?.neighbors.map((neighbor) => neighbor.source_id) ?? []),
    [selectedNeighborhood],
  );

  const handleRefresh = useCallback(async () => {
    await loadMap();
    if (selectedSourceId !== null) {
      await loadNeighbors(selectedSourceId);
    }
  }, [loadMap, loadNeighbors, selectedSourceId]);

  const openSourceModal = useCallback((sourceId: number) => {
    setModalSourceId(sourceId);
  }, []);

  const closeSourceModal = useCallback(() => {
    setModalSourceId(null);
  }, []);

  return (
    <PageShell size="wide" className={styles.main}>
      <PageHeader
        title="Semantic Visualizer"
        description="Projection 2D des dernières sources embeddées avec voisinage sémantique cross-langue."
        sideContent={
          <div className={styles.headerMeta}>
            <span>{mapPayload.total} sources projetées</span>
            <span>
              {mapPayload.date_from ?? dateRange.dateFrom} → {mapPayload.date_to ?? dateRange.dateTo}
            </span>
            <span>{mapPayload.embedding_model_name}</span>
            <span>{mapPayload.projection_version}</span>
          </div>
        }
      />

      <Surface className={styles.toolbar} tone="soft" padding="md">
        <div className={styles.toolbarRow}>
          <Field label="Date de debut" htmlFor="visualizer-date-from" className={styles.limitField}>
            <TextInput
              id="visualizer-date-from"
              type="date"
              value={dateRange.dateFrom}
              onChange={(event) => {
                setDateRange((current) => ({
                  ...current,
                  dateFrom: event.target.value,
                }));
              }}
            />
          </Field>

          <Field label="Date de fin" htmlFor="visualizer-date-to" className={styles.limitField}>
            <TextInput
              id="visualizer-date-to"
              type="date"
              value={dateRange.dateTo}
              onChange={(event) => {
                setDateRange((current) => ({
                  ...current,
                  dateTo: event.target.value,
                }));
              }}
            />
          </Field>

          <div className={styles.toolbarActions}>
            <Button variant="secondary" onClick={() => void loadMap()} disabled={loadingMap}>
              Reload map
            </Button>
            <Button
              variant="primary"
              onClick={() => void handleRefresh()}
              disabled={loadingMap || loadingNeighbors}
            >
              Refresh selection
            </Button>
          </div>
        </div>

        {mapError ? <Notice tone="danger">Visualizer error: {mapError}</Notice> : null}
        {neighborsError ? <Notice tone="warning">Neighbors error: {neighborsError}</Notice> : null}
      </Surface>

      <section className={styles.layout}>
        <Surface className={styles.canvasPanel} tone="gradient" padding="lg">
          <div className={styles.panelHeader}>
            <div>
              <h2>Map 2D</h2>
              <p>Les points proches partagent un contenu sémantiquement voisin, pas seulement la langue.</p>
            </div>
            <div className={styles.legend}>
              <span className={cx(styles.legendItem, styles.legendSelected)}>Selected</span>
              <span className={cx(styles.legendItem, styles.legendNeighbor)}>Neighbors</span>
              <span className={cx(styles.legendItem, styles.legendOther)}>Other sources</span>
            </div>
          </div>

          {loadingMap ? <Notice>Loading visualizer...</Notice> : null}
          {!loadingMap && mapPayload.items.length === 0 ? (
            <Notice tone="info">No projected source is available yet. Queue embeddings or restart the DB manager bootstrap.</Notice>
          ) : null}

          {!loadingMap && mapPayload.items.length > 0 ? (
            <div className={styles.canvasShell}>
              <svg
                viewBox={`0 0 ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}`}
                className={styles.canvas}
                role="img"
                aria-label="Semantic source map"
              >
                <rect
                  x="1"
                  y="1"
                  width={VIEWBOX_WIDTH - 2}
                  height={VIEWBOX_HEIGHT - 2}
                  rx="28"
                  className={styles.canvasFrame}
                />

                {Array.from({ length: 6 }, (_, index) => {
                  const x = VIEWBOX_PADDING + (index / 5) * (VIEWBOX_WIDTH - VIEWBOX_PADDING * 2);
                  const y = VIEWBOX_PADDING + (index / 5) * (VIEWBOX_HEIGHT - VIEWBOX_PADDING * 2);
                  return (
                    <g key={index}>
                      <line
                        x1={x}
                        y1={VIEWBOX_PADDING}
                        x2={x}
                        y2={VIEWBOX_HEIGHT - VIEWBOX_PADDING}
                        className={styles.gridLine}
                      />
                      <line
                        x1={VIEWBOX_PADDING}
                        y1={y}
                        x2={VIEWBOX_WIDTH - VIEWBOX_PADDING}
                        y2={y}
                        className={styles.gridLine}
                      />
                    </g>
                  );
                })}

                {selectedPoint && selectedNeighborhood
                  ? selectedNeighborhood.neighbors
                      .map((neighbor) => plotPointBySourceId.get(neighbor.source_id))
                      .filter((point): point is PlotPoint => point !== undefined)
                      .map((neighbor) => (
                        <line
                          key={neighbor.source_id}
                          x1={selectedPoint.plotX}
                          y1={selectedPoint.plotY}
                          x2={neighbor.plotX}
                          y2={neighbor.plotY}
                          className={styles.connectionLine}
                        />
                      ))
                  : null}

                {plotPoints.map((point) => {
                  const isSelected = point.source_id === selectedSourceId;
                  const isNeighbor = neighborIds.has(point.source_id);

                  return (
                    <g
                      key={point.source_id}
                      role="button"
                      tabIndex={0}
                      className={styles.pointGroup}
                      onClick={() => setSelectedSourceId(point.source_id)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setSelectedSourceId(point.source_id);
                        }
                      }}
                    >
                      <circle
                        cx={point.plotX}
                        cy={point.plotY}
                        r={isSelected ? 9 : isNeighbor ? 7 : 5.25}
                        className={cx(
                          styles.point,
                          isSelected && styles.pointSelected,
                          isNeighbor && styles.pointNeighbor,
                        )}
                      />
                      {isSelected || isNeighbor ? (
                        <text x={point.plotX + 11} y={point.plotY - 11} className={styles.pointLabel}>
                          {truncateLabel(point.title)}
                        </text>
                      ) : null}
                    </g>
                  );
                })}
              </svg>
            </div>
          ) : null}
        </Surface>

        <div className={styles.sidebar}>
          <Surface className={styles.selectionPanel} tone="default" padding="lg">
            <div className={styles.panelHeader}>
              <div>
                <h2>Selected source</h2>
                <p>Click a point to inspect its semantic neighborhood.</p>
              </div>
              {selectedPoint ? (
                <Button variant="ghost" size="sm" onClick={() => openSourceModal(selectedPoint.source_id)}>
                  Detail
                </Button>
              ) : null}
            </div>

            {!selectedPoint ? (
              <Notice tone="info">Select a source in the map.</Notice>
            ) : (
              <article className={styles.selectedCard}>
                <div className={styles.selectedMeta}>
                  <span>{formatCompanyLabel(selectedPoint.company_names)}</span>
                  <span>{formatSourceDate(selectedPoint.published_at, "day_month_year")}</span>
                </div>
                <h3>{selectedPoint.title}</h3>
                <p>{selectedPoint.summary ?? "No summary available for this source."}</p>
                <div className={styles.selectedActions}>
                  <Button variant="primary" onClick={() => window.open(selectedPoint.url, "_blank", "noopener,noreferrer")}>
                    Open article
                  </Button>
                  <Button variant="secondary" onClick={() => openSourceModal(selectedPoint.source_id)}>
                    Open detail
                  </Button>
                </div>
              </article>
            )}
          </Surface>

          <Surface className={styles.neighborsPanel} tone="soft" padding="lg">
              <div className={styles.panelHeader}>
                <div>
                  <h2>Nearest sources</h2>
                  <p>Calculated on the original multilingual embedding inside the current date range.</p>
                </div>
              </div>

            {loadingNeighbors ? <Notice>Loading neighbors...</Notice> : null}
            {!loadingNeighbors && selectedNeighborhood?.neighbors.length === 0 ? (
              <Notice tone="info">No close neighbor found in the current sample.</Notice>
            ) : null}

            {!loadingNeighbors && selectedNeighborhood?.neighbors.length ? (
              <div className={styles.neighborList}>
                {selectedNeighborhood.neighbors.map((neighbor) => (
                  <article key={neighbor.source_id} className={styles.neighborCard}>
                    <div className={styles.neighborHeader}>
                      <div>
                        <p className={styles.neighborCompany}>{formatCompanyLabel(neighbor.company_names)}</p>
                        <h3>{neighbor.title}</h3>
                      </div>
                      <span className={styles.similarityBadge}>{formatSimilarity(neighbor.similarity)}</span>
                    </div>

                    <p className={styles.neighborSummary}>
                      {neighbor.summary ?? "No summary available for this source."}
                    </p>

                    <div className={styles.neighborMeta}>
                      <span>{formatSourceDate(neighbor.published_at, "day_month_year")}</span>
                      <span>
                        x={neighbor.x.toFixed(2)} / y={neighbor.y.toFixed(2)}
                      </span>
                    </div>

                    <div className={styles.neighborActions}>
                      <Button
                        variant="chip"
                        active={neighbor.source_id === selectedSourceId}
                        onClick={() => setSelectedSourceId(neighbor.source_id)}
                      >
                        Focus
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => openSourceModal(neighbor.source_id)}>
                        Detail
                      </Button>
                    </div>
                  </article>
                ))}
              </div>
            ) : null}
          </Surface>
        </div>
      </section>

      {modalSourceId !== null ? (
        <SourceModal
          sourceDetail={modalSourceDetail}
          loading={loadingModalSource}
          error={modalSourceError}
          onClose={closeSourceModal}
        />
      ) : null}
    </PageShell>
  );
}
