import type { ReactNode } from "react";
import { SectionTitle } from "./SectionTitle";
import styles from "./Section.module.css";

interface SectionProps {
  id?: string;
  title: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}

/** Standard page section: semantic wrapper + reusable heading. */
export function Section({
  id,
  title,
  description,
  action,
  children,
  className = "",
}: SectionProps) {
  const titleId = id ? `${id}-title` : undefined;

  return (
    <section
      className={`${styles.section} ${className}`}
      aria-labelledby={titleId}
    >
      <SectionTitle
        id={titleId}
        title={title}
        description={description}
        action={action}
      />
      {children}
    </section>
  );
}
