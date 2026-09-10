import styles from "./DataGrid.module.css";
import type { DataGridColumn } from "../../types/data-display";
import { Surface } from "./Surface";

interface DataGridProps {
  columns: DataGridColumn[];
  rows: Record<string, string>[];
  caption?: string;
  emptyMessage?: string;
}

/** Generic tabular surface — reusable for any report. */
export function DataGrid({
  columns,
  rows,
  caption,
  emptyMessage = "Sin datos para mostrar",
}: DataGridProps) {
  return (
    <Surface className={styles.wrap}>
      {caption ? <p className={styles.caption}>{caption}</p> : null}
      <div className={styles.scroll}>
        <table className={styles.table}>
          {caption ? <caption className="sr-only">{caption}</caption> : null}
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  scope="col"
                  className={col.align === "right" ? styles.right : undefined}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className={styles.empty}>
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              rows.map((row, index) => (
                <tr key={index}>
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={col.align === "right" ? styles.right : undefined}
                    >
                      {row[col.key] ?? "—"}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </Surface>
  );
}
