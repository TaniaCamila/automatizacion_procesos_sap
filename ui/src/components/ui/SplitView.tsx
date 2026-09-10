import type { ReactNode } from "react";
import { Surface } from "./Surface";
import styles from "./SplitView.module.css";

interface SplitViewProps {
  left: ReactNode;
  right: ReactNode;
  /** Left pane percentage. Default 60 (enterprise report layout). */
  leftRatio?: number;
}

export function SplitView({ left, right, leftRatio = 60 }: SplitViewProps) {
  const rightRatio = 100 - leftRatio;

  return (
    <Surface className={styles.split}>
      <div className={styles.pane} style={{ flexBasis: `${leftRatio}%` }}>
        {left}
      </div>
      <div className={styles.divider} aria-hidden />
      <div className={styles.pane} style={{ flexBasis: `${rightRatio}%` }}>
        {right}
      </div>
    </Surface>
  );
}
