"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge, Button, Notice, PageHeader, PageShell, Surface } from "@/components";
import { getQueuesOverview, purgeTaskQueue } from "@/services/api/queues.service";
import type { QueueOverviewRead, TaskQueueOverviewRead } from "@/types/queues";
import { formatSourceDate } from "@/utils/date";

import styles from "./page.module.css";

const REFRESH_INTERVAL_MS = 15_000;

function formatInteger(value: number | null): string {
  if (value === null) {
    return "n/a";
  }
  return new Intl.NumberFormat("fr-FR").format(value);
}

function formatIdleDuration(idleMs: number): string {
  if (idleMs < 1000) {
    return `${idleMs} ms`;
  }
  if (idleMs < 60_000) {
    return `${(idleMs / 1000).toFixed(1)} s`;
  }
  return `${(idleMs / 60_000).toFixed(1)} min`;
}

function sortQueuesByPriority(items: TaskQueueOverviewRead[]): TaskQueueOverviewRead[] {
  const nextItems = [...items];
  nextItems.sort((left, right) => {
    if (left.blocked !== right.blocked) {
      return left.blocked ? -1 : 1;
    }
    if (right.queue_length !== left.queue_length) {
      return right.queue_length - left.queue_length;
    }
    return left.queue_name.localeCompare(right.queue_name);
  });
  return nextItems;
}

export default function AdminQueuesPage() {
  const [overview, setOverview] = useState<QueueOverviewRead | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [purgingQueues, setPurgingQueues] = useState<Set<string>>(new Set());
  const [actionNotice, setActionNotice] = useState<{
    id: number;
    tone: "info" | "danger";
    message: string;
  } | null>(null);

  const loadOverview = useCallback(async (silent: boolean) => {
    if (silent) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      const payload = await getQueuesOverview();
      setOverview(payload);
    } catch (loadError) {
      const message =
        loadError instanceof Error ? loadError.message : "Unexpected error while loading queues";
      setError(message);
    } finally {
      if (silent) {
        setRefreshing(false);
      } else {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadOverview(false);
  }, [loadOverview]);

  useEffect(() => {
    const timerId = window.setInterval(() => {
      void loadOverview(true);
    }, REFRESH_INTERVAL_MS);
    return () => {
      window.clearInterval(timerId);
    };
  }, [loadOverview]);

  const queueItems = useMemo(
    () => sortQueuesByPriority(overview?.items ?? []),
    [overview?.items],
  );
  const blockedQueues = overview?.blocked_queues ?? 0;

  const handlePurgeQueue = useCallback(
    async (queueName: string) => {
      const shouldPurge = window.confirm(
        `Purger complètement la file '${queueName}' ? Cette action est destructive.`,
      );
      if (!shouldPurge) {
        return;
      }

      setPurgingQueues((current) => {
        const next = new Set(current);
        next.add(queueName);
        return next;
      });

      try {
        const result = await purgeTaskQueue(queueName);
        setActionNotice({
          id: Date.now(),
          tone: "info",
          message: result.deleted
            ? `Queue '${result.queue_name}' purgée avec succès.`
            : `Queue '${result.queue_name}' déjà vide ou absente.`,
        });
        await loadOverview(true);
      } catch (purgeError) {
        const message =
          purgeError instanceof Error ? purgeError.message : "Unable to purge queue";
        setActionNotice({
          id: Date.now(),
          tone: "danger",
          message: `Purge échouée pour '${queueName}': ${message}`,
        });
      } finally {
        setPurgingQueues((current) => {
          const next = new Set(current);
          next.delete(queueName);
          return next;
        });
      }
    },
    [loadOverview],
  );

  return (
    <PageShell size="wide" className={styles.main}>
      <PageHeader
        title="Postgres Queues"
        description="Visualisez les files SQL, repérez les tâches bloquées et les workers inactifs."
      />

      <Surface className={styles.toolbar} padding="sm">
        <div className={styles.meta}>
          <p>Queues: {formatInteger(queueItems.length)}</p>
          <p>Blocked: {formatInteger(blockedQueues)}</p>
          <p>
            Queue backend status:{" "}
            <strong>{overview?.queue_backend_available === false ? "unavailable" : "available"}</strong>
          </p>
          <p>
            Updated at: <strong>{formatSourceDate(overview?.generated_at ?? null, "full")}</strong>
          </p>
        </div>
        <Button
          variant="secondary"
          onClick={() => void loadOverview(true)}
          disabled={loading || refreshing}
        >
          {refreshing ? "Refreshing..." : "Refresh"}
        </Button>
      </Surface>

      {error ? <Notice tone="danger">{error}</Notice> : null}
      {overview?.queue_backend_error ? (
        <Notice tone="warning">{overview.queue_backend_error}</Notice>
      ) : null}
      {actionNotice ? (
        <Notice key={actionNotice.id} tone={actionNotice.tone}>
          {actionNotice.message}
        </Notice>
      ) : null}

      {loading && overview === null ? (
        <Surface padding="sm">
          <p className={styles.placeholder}>Loading queues overview...</p>
        </Surface>
      ) : null}

      <section className={styles.streamGrid}>
        {queueItems.map((queue) => (
          <Surface key={queue.queue_name} className={styles.streamCard}>
            <header className={styles.streamHeader}>
              <div className={styles.streamIdentity}>
                <h2>{queue.queue_name}</h2>
                <p>{queue.purpose}</p>
              </div>
              <div className={styles.headerActions}>
                <div className={styles.badges}>
                  <Badge tone={queue.blocked ? "danger" : "success"} uppercase>
                    {queue.blocked ? "blocked" : "ok"}
                  </Badge>
                  <Badge tone={queue.queue_exists ? "accent" : "warning"} uppercase>
                    {queue.queue_exists ? "active" : "idle"}
                  </Badge>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={purgingQueues.has(queue.queue_name)}
                  onClick={() => void handlePurgeQueue(queue.queue_name)}
                >
                  {purgingQueues.has(queue.queue_name) ? "Purging..." : "Purge queue"}
                </Button>
              </div>
            </header>

            <section className={styles.kpiGrid}>
              <article className={styles.kpiItem}>
                <p className={styles.kpiLabel}>Queue length</p>
                <p className={styles.kpiValue}>{formatInteger(queue.queue_length)}</p>
              </article>
              <article className={styles.kpiItem}>
                <p className={styles.kpiLabel}>Queued tasks</p>
                <p className={styles.kpiValue}>{formatInteger(queue.queued_tasks)}</p>
              </article>
              <article className={styles.kpiItem}>
                <p className={styles.kpiLabel}>Processing tasks</p>
                <p className={styles.kpiValue}>{formatInteger(queue.processing_tasks)}</p>
              </article>
              <article className={styles.kpiItem}>
                <p className={styles.kpiLabel}>Last task</p>
                <p className={styles.kpiValue}>{queue.last_task_id ?? "n/a"}</p>
              </article>
            </section>

            {queue.blocked_reasons.length > 0 ? (
              <section className={styles.sectionBlock}>
                <h3>Blocking reasons</h3>
                {queue.blocked_reasons.map((reason, index) => (
                  <Notice key={`${queue.queue_name}-reason-${index}`} tone="warning">
                    {reason}
                  </Notice>
                ))}
              </section>
            ) : null}

            {queue.error ? (
              <section className={styles.sectionBlock}>
                <Notice tone="danger">{queue.error}</Notice>
              </section>
            ) : null}

            <section className={styles.sectionBlock}>
              <h3>Workers</h3>
              {queue.workers.length === 0 ? (
                <p className={styles.placeholder}>No worker detected on this queue.</p>
              ) : (
                <div className={styles.groupGrid}>
                  <article className={styles.groupCard}>
                    <header className={styles.groupHeader}>
                      <h4>{queue.worker_type}</h4>
                      <Badge tone={queue.blocked ? "danger" : "success"} uppercase>
                        {queue.blocked ? "blocked" : "ok"}
                      </Badge>
                    </header>

                    <div className={styles.groupStats}>
                      <p>Workers: {formatInteger(queue.workers.length)}</p>
                      <p>Connected: {formatInteger(queue.connected_workers)}</p>
                      <p>Active: {formatInteger(queue.active_workers)}</p>
                    </div>

                    <div className={styles.tableWrap}>
                      <table className={styles.table}>
                        <thead>
                          <tr>
                            <th>Worker</th>
                            <th>Processing</th>
                            <th>Idle</th>
                            <th>Connected</th>
                            <th>Active</th>
                          </tr>
                        </thead>
                        <tbody>
                          {queue.workers.map((worker) => (
                            <tr key={worker.name}>
                              <td>{worker.name}</td>
                              <td>{formatInteger(worker.processing_tasks)}</td>
                              <td>{formatIdleDuration(worker.idle_ms)}</td>
                              <td>
                                <Badge tone={worker.connected ? "success" : "danger"}>
                                  {worker.connected ? "yes" : "no"}
                                </Badge>
                              </td>
                              <td>
                                <Badge tone={worker.active ? "accent" : "warning"}>
                                  {worker.active ? "yes" : "no"}
                                </Badge>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </article>
                </div>
              )}
            </section>

            {queue.leased_tasks.length > 0 ? (
              <section className={styles.sectionBlock}>
                <h3>Stuck task leases</h3>
                <div className={styles.tableWrap}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th>Task</th>
                        <th>Worker</th>
                        <th>Idle</th>
                        <th>Attempts</th>
                      </tr>
                    </thead>
                    <tbody>
                      {queue.leased_tasks.map((taskLease) => (
                        <tr key={taskLease.task_id}>
                          <td>{taskLease.task_id}</td>
                          <td>{taskLease.worker_name ?? "n/a"}</td>
                          <td>{formatIdleDuration(taskLease.idle_ms)}</td>
                          <td>{formatInteger(taskLease.attempts)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            ) : null}
          </Surface>
        ))}
      </section>
    </PageShell>
  );
}
