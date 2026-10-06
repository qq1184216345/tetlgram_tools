import { FormEvent, ReactNode, useEffect, useState } from "react";
import logo from "../assets/logo.png";
import { useLicense } from "../context/LicenseContext";

type AuthMode = "login" | "register" | "reset";

export function LicenseGate() {
  const {
    phase,
    user,
    error,
    login,
    register,
    sendCode,
    resetPassword,
    redeem,
    logout,
    clearError,
  } = useLicense();
  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [emailCode, setEmailCode] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState("");
  const [localOk, setLocalOk] = useState("");
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [cooldown]);

  function switchMode(next: AuthMode) {
    setMode(next);
    setLocalError("");
    setLocalOk("");
    clearError();
  }

  async function handleSendCode() {
    setLocalError("");
    setLocalOk("");
    clearError();
    if (!email.trim()) {
      setLocalError("请先填写邮箱");
      return;
    }
    setBusy(true);
    try {
      await sendCode(email.trim(), mode === "reset" ? "reset" : "register");
      setCooldown(60);
      setLocalOk("验证码已发送，请查收邮箱");
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "发送失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleAuth(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setLocalError("");
    setLocalOk("");
    clearError();
    try {
      if (mode === "login") {
        await login(email.trim(), password);
      } else if (mode === "register") {
        await register(email.trim(), password, emailCode.trim());
      } else {
        await resetPassword(email.trim(), emailCode.trim(), password);
        setLocalOk("密码已重置，请登录");
        setMode("login");
        setPassword("");
        setEmailCode("");
      }
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "操作失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleRedeem(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setLocalError("");
    clearError();
    try {
      await redeem(code.trim());
      setCode("");
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "激活失败");
    } finally {
      setBusy(false);
    }
  }

  const shell = (body: ReactNode) => (
    <div className="license-gate">
      <div className="license-atmosphere" aria-hidden>
        <span className="license-orb license-orb-a" />
        <span className="license-orb license-orb-b" />
        <span className="license-grain" />
      </div>
      <div className="license-panel">{body}</div>
    </div>
  );

  if (phase === "loading") {
    return shell(
      <>
        <div className="license-brand">
          <img src={logo} alt="纸翼" className="license-logo" />
          <div>
            <h1>纸翼</h1>
            <p>正在校验授权…</p>
          </div>
        </div>
        <div className="license-loading-bar" aria-hidden />
      </>,
    );
  }

  if (phase === "need_license" || (phase === "ready" && user && !user.licensed)) {
    return shell(
      <>
        <div className="license-brand">
          <img src={logo} alt="纸翼" className="license-logo" />
          <div>
            <h1>激活授权</h1>
            <p>账号 {user?.email} 尚未开通有效期</p>
          </div>
        </div>
        <form onSubmit={handleRedeem} className="license-form">
          <label>
            卡密
            <input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="PW-XXXX-XXXX-XXXX"
              required
              autoComplete="off"
            />
          </label>
          {(localError || error) && <p className="error">{localError || error}</p>}
          <div className="button-row">
            <button type="submit" className="license-primary" disabled={busy}>
              激活
            </button>
            <button type="button" className="license-ghost" disabled={busy} onClick={() => void logout()}>
              退出登录
            </button>
          </div>
        </form>
      </>,
    );
  }

  if (phase === "kicked" || phase === "need_login") {
    return shell(
      <>
        <div className="license-brand">
          <img src={logo} alt="纸翼" className="license-logo" />
          <div>
            <h1>纸翼</h1>
            <p>{phase === "kicked" ? "账号已在其他设备登录，请重新登录" : "登录后继续使用"}</p>
          </div>
        </div>

        <div className="license-mode-tabs" role="tablist">
          {(
            [
              ["login", "登录"],
              ["register", "注册"],
              ["reset", "找回密码"],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={mode === key}
              className={mode === key ? "active" : ""}
              onClick={() => switchMode(key)}
            >
              {label}
            </button>
          ))}
        </div>

        <form onSubmit={handleAuth} className="license-form">
          <label>
            邮箱
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="username"
              placeholder="name@example.com"
            />
          </label>
          {(mode === "register" || mode === "reset") && (
            <label>
              邮箱验证码
              <div className="code-row">
                <input
                  value={emailCode}
                  onChange={(e) => setEmailCode(e.target.value)}
                  placeholder="6 位验证码"
                  required
                  maxLength={16}
                  autoComplete="one-time-code"
                />
                <button
                  type="button"
                  className="license-ghost code-btn"
                  disabled={busy || cooldown > 0}
                  onClick={() => void handleSendCode()}
                >
                  {cooldown > 0 ? `${cooldown}s` : "获取验证码"}
                </button>
              </div>
            </label>
          )}
          <label>
            {mode === "reset" ? "新密码" : "密码"}
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              placeholder="至少 6 位"
            />
          </label>
          {localOk && <p className="ok">{localOk}</p>}
          {(localError || error) && <p className="error">{localError || error}</p>}
          <button type="submit" className="license-primary" disabled={busy}>
            {busy ? "处理中…" : mode === "login" ? "登录" : mode === "register" ? "注册并登录" : "重置密码"}
          </button>
        </form>
      </>,
    );
  }

  return null;
}

export function formatExpiresAt(iso: string | null | undefined): string {
  if (!iso) return "未授权";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    const y = d.getFullYear();
    const m = d.getMonth() + 1;
    const day = d.getDate();
    const h = d.getHours();
    const min = d.getMinutes();
    const sec = d.getSeconds();
    return `${y}年${m}月${day}日${h}时${min}分${sec}秒`;
  } catch {
    return iso;
  }
}
