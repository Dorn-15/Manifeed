"use client";

import { HealthStatusCard } from "@/features/health/components/HealthStatusCard";
import { useHealthStatus } from "@/features/health/hooks/useHealthStatus";

import styles from "./page.module.css";

export default function AdminHomePage() {
  const { health, statusText } = useHealthStatus();

  return (
    <main className={styles.main}>
      <section className={styles.hero}>
        <div className={styles.heroTag}>Manifeed Admin</div>
        <h1>RSS Control Studio</h1>
        <p>Monitor source quality, synchronization, and API availability from one place.</p>
      </section>

      <section className={styles.panelGrid}>
        <HealthStatusCard statusText={statusText} health={health} />
      </section>
    </main>
  );
}
