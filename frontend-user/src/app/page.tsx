"use client";

import { HealthOverview } from "@/features/health/components/HealthOverview";
import { useHealthStatus } from "@/features/health/hooks/useHealthStatus";

import styles from "./page.module.css";

export default function UserHomePage() {
  const { health, statusText } = useHealthStatus();

  return (
    <main className={styles.main}>
      <section className={styles.hero}>
        <p className={styles.kicker}>Manifeed</p>
        <h1>Reader Portal</h1>
        <p className={styles.lead}>Live availability of RSS ingestion services.</p>
      </section>

      <HealthOverview statusText={statusText} health={health} />
    </main>
  );
}
