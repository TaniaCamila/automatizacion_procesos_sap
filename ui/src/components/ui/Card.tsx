import type { ReactNode } from "react";
import { Surface } from "./Surface";
import styles from "./Card.module.css";

interface CardProps {
  children: ReactNode;
  as?: "div" | "section" | "article" | "aside";
  className?: string;
  padding?: "sm" | "md" | "lg";
}

export function Card({
  children,
  as = "div",
  className = "",
  padding = "md",
}: CardProps) {
  return (
    <Surface
      as={as}
      className={`${styles.card} ${styles[`pad-${padding}`]} ${className}`}
    >
      {children}
    </Surface>
  );
}
