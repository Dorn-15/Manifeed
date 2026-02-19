import type { HTMLAttributes } from "react";

import { cx } from "../../lib/cx";
import styles from "./Notice.module.css";

type NoticeTone = "neutral" | "info" | "warning" | "danger";

type NoticeProps = HTMLAttributes<HTMLParagraphElement> & {
  tone?: NoticeTone;
};

export function Notice({ tone = "neutral", className, children, ...rest }: NoticeProps) {
  return (
    <p className={cx(styles.notice, styles[`tone_${tone}`], className)} {...rest}>
      {children}
    </p>
  );
}
