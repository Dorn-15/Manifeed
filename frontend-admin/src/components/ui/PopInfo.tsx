"use client";

import { useEffect, useState } from "react";

import styles from "./PopInfo.module.css";

export type PopInfoType = "info" | "alert" | "success" | "warning";

type PopInfoProps = {
  title: string;
  text: string;
  type?: PopInfoType;
  durationMs?: number;
  onClose?: () => void;
};

export function PopInfo({
  title,
  text,
  type = "info",
  durationMs = 5000,
  onClose,
}: PopInfoProps) {
  const [visible, setVisible] = useState<boolean>(true);

  useEffect(() => {
    setVisible(true);
    const timeoutId = window.setTimeout(() => {
      setVisible(false);
      onClose?.();
    }, durationMs);

    return () => window.clearTimeout(timeoutId);
  }, [durationMs, onClose]);

  if (!visible) {
    return null;
  }

  return (
    <aside
      className={`${styles.popInfo} ${styles[type]}`}
      role={type === "alert" ? "alert" : "status"}
      aria-live={type === "alert" ? "assertive" : "polite"}
    >
      <h2>{title}</h2>
      <p>{text}</p>
    </aside>
  );
}
