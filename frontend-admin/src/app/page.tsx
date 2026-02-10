"use client";

import Link from "next/link";

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
        <p>
          Premium interface to monitor source quality, synchronization, and API availability.
        </p>
        <div className={styles.heroActions}>
          <Link className={styles.primaryAction} href="/rss">
            Open RSS feed cards
          </Link>
        </div>
      </section>

      <section className={styles.panelGrid}>
        <HealthStatusCard statusText={statusText} health={health} />
      </section>
    </main>
  );
}
