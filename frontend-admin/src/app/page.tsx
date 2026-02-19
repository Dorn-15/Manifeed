"use client";

import { PageHeader, PageShell } from "@/components";
import { HealthStatusCard } from "@/features/health/components/HealthStatusCard";
import { useHealthStatus } from "@/features/health/hooks/useHealthStatus";

import styles from "./page.module.css";

export default function AdminHomePage() {
  const { health, statusText } = useHealthStatus();

  return (
    <PageShell size="wide" className={styles.main}>
      <PageHeader
        title="RSS Control Studio"
        description="Monitor source quality, synchronization, and API availability from one place."
      />

      <section className={styles.panelGrid}>
        <HealthStatusCard statusText={statusText} health={health} />
      </section>
    </PageShell>
  );
}
