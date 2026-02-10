import type { HealthRead } from "@/types/health";

import styles from "./HealthOverview.module.css";

type HealthOverviewProps = {
  statusText: string;
  health: HealthRead | null;
};

export function HealthOverview({ statusText, health }: HealthOverviewProps) {
  return (
    <section className={styles.card}>
      <h2>System Health</h2>
      <div className={styles.metrics}>
        <article>
          <p className={styles.label}>API status</p>
          <p className={styles.value}>{statusText}</p>
        </article>
        <article>
          <p className={styles.label}>Database</p>
          <p className={styles.value}>{health?.database ?? "unknown"}</p>
        </article>
      </div>
    </section>
  );
}
