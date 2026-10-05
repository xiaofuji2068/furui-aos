"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import {
  AuthUser, clearSession, fetchMe, getCachedUser, getToken,
  hasPerm as _hasPerm, login as apiLogin, logout as apiLogout,
} from "@/lib/api";

interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  hasPerm: (code: string) => boolean;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  // 启动时：有 token 就拉取真实用户信息，保证刷新页面后登录态不丢
  useEffect(() => {
    let alive = true;
    (async () => {
      if (!getToken()) {
        setLoading(false);
        return;
      }
      // 先用缓存渲染，避免白屏
      const cached = getCachedUser();
      if (cached) setUser(cached);
      try {
        const me = await fetchMe();
        if (alive) setUser(me);
      } catch {
        clearSession();
        if (alive) setUser(null);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const u = await apiLogin(username, password);
    setUser(u);
  }, []);

  const logout = useCallback(async () => {
    await apiLogout();
    setUser(null);
  }, []);

  const hasPerm = useCallback((code: string) => _hasPerm(user, code), [user]);

  return (
    <Ctx.Provider value={{ user, loading, login, logout, hasPerm }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth 必须在 <AuthProvider> 内使用");
  return ctx;
}
