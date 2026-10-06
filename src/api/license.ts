import ports from "../../config/ports.json";
import { secureGet, secureRemove, secureSet } from "../lib/secureStore";

export interface LicenseUser {
  id: number;
  email: string;
  is_admin: boolean;
  status: string;
  expires_at: string | null;
  licensed: boolean;
  created_at?: string | null;
}

export interface LicenseAuthResult {
  access_token: string;
  token_type: string;
  user: LicenseUser;
}

const TOKEN_KEY = "paperwing_license_token";
const USER_KEY = "paperwing_license_user";
const LEGACY_BASE_KEY = "paperwing_license_api_base";

const FALLBACK_LICENSE_API_BASE = `http://${ports.license.host}:${ports.license.port}`;

/**
 * 授权服务地址写死在构建配置，不开放给用户填写。
 * 开发：默认本机；发行：在 .env.production 设置 VITE_LICENSE_API_BASE=https://你的域名
 */
function resolveLicenseApiBase(): string {
  const fromEnv =
    typeof import.meta !== "undefined"
      ? (import.meta as { env?: { VITE_LICENSE_API_BASE?: string } }).env?.VITE_LICENSE_API_BASE
      : undefined;
  const raw = (fromEnv || FALLBACK_LICENSE_API_BASE).trim();
  return raw.replace(/\/$/, "");
}

export const LICENSE_API_BASE = resolveLicenseApiBase();

export function getLicenseApiBase(): string {
  return LICENSE_API_BASE;
}

/** 清除旧版可写死的 localStorage 覆盖，避免被改地址 */
export function purgeLegacyLicenseOverrides(): void {
  try {
    localStorage.removeItem(LEGACY_BASE_KEY);
  } catch {
    /* ignore */
  }
}

let memoryToken: string | null = null;
let memoryUser: LicenseUser | null = null;
let sessionReady: Promise<void> | null = null;

export function hydrateLicenseSession(): Promise<void> {
  if (!sessionReady) {
    sessionReady = (async () => {
      purgeLegacyLicenseOverrides();
      memoryToken = await secureGet(TOKEN_KEY);
      const rawUser = await secureGet(USER_KEY);
      if (rawUser) {
        try {
          memoryUser = JSON.parse(rawUser) as LicenseUser;
        } catch {
          memoryUser = null;
        }
      }
      // 明文迁移为加密
      if (memoryToken && localStorage.getItem(TOKEN_KEY)?.startsWith("pwenc:") === false) {
        await secureSet(TOKEN_KEY, memoryToken);
      }
      if (rawUser && localStorage.getItem(USER_KEY)?.startsWith("pwenc:") === false) {
        await secureSet(USER_KEY, rawUser);
      }
    })();
  }
  return sessionReady;
}

export function getLicenseToken(): string | null {
  return memoryToken;
}

export function getCachedLicenseUser(): LicenseUser | null {
  return memoryUser;
}

export async function clearLicenseSession(): Promise<void> {
  memoryToken = null;
  memoryUser = null;
  secureRemove(TOKEN_KEY);
  secureRemove(USER_KEY);
}

async function saveSession(token: string, user: LicenseUser): Promise<void> {
  memoryToken = token;
  memoryUser = user;
  await secureSet(TOKEN_KEY, token);
  await secureSet(USER_KEY, JSON.stringify(user));
}

function deviceLabel(): string {
  const ua = navigator.userAgent.slice(0, 80);
  return `desktop:${ua}`;
}

async function licenseRequest<T>(path: string, options?: RequestInit): Promise<T> {
  await hydrateLicenseSession();
  const token = getLicenseToken();
  const response = await fetch(`${getLicenseApiBase()}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options?.headers ?? {}),
    },
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = (body as { detail?: unknown }).detail;
    let message = "授权服务请求失败";
    if (typeof detail === "string") message = detail;
    else if (Array.isArray(detail)) {
      message = detail.map((item: { msg?: string }) => item.msg ?? String(item)).join("; ");
    }
    const err = new Error(message) as Error & { status?: number; kicked?: boolean };
    err.status = response.status;
    err.kicked = message === "kicked" || response.headers.get("X-License-Status") === "kicked";
    throw err;
  }
  return body as T;
}

export const licenseApi = {
  health: () => licenseRequest<{ status: string }>("/health"),
  sendCode: (email: string, purpose: "register" | "reset") =>
    licenseRequest<{ success: boolean; message: string; cooldown_seconds: number }>(
      "/auth/send-code",
      {
        method: "POST",
        body: JSON.stringify({ email, purpose }),
      },
    ),
  register: (email: string, password: string, emailCode: string) =>
    licenseRequest<LicenseAuthResult>("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        email,
        password,
        email_code: emailCode,
        device_label: deviceLabel(),
      }),
    }).then(async (r) => {
      await saveSession(r.access_token, r.user);
      return r;
    }),
  resetPassword: (email: string, emailCode: string, newPassword: string) =>
    licenseRequest<{ success: boolean; message: string }>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({
        email,
        email_code: emailCode,
        new_password: newPassword,
      }),
    }),
  changePassword: (payload: {
    newPassword: string;
    oldPassword?: string;
    emailCode?: string;
  }) =>
    licenseRequest<{ success: boolean; message: string }>("/auth/change-password", {
      method: "POST",
      body: JSON.stringify({
        new_password: payload.newPassword,
        old_password: payload.oldPassword || null,
        email_code: payload.emailCode || null,
      }),
    }),
  login: (email: string, password: string) =>
    licenseRequest<LicenseAuthResult>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password, device_label: deviceLabel() }),
    }).then(async (r) => {
      await saveSession(r.access_token, r.user);
      return r;
    }),
  logout: async () => {
    try {
      await licenseRequest("/auth/logout", { method: "POST", body: "{}" });
    } finally {
      await clearLicenseSession();
    }
  },
  me: () =>
    licenseRequest<LicenseUser>("/auth/me").then(async (user) => {
      memoryUser = user;
      await secureSet(USER_KEY, JSON.stringify(user));
      return user;
    }),
  heartbeat: () =>
    licenseRequest<{ ok: boolean; kicked: boolean; user: LicenseUser }>("/auth/heartbeat", {
      method: "POST",
      body: JSON.stringify({ device_label: deviceLabel() }),
    }).then(async (r) => {
      if (r.user) {
        memoryUser = r.user;
        await secureSet(USER_KEY, JSON.stringify(r.user));
      }
      return r;
    }),
  redeem: (code: string) =>
    licenseRequest<{ success: boolean; user: LicenseUser }>("/license/redeem", {
      method: "POST",
      body: JSON.stringify({ code }),
    }).then(async (r) => {
      if (r.user) {
        memoryUser = r.user;
        await secureSet(USER_KEY, JSON.stringify(r.user));
      }
      return r;
    }),
  verify: () =>
    licenseRequest<{ ok: boolean; kicked: boolean; licensed: boolean; user: LicenseUser }>(
      "/license/verify",
      { method: "POST" },
    ),
};
