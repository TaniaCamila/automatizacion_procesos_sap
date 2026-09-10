import type { ReactNode } from "react";
import { Breadcrumb } from "../navigation/Breadcrumb";
import {
  WelcomeHeader,
  type WelcomeHeaderMetaItem,
} from "../ui/WelcomeHeader";
import { PageContainer } from "./PageContainer";
import styles from "./PageScaffold.module.css";

interface PageScaffoldProps {
  title: string;
  subtitle?: string;
  description?: string;
  meta?: WelcomeHeaderMetaItem[];
  lastUpdate?: string;
  showClock?: boolean;
  actions?: ReactNode;
  children: ReactNode;
  narrow?: boolean;
}

/** Common semantic structure for every application page. */
export function PageScaffold({
  title,
  subtitle,
  description,
  meta,
  lastUpdate,
  showClock,
  actions,
  children,
  narrow,
}: PageScaffoldProps) {
  return (
    <PageContainer narrow={narrow}>
      <Breadcrumb />
      <div className={styles.page}>
        <WelcomeHeader
          title={title}
          subtitle={subtitle}
          description={description}
          meta={meta}
          lastUpdate={lastUpdate}
          showClock={showClock}
          actions={actions}
        />
        {children}
      </div>
    </PageContainer>
  );
}
