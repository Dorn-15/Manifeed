import type { ReactNode } from "react";

import { cx } from "../../lib/cx";
import { Surface } from "../../primitives/surface/Surface";
import styles from "./PageHeader.module.css";

type PageHeaderProps = {
  title: string;
  description?: string;
  className?: string;
  sideContent?: ReactNode;
};

export function PageHeader({
  title,
  description,
  className,
  sideContent,
}: PageHeaderProps) {
  return (
    <Surface as="header" className={cx(styles.header, className)} tone="gradient" padding="lg">
      <div className={styles.content}>
        <h1>{title}</h1>
        {description ? <p className={styles.description}>{description}</p> : null}
      </div>
      {sideContent ? <div className={styles.sideContent}>{sideContent}</div> : null}
    </Surface>
  );
}
