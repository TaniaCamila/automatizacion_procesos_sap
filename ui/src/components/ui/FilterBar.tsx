import type { ReactNode } from "react";
import type { FilterField } from "../../types/data-display";
import { Button } from "./Button";
import { Surface } from "./Surface";
import styles from "./FilterBar.module.css";

interface FilterBarProps {
  fields?: FilterField[];
  actions?: ReactNode;
  disabled?: boolean;
}

/** Generic filter shell — fields are data-driven, no business rules. */
export function FilterBar({
  fields = [
    { id: "a", label: "Filtro A", placeholder: "Pendiente de configuración" },
    { id: "b", label: "Filtro B", placeholder: "Pendiente de configuración" },
    { id: "c", label: "Filtro C", placeholder: "Pendiente de configuración" },
  ],
  actions,
  disabled = true,
}: FilterBarProps) {
  return (
    <Surface className={styles.bar}>
      <div role="search" aria-label="Filtros" className={styles.inner}>
        <div className={styles.fields}>
          {fields.map((field) => (
            <label key={field.id} className={styles.field}>
              <span className={styles.label}>{field.label}</span>
              {field.type === "date" || field.type === "text" ? (
                <input
                  className={styles.control}
                  type={field.type === "date" ? "date" : "search"}
                  placeholder={
                    field.type === "text" ? field.placeholder : undefined
                  }
                  disabled={disabled}
                  defaultValue={field.defaultValue}
                />
              ) : (
                <select
                  className={styles.control}
                  disabled={disabled}
                  defaultValue={field.defaultValue ?? ""}
                >
                  <option value="">
                    {field.placeholder ?? "Seleccionar"}
                  </option>
                  {field.options?.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              )}
            </label>
          ))}
        </div>
        <div className={styles.actions}>
          {actions ?? (
            <>
              <Button variant="secondary" size="sm" disabled={disabled}>
                Restablecer
              </Button>
              <Button variant="primary" size="sm" disabled={disabled}>
                Aplicar
              </Button>
            </>
          )}
        </div>
      </div>
    </Surface>
  );
}
