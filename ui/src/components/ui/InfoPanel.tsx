import styles from "./InfoPanel.module.css";
import type {
  InfoPanelItem,
  InfoPanelItemType,
} from "../../types/data-display";
import { Surface } from "./Surface";

interface InfoPanelProps {
  title?: string;
  items: InfoPanelItem[];
  headingLevel?: "h2" | "h3" | "h4";
}

const TYPE_LABEL: Record<InfoPanelItemType, string> = {
  info: "Info",
  alert: "Alerta",
  change: "Cambio",
  roadmap: "Roadmap",
  sprint: "Sprint",
  news: "Noticia",
  admin: "Admin",
};

/**
 * Generic information panel — content fully driven by `items` props.
 */
export function InfoPanel({
  title = "Información",
  items,
  headingLevel = "h2",
}: InfoPanelProps) {
  const Heading = headingLevel;
  const ItemHeading =
    headingLevel === "h2" ? "h3" : headingLevel === "h3" ? "h4" : "h5";

  return (
    <Surface as="section" className={styles.panel}>
      <header className={styles.header}>
        <Heading className={styles.title}>{title}</Heading>
      </header>
      <ul className={styles.list}>
        {items.map((item) => (
          <li key={item.id} className={styles.item}>
            <div className={styles.itemHead}>
              <span className={`${styles.tag} ${styles[item.type]}`}>
                {TYPE_LABEL[item.type]}
              </span>
              {item.date ? <time className={styles.date}>{item.date}</time> : null}
            </div>
            <ItemHeading className={styles.itemTitle}>{item.title}</ItemHeading>
            <p className={styles.itemDescription}>{item.description}</p>
          </li>
        ))}
      </ul>
    </Surface>
  );
}
