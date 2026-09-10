export type NotificationType = "success" | "warning" | "error" | "info";

export interface AppNotification {
  id: string;
  type: NotificationType;
  message: string;
  title?: string;
  createdAt: number;
}

export interface NotificationContextValue {
  notifications: AppNotification[];
  notify: (
    type: NotificationType,
    message: string,
    title?: string,
  ) => string;
  dismiss: (id: string) => void;
  clear: () => void;
}
