import type { HTMLAttributes } from "react";

import { cx } from "../../lib/cx";
import styles from "./EmptyState.module.css";

type EmptyStateProps = HTMLAttributes<HTMLElement> & {
  title: string;
  description: string;
};

export function EmptyState({ title, description, className, ...rest }: EmptyStateProps) {
  return (
    <section className={cx(styles.emptyState, className)} {...rest}>
      <h2>{title}</h2>
      <p>{description}</p>
    </section>
  );
}
