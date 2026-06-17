import { createContext, useContext, useState, ReactNode } from "react";
import { api, getToken, setToken, clearToken } from "./api/client";

interface AuthContextValue {
  loggedIn: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loggedIn, setLoggedIn] = useState(!!getToken());

  async function login(username: string, password: string) {
    const res = await api.post<{ token: string }>("/api/auth/login", { username, password });
    setToken(res.token);
    setLoggedIn(true);
  }

  function logout() {
    api.post("/api/auth/logout").catch(() => undefined);
    clearToken();
    setLoggedIn(false);
  }

  return <AuthContext.Provider value={{ loggedIn, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
