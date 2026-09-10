import { useMemo, type ReactNode } from "react";
import { mockUser } from "../data/authMock";
import type { AuthContextValue } from "../types/auth";
import { AuthContext } from "./AuthContext";

interface AuthProviderProps {
  children: ReactNode;
}

/** Mock authentication seam. Replace its value source, not its consumers. */
export function AuthProvider({ children }: AuthProviderProps) {
  const value = useMemo<AuthContextValue>(
    () => ({
      user: mockUser,
      isAuthenticated: true,
      hasPermission: (permission) =>
        !permission || mockUser.permissions.includes(permission),
    }),
    [],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
