import type { ReactNode } from "react";

interface PageContainerProps {
  children: ReactNode;
  narrow?: boolean;
}

export function PageContainer({ children, narrow = false }: PageContainerProps) {
  return (
    <div className={`page-container${narrow ? " page-container--narrow" : ""}`}>
      {children}
    </div>
  );
}
