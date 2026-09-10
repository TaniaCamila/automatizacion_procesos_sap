export type UserRole = "administrator" | "analyst" | "viewer";

export interface AuthUser {
  id: string;
  displayName: string;
  email: string;
  role: UserRole;
  permissions: string[];
}

export interface AuthContextValue {
  user: AuthUser;
  isAuthenticated: boolean;
  hasPermission: (permission?: string) => boolean;
}
