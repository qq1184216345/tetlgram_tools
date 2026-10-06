import { createContext, useCallback, useContext, useEffect, useMemo, useState, ReactNode } from "react";
import {
  clearLicenseSession,
  getCachedLicenseUser,
  getLicenseToken,
  hydrateLicenseSession,
  licenseApi,
  LicenseUser,
} from "../api/license";
import { api } from "../api/client";

type LicensePhase = "loading" | "need_login" | "need_license" | "ready" | "kicked";

interface LicenseContextValue {
  phase: LicensePhase;
  user: LicenseUser | null;
  error: string;
  refresh: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, emailCode: string) => Promise<void>;
  sendCode: (email: string, purpose: "register" | "reset") => Promise<void>;
  resetPassword: (email: string, emailCode: string, newPassword: string) => Promise<void>;
  redeem: (code: string) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}

const LicenseContext = createContext<LicenseContextValue | null>(null);

async function syncLocalGate(token: string | null, user: LicenseUser | null): Promise<void> {
  try {
    await api.reportLicenseStatus({
      token: token || "",
      email: user?.email || "",
      expires_at: user?.expires_at || null,
      licensed: Boolean(user?.licensed),
      checked_at: new Date().toISOString(),
    });
  } catch {
    // 本地后端未启动时忽略
  }
}

export function LicenseProvider({ children }: { children: ReactNode }) {
  const [phase, setPhase] = useState<LicensePhase>("loading");
  const [user, setUser] = useState<LicenseUser | null>(null);
  const [error, setError] = useState("");

  const applyUser = useCallback(async (next: LicenseUser | null) => {
    setUser(next);
    const token = getLicenseToken();
    await syncLocalGate(token, next);
    if (!next || !token) {
      setPhase("need_login");
      return;
    }
    if (next.status === "banned") {
      setPhase("need_login");
      setError("账号已被封禁");
      await clearLicenseSession();
      return;
    }
    if (!next.licensed) {
      setPhase("need_license");
      return;
    }
    setPhase("ready");
  }, []);

  const refresh = useCallback(async () => {
    await hydrateLicenseSession();
    const token = getLicenseToken();
    if (!token) {
      await applyUser(null);
      return;
    }
    setUser(getCachedLicenseUser());
    try {
      const me = await licenseApi.me();
      await applyUser(me);
      setError("");
    } catch (e) {
      const err = e as Error & { kicked?: boolean };
      if (err.kicked || err.message === "kicked") {
        await clearLicenseSession();
        setPhase("kicked");
        setUser(null);
        setError("账号已在其他设备登录");
        await syncLocalGate(null, null);
        return;
      }
      // 断网：若本地有缓存且曾授权，交给本地 gate 宽限；前端暂保持缓存态
      const cached = getCachedLicenseUser();
      if (cached?.licensed) {
        setUser(cached);
        setPhase("ready");
        setError("授权服务暂时不可达，进入离线宽限期");
        return;
      }
      await clearLicenseSession();
      setPhase("need_login");
      setError(err.message || "请重新登录");
    }
  }, [applyUser]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (phase !== "ready" && phase !== "need_license") return;
    const timer = setInterval(async () => {
      try {
        const hb = await licenseApi.heartbeat();
        await applyUser(hb.user);
      } catch (e) {
        const err = e as Error & { kicked?: boolean };
        if (err.kicked || err.message === "kicked") {
          await clearLicenseSession();
          setPhase("kicked");
          setUser(null);
          setError("账号已在其他设备登录");
          await syncLocalGate(null, null);
        }
      }
    }, 5 * 60 * 1000);
    return () => clearInterval(timer);
  }, [phase, applyUser]);

  const login = useCallback(
    async (email: string, password: string) => {
      setError("");
      const r = await licenseApi.login(email, password);
      await applyUser(r.user);
    },
    [applyUser],
  );

  const register = useCallback(
    async (email: string, password: string, emailCode: string) => {
      setError("");
      const r = await licenseApi.register(email, password, emailCode);
      await applyUser(r.user);
    },
    [applyUser],
  );

  const sendCode = useCallback(async (email: string, purpose: "register" | "reset") => {
    setError("");
    await licenseApi.sendCode(email, purpose);
  }, []);

  const resetPassword = useCallback(
    async (email: string, emailCode: string, newPassword: string) => {
      setError("");
      await licenseApi.resetPassword(email, emailCode, newPassword);
    },
    [],
  );

  const redeem = useCallback(
    async (code: string) => {
      setError("");
      const r = await licenseApi.redeem(code);
      await applyUser(r.user);
    },
    [applyUser],
  );

  const logout = useCallback(async () => {
    await licenseApi.logout();
    await applyUser(null);
    setError("");
  }, [applyUser]);

  const value = useMemo(
    () => ({
      phase,
      user,
      error,
      refresh,
      login,
      register,
      sendCode,
      resetPassword,
      redeem,
      logout,
      clearError: () => setError(""),
    }),
    [phase, user, error, refresh, login, register, sendCode, resetPassword, redeem, logout],
  );

  return <LicenseContext.Provider value={value}>{children}</LicenseContext.Provider>;
}

export function useLicense(): LicenseContextValue {
  const ctx = useContext(LicenseContext);
  if (!ctx) throw new Error("useLicense must be used within LicenseProvider");
  return ctx;
}
