import type { HTMLAttributes } from "react";

import { cx } from "../../lib/cx";
import styles from "./Surface.module.css";

type SurfaceTone = "default" | "soft" | "gradient";
type SurfacePadding = "none" | "sm" | "md" | "lg";
type SurfaceElement = "section" | "article" | "aside" | "div" | "header" | "footer";

type SurfaceProps = HTMLAttributes<HTMLElement> & {
  as?: SurfaceElement;
  tone?: SurfaceTone;
  padding?: SurfacePadding;
  blur?: boolean;
};

export function Surface({
  as = "section",
  tone = "default",
  padding = "md",
  blur = true,
  className,
  children,
  ...rest
}: SurfaceProps) {
  const Component = as;

  return (
    <Component
      className={cx(
        styles.surface,
        styles[`tone_${tone}`],
        styles[`padding_${padding}`],
        blur && styles.blur,
        className,
      )}
      {...rest}
    >
      {children}
    </Component>
  );
}
