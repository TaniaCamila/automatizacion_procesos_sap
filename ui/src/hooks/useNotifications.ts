import { useContext } from "react";
import { NotificationContext } from "../providers/NotificationContext";

export function useNotifications() {
  const context = useContext(NotificationContext);

  if (!context) {
    throw new Error(
      "useNotifications must be used inside NotificationProvider.",
    );
  }

  return context;
}
