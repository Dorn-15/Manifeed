import type { HealthRead } from "@/types/health";

import styles from "./HealthStatusCard.module.css";

type HealthStatusCardProps = {
  statusText: string;
  health: HealthRead | null;
};

export function HealthStatusCard({ statusText, health }: HealthStatusCardProps) {
  const isHealthy = statusText.toLowerCase() === "ok";

  return (
    <section className={styles.card}>
      <header className={styles.header}>
        <h2>Backend Health</h2>
        <span className={isHealthy ? styles.statusPillHealthy : styles.statusPillWarning}>
          {isHealthy ? "Stable" : "Check"}
        </span>
      </header>

      <div className={styles.grid}>
        <article className={styles.metric}>
          <span>API status</span>
          <strong>{statusText}</strong>
        </article>
        <article className={styles.metric}>
          <span>Database</span>
          <strong>{health?.database ?? "unknown"}</strong>
        </article>
      </div>
    </section>
  );
}
