import {
  useCallback,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type {
  AppNotification,
  NotificationContextValue,
  NotificationType,
} from "../types/notification";
import { NotificationContext } from "./NotificationContext";

interface NotificationProviderProps {
  children: ReactNode;
}

export function NotificationProvider({
  children,
}: NotificationProviderProps) {
  const [notifications, setNotifications] = useState<AppNotification[]>([]);

  const notify = useCallback(
    (type: NotificationType, message: string, title?: string) => {
      const id = crypto.randomUUID();
      setNotifications((current) => [
        ...current,
        { id, type, message, title, createdAt: Date.now() },
      ]);
      return id;
    },
    [],
  );

  const dismiss = useCallback((id: string) => {
    setNotifications((current) =>
      current.filter((notification) => notification.id !== id),
    );
  }, []);

  const clear = useCallback(() => setNotifications([]), []);

  const value = useMemo<NotificationContextValue>(
    () => ({ notifications, notify, dismiss, clear }),
    [clear, dismiss, notifications, notify],
  );

  return (
    <NotificationContext.Provider value={value}>
      {children}
    </NotificationContext.Provider>
  );
}
