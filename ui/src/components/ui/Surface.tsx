import type { ReactNode } from "react";
import styles from "./Surface.module.css";

type SurfaceElement = "div" | "section" | "article" | "aside";
type SurfaceElevation = "none" | "sm" | "md";

interface SurfaceProps {
  children: ReactNode;
  as?: SurfaceElement;
  elevation?: SurfaceElevation;
  className?: string;
}

/** Lowest-level visual surface in the design system. */
export function Surface({
  children,
  as: Component = "div",
  elevation = "sm",
  className = "",
}: SurfaceProps) {
  return (
    <Component
      className={`${styles.surface} ${styles[elevation]} ${className}`}
    >
      {children}
    </Component>
  );
}
