import { Badge, Surface } from "@/components";
import type { HealthRead } from "@/types/health";

import styles from "./HealthStatusCard.module.css";

type HealthStatusCardProps = {
  statusText: string;
  health: HealthRead | null;
};

export function HealthStatusCard({ statusText, health }: HealthStatusCardProps) {
  const isHealthy = statusText.toLowerCase() === "ok";

  return (
    <Surface className={styles.card} padding="lg">
      <header className={styles.header}>
        <h2>Backend Health</h2>
        <Badge tone={isHealthy ? "success" : "warning"} uppercase>
          {isHealthy ? "Stable" : "Check"}
        </Badge>
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
    </Surface>
  );
}
