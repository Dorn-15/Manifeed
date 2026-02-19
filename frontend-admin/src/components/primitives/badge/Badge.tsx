import type { HTMLAttributes } from "react";

import { cx } from "../../lib/cx";
import styles from "./Badge.module.css";

type BadgeTone = "neutral" | "accent" | "success" | "warning" | "danger";

type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  tone?: BadgeTone;
  uppercase?: boolean;
};

export function Badge({
  tone = "neutral",
  uppercase = false,
  className,
  children,
  ...rest
}: BadgeProps) {
  return (
    <span
      className={cx(styles.badge, styles[`tone_${tone}`], uppercase && styles.uppercase, className)}
      {...rest}
    >
      {children}
    </span>
  );
}
