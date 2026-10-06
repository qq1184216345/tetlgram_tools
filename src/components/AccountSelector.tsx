import { useEffect, useMemo, useRef, useState } from "react";
import { api, AccountInfo } from "../api/client";
import { usePageNav } from "../context/PageNavContext";

interface AccountSelectorProps {
  selected: string[];
  onChange: (ids: string[]) => void;
}

export function AccountSelector({ selected, onChange }: AccountSelectorProps) {
  const [accounts, setAccounts] = useState<AccountInfo[]>([]);
  const [query, setQuery] = useState("");
  const selectedRef = useRef(selected);
  const go = usePageNav();
  selectedRef.current = selected;

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const data = await api.listAccounts();
        if (cancelled) return;
        setAccounts(data);
        const onlineIds = new Set(
          data.filter((account) => account.status === "online").map((account) => account.id),
        );
        const next = selectedRef.current.filter((id) => onlineIds.has(id));
        if (next.length !== selectedRef.current.length) {
          onChange(next);
        }
      } catch {
        /* ignore */
      }
    };

    void load();
    const timer = window.setInterval(() => void load(), 5000);
    const onFocus = () => void load();
    window.addEventListener("focus", onFocus);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, [onChange]);

  const onlineAccounts = accounts.filter((account) => account.status === "online");
  const offlineCount = accounts.length - onlineAccounts.length;
  const keyword = query.trim().toLowerCase();
  const visible = useMemo(() => {
    if (!keyword) return onlineAccounts;
    return onlineAccounts.filter((account) => {
      const hay = `${account.phone || ""} ${account.username || ""} ${account.id}`.toLowerCase();
      return hay.includes(keyword);
    });
  }, [onlineAccounts, keyword]);

  const allSelected =
    onlineAccounts.length > 0 && onlineAccounts.every((account) => selected.includes(account.id));

  function toggle(id: string) {
    if (selected.includes(id)) {
      onChange(selected.filter((item) => item !== id));
    } else {
      onChange([...selected, id]);
    }
  }

  function selectAll() {
    onChange(onlineAccounts.map((account) => account.id));
  }

  function clearAll() {
    onChange([]);
  }

  if (accounts.length === 0) {
    return (
      <div className="empty-state">
        <p>还没有账号</p>
        <span className="muted">导入 session 或扫码登录后才能发任务</span>
        <button type="button" className="secondary" onClick={() => go("accounts")}>
          去账号中心添加
        </button>
      </div>
    );
  }

  if (onlineAccounts.length === 0) {
    return (
      <div className="empty-state">
        <p>没有在线账号</p>
        <span className="muted">已导入 {accounts.length} 个账号，先连接后再勾选</span>
        <button type="button" className="secondary" onClick={() => go("accounts")}>
          去连接账号
        </button>
      </div>
    );
  }

  return (
    <div className="account-selector">
      <div className="account-selector-toolbar">
        <button type="button" className="secondary" onClick={allSelected ? clearAll : selectAll}>
          {allSelected ? "取消全选" : "全选在线"}
        </button>
        <span className="muted" style={{ marginBottom: 0 }}>
          已选 {selected.length}/{onlineAccounts.length}
          {offlineCount > 0 ? ` · ${offlineCount} 离线` : ""}
        </span>
      </div>
      {onlineAccounts.length > 6 && (
        <input
          className="account-search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="搜索手机号 / 用户名"
        />
      )}
      {visible.map((account) => (
        <label key={account.id} className={`account-chip${selected.includes(account.id) ? " selected" : ""}`}>
          <input
            type="checkbox"
            checked={selected.includes(account.id)}
            onChange={() => toggle(account.id)}
          />
          <span>
            {account.phone || account.id}
            {account.username && ` (@${account.username})`}
          </span>
          <span className={`badge badge-${account.status}`}>在线</span>
        </label>
      ))}
      {visible.length === 0 && <p className="muted">没有匹配的在线账号</p>}
    </div>
  );
}
