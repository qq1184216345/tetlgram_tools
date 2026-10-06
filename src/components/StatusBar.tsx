import { FormEvent, useEffect, useRef, useState } from "react";
import { useLicense } from "../context/LicenseContext";
import { useToast } from "../context/ToastContext";
import { licenseApi } from "../api/license";

interface StatusBarProps {
  backendOnline: boolean;
  accountCount: number;
  version: string;
  expiresAtLabel?: string;
}

type PwdMode = "old" | "email";

export function StatusBar({
  backendOnline,
  accountCount,
  version,
  expiresAtLabel,
}: StatusBarProps) {
  const { user, logout } = useLicense();
  const toast = useToast();
  const [menuOpen, setMenuOpen] = useState(false);
  const [pwdOpen, setPwdOpen] = useState(false);
  const [pwdMode, setPwdMode] = useState<PwdMode>("old");
  const [oldPassword, setOldPassword] = useState("");
  const [emailCode, setEmailCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [menuOpen]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [cooldown]);

  function resetPwdForm() {
    setOldPassword("");
    setEmailCode("");
    setNewPassword("");
    setPwdMode("old");
    setCooldown(0);
  }

  async function handleSendCode() {
    if (!user?.email) return;
    setBusy(true);
    try {
      await licenseApi.sendCode(user.email, "reset");
      setCooldown(60);
      toast.success("验证码已发送，请查收邮箱");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "发送失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleChangePassword(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      if (pwdMode === "old") {
        await licenseApi.changePassword({
          newPassword,
          oldPassword,
        });
      } else {
        await licenseApi.changePassword({
          newPassword,
          emailCode: emailCode.trim(),
        });
      }
      toast.success("密码已修改");
      setPwdOpen(false);
      resetPwdForm();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "修改失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <footer className="status-bar">
      <div className="status-bar-main">
        <span className={`status-dot ${backendOnline ? "online" : "offline"}`} />
        <span>后端: {backendOnline ? "已连接" : "未连接"}</span>
        <span>账号: {accountCount}</span>
        {expiresAtLabel && expiresAtLabel !== "未授权" && <span>到期: {expiresAtLabel}</span>}
        <span>版本: {version}</span>
      </div>

      {user?.email && (
        <div className="status-bar-account" ref={menuRef}>
          <button
            type="button"
            className="status-account-btn"
            onClick={() => setMenuOpen((v) => !v)}
            title="账号菜单"
          >
            <span className="status-account-email">{user.email}</span>
            <span className="status-account-caret" aria-hidden>
              ▾
            </span>
          </button>
          {menuOpen && (
            <div className="status-account-menu" role="menu">
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setMenuOpen(false);
                  resetPwdForm();
                  setPwdOpen(true);
                }}
              >
                修改密码
              </button>
              <button
                type="button"
                role="menuitem"
                className="danger"
                onClick={() => {
                  setMenuOpen(false);
                  void logout();
                }}
              >
                退出账号
              </button>
            </div>
          )}
        </div>
      )}

      {pwdOpen && (
        <div
          className="status-pwd-overlay"
          onClick={() => {
            if (!busy) {
              setPwdOpen(false);
              resetPwdForm();
            }
          }}
        >
          <form
            className="status-pwd-dialog"
            onClick={(e) => e.stopPropagation()}
            onSubmit={(e) => void handleChangePassword(e)}
          >
            <h3>修改密码</h3>
            <div className="status-pwd-tabs" role="tablist">
              <button
                type="button"
                role="tab"
                className={pwdMode === "old" ? "active" : ""}
                onClick={() => setPwdMode("old")}
              >
                原密码验证
              </button>
              <button
                type="button"
                role="tab"
                className={pwdMode === "email" ? "active" : ""}
                onClick={() => setPwdMode("email")}
              >
                邮箱验证码
              </button>
            </div>

            {pwdMode === "old" ? (
              <label>
                当前密码
                <input
                  type="password"
                  value={oldPassword}
                  onChange={(e) => setOldPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                />
              </label>
            ) : (
              <>
                <p className="status-pwd-hint">验证码将发送至 {user?.email}</p>
                <label>
                  邮箱验证码
                  <div className="status-pwd-code-row">
                    <input
                      value={emailCode}
                      onChange={(e) => setEmailCode(e.target.value)}
                      required
                      maxLength={16}
                      placeholder="6 位验证码"
                      autoComplete="one-time-code"
                    />
                    <button
                      type="button"
                      className="ghost"
                      disabled={busy || cooldown > 0}
                      onClick={() => void handleSendCode()}
                    >
                      {cooldown > 0 ? `${cooldown}s` : "获取验证码"}
                    </button>
                  </div>
                </label>
              </>
            )}

            <label>
              新密码
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={6}
                autoComplete="new-password"
                placeholder="至少 6 位"
              />
            </label>
            <div className="status-pwd-actions">
              <button
                type="button"
                className="ghost"
                disabled={busy}
                onClick={() => {
                  setPwdOpen(false);
                  resetPwdForm();
                }}
              >
                取消
              </button>
              <button type="submit" disabled={busy}>
                {busy ? "提交中…" : "确认修改"}
              </button>
            </div>
          </form>
        </div>
      )}
    </footer>
  );
}
