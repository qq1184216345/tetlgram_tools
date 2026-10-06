const state = {
  token: localStorage.getItem("pw_admin_token") || "",
  email: localStorage.getItem("pw_admin_email") || "",
};

function $(id) {
  return document.getElementById(id);
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const res = await fetch(path, { ...options, headers });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = body.detail;
    throw new Error(typeof detail === "string" ? detail : res.statusText);
  }
  return body;
}

function showMain(show) {
  $("login-view").classList.toggle("hidden", show);
  $("main-view").classList.toggle("hidden", !show);
  if (show) $("admin-email").textContent = state.email;
}

function fmtTime(v) {
  if (!v) return "-";
  try {
    return new Date(v).toLocaleString();
  } catch {
    return v;
  }
}

async function loadUsers() {
  const q = $("user-q").value.trim();
  const data = await api(`/admin/users?q=${encodeURIComponent(q)}&limit=200`);
  const tbody = $("users-body");
  tbody.innerHTML = "";
  for (const u of data.items) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${u.id}</td>
      <td>${u.email}${u.is_admin ? " (管理员)" : ""}</td>
      <td class="${u.status === "banned" ? "bad" : "ok"}">${u.status}</td>
      <td>${fmtTime(u.expires_at)}</td>
      <td class="${u.licensed ? "ok" : "bad"}">${u.licensed ? "有效" : "无/过期"}</td>
      <td></td>`;
    const actions = tr.lastElementChild;
    if (!u.is_admin) {
      const banBtn = document.createElement("button");
      banBtn.textContent = u.status === "banned" ? "解封" : "封禁";
      banBtn.className = u.status === "banned" ? "" : "danger";
      banBtn.onclick = async () => {
        await api(`/admin/users/${u.id}/ban`, {
          method: "POST",
          body: JSON.stringify({ banned: u.status !== "banned" }),
        });
        await loadUsers();
      };
      const extBtn = document.createElement("button");
      extBtn.textContent = "+30天";
      extBtn.onclick = async () => {
        await api(`/admin/users/${u.id}/extend`, {
          method: "POST",
          body: JSON.stringify({ days: 30 }),
        });
        await loadUsers();
      };
      actions.append(banBtn, document.createTextNode(" "), extBtn);
    }
    tbody.appendChild(tr);
  }
}

async function loadCards() {
  const status = $("card-status").value;
  const qs = status ? `?status=${status}&limit=200` : "?limit=200";
  const data = await api(`/admin/cards${qs}`);
  const tbody = $("cards-body");
  tbody.innerHTML = "";
  for (const c of data.items) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${c.id}</td>
      <td><code>${c.code}</code></td>
      <td>${c.duration_days}</td>
      <td>${c.status}</td>
      <td>${c.batch_note || "-"}</td>
      <td>${fmtTime(c.used_at)}</td>
      <td></td>`;
    if (c.status === "unused") {
      const btn = document.createElement("button");
      btn.textContent = "作废";
      btn.className = "danger";
      btn.onclick = async () => {
        await api(`/admin/cards/${c.id}/revoke`, { method: "POST", body: "{}" });
        await loadCards();
      };
      tr.lastElementChild.appendChild(btn);
    }
    tbody.appendChild(tr);
  }
}

async function loadAudit() {
  const data = await api("/admin/audit?limit=200");
  const tbody = $("audit-body");
  tbody.innerHTML = "";
  for (const a of data.items) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${fmtTime(a.created_at)}</td>
      <td>${a.action}</td>
      <td>${a.actor}</td>
      <td>${a.detail || ""}</td>`;
    tbody.appendChild(tr);
  }
}

function switchTab(name) {
  document.querySelectorAll(".tabs button").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === name);
  });
  ["users", "cards", "version", "audit"].forEach((t) => {
    $(`tab-${t}`).classList.toggle("hidden", t !== name);
  });
  if (name === "users") loadUsers().catch(alert);
  if (name === "cards") loadCards().catch(alert);
  if (name === "version") loadVersion().catch(alert);
  if (name === "audit") loadAudit().catch(alert);
}

async function loadVersion() {
  const data = await api("/admin/app-version");
  $("ver-version").value = data.version || "";
  $("ver-url").value = data.download_url || data.url || "";
  $("ver-notes").value = data.notes || "";
  $("ver-force").checked = Boolean(data.force_update || data.force);
  $("ver-meta").textContent = data.updated_at
    ? `上次更新：${fmtTime(data.updated_at)} · ${data.updated_by || "-"}`
    : "";
  $("ver-msg").textContent = "";
}

$("ver-refresh").onclick = () => loadVersion().catch(alert);
$("ver-save").onclick = async () => {
  $("ver-msg").textContent = "";
  try {
    const data = await api("/admin/app-version", {
      method: "PUT",
      body: JSON.stringify({
        version: $("ver-version").value.trim(),
        download_url: $("ver-url").value.trim(),
        notes: $("ver-notes").value.trim(),
        force_update: $("ver-force").checked,
      }),
    });
    $("ver-msg").textContent = `已保存版本 ${data.item?.version || ""}`;
    await loadVersion();
  } catch (e) {
    alert(e.message || String(e));
  }
};

$("login-btn").onclick = async () => {
  $("login-error").textContent = "";
  try {
    const email = $("login-email").value.trim();
    const password = $("login-password").value;
    const data = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password, device_label: "admin-web" }),
    });
    if (!data.user?.is_admin) throw new Error("非管理员账号");
    state.token = data.access_token;
    state.email = data.user.email;
    localStorage.setItem("pw_admin_token", state.token);
    localStorage.setItem("pw_admin_email", state.email);
    showMain(true);
    switchTab("users");
  } catch (e) {
    $("login-error").textContent = e.message || String(e);
  }
};

$("logout-btn").onclick = async () => {
  try {
    await api("/auth/logout", { method: "POST", body: "{}" });
  } catch (_) {}
  state.token = "";
  localStorage.removeItem("pw_admin_token");
  localStorage.removeItem("pw_admin_email");
  showMain(false);
};

document.querySelectorAll(".tabs button").forEach((b) => {
  b.onclick = () => switchTab(b.dataset.tab);
});

$("user-search").onclick = () => loadUsers().catch(alert);
$("user-refresh").onclick = () => loadUsers().catch(alert);
$("card-refresh").onclick = () => loadCards().catch(alert);
$("card-status").onchange = () => loadCards().catch(alert);
$("audit-refresh").onclick = () => loadAudit().catch(alert);

$("gen-btn").onclick = async () => {
  try {
    const data = await api("/admin/cards/generate", {
      method: "POST",
      body: JSON.stringify({
        duration_days: Number($("gen-days").value) || 30,
        count: Number($("gen-count").value) || 1,
        batch_note: $("gen-note").value.trim(),
      }),
    });
    $("gen-result").value = (data.codes || []).join("\n");
    await loadCards();
  } catch (e) {
    alert(e.message || String(e));
  }
};

(async function boot() {
  if (!state.token) {
    showMain(false);
    return;
  }
  try {
    const me = await api("/auth/me");
    if (!me.is_admin) throw new Error("非管理员");
    state.email = me.email;
    showMain(true);
    switchTab("users");
  } catch {
    state.token = "";
    localStorage.removeItem("pw_admin_token");
    showMain(false);
  }
})();
