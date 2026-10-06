import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api, AccountInfo, ChatHistoryMessage } from "../api/client";

import { AccountSelector } from "../components/AccountSelector";

import { usePersistedAccounts } from "../hooks/usePersistedAccounts";

import { useTaskRunner } from "../hooks/useTaskRunner";

import { useGlobalTask } from "../context/TaskContext";

import { useToast } from "../context/ToastContext";
import { useTauriFileDrop } from "../hooks/useTauriFileDrop";



const STATUS_LABEL: Record<AccountInfo["status"], string> = {

  offline: "离线",

  online: "在线",

  connecting: "连接中",

  error: "异常",

};



type Tab = "list" | "import" | "profile";



export function AccountsPage() {

  const [tab, setTab] = useState<Tab>("list");

  const [accounts, setAccounts] = useState<AccountInfo[]>([]);

  const [phone, setPhone] = useState("");

  const [code, setCode] = useState("");

  const [password, setPassword] = useState("");

  const [codeSent, setCodeSent] = useState(false);

  const toast = useToast();

  const [loading, setLoading] = useState(false);

  const [tdataPath, setTdataPath] = useState("");

  const [tdataSessionName, setTdataSessionName] = useState("");

  const fileRef = useRef<HTMLInputElement>(null);



  const [checkedIds, setCheckedIds] = useState<string[]>([]);

  const [selectedAccounts, setSelectedAccounts] = usePersistedAccounts();

  const [useRandomConfig, setUseRandomConfig] = useState(true);

  const [updateFirstName, setUpdateFirstName] = useState(true);

  const [updateLastName, setUpdateLastName] = useState(true);

  const [updateAbout, setUpdateAbout] = useState(true);

  const [updateUsername, setUpdateUsername] = useState(true);

  const [updateAvatar, setUpdateAvatar] = useState(true);

  const [updatePassword, setUpdatePassword] = useState(false);
  const [remove2fa, setRemove2fa] = useState(false);

  const [firstName, setFirstName] = useState("");

  const [lastName, setLastName] = useState("");

  const [about, setAbout] = useState("");

  const [username, setUsername] = useState("");

  const [oldPassword, setOldPassword] = useState("");

  const [newPassword, setNewPassword] = useState("");

  const [profileConfig, setProfileConfig] = useState<Record<string, { exists?: boolean; count: number }>>({});



  const [qrLoginId, setQrLoginId] = useState("");

  const [qrImage, setQrImage] = useState("");

  const [qrStatus, setQrStatus] = useState("");

  const [qrPassword, setQrPassword] = useState("");

  const [chatAccountId, setChatAccountId] = useState<string | null>(null);
  const [chatTarget, setChatTarget] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatHistoryMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [proxyDrafts, setProxyDrafts] = useState<Record<string, string>>({});
  const [adAccountId, setAdAccountId] = useState<string | null>(null);
  const [adDraft, setAdDraft] = useState("");
  const [statusDetail, setStatusDetail] = useState<{
    accountId: string;
    summary: string;
    fullText: string;
    verifyLinks: string[];
  } | null>(null);
  const [privacyOpen, setPrivacyOpen] = useState(false);
  const [privacyPhone, setPrivacyPhone] = useState("disallow_all");
  const [privacyLastSeen, setPrivacyLastSeen] = useState("disallow_all");
  const [privacyPhoto, setPrivacyPhoto] = useState("allow_all");
  const [privacyInvite, setPrivacyInvite] = useState("disallow_all");
  const [deviceAccountId, setDeviceAccountId] = useState<string | null>(null);
  const [devices, setDevices] = useState<
    Array<{
      hash: number;
      device_model: string;
      platform: string;
      system_version: string;
      app_name: string;
      app_version: string;
      country: string;
      ip: string;
      date_active: string;
      current: boolean;
    }>
  >([]);
  const [selectedDeviceHashes, setSelectedDeviceHashes] = useState<number[]>([]);
  const [devicesLoading, setDevicesLoading] = useState(false);

  const { currentTask, loading: taskLoading, isRunning, run, stop } = useTaskRunner(
    "connect_accounts",
    "update_profile",
  );

  const { isTaskRunning } = useGlobalTask();
  const [dropHover, setDropHover] = useState(false);
  const [proxyPool, setProxyPool] = useState<string[]>([]);
  const [accountQuery, setAccountQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const TASK_BLOCK_MSG = "有任务正在运行，请先暂停或停止任务后再登录或导入账号";

  const visibleAccounts = useMemo(() => {
    const query = accountQuery.trim().toLowerCase();
    return accounts.filter((account) => {
      if (statusFilter !== "all" && account.status !== statusFilter) return false;
      if (!query) return true;
      const haystack = [
        account.phone,
        account.id,
        account.username,
        account.first_name,
        account.last_name,
        account.proxy,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  }, [accounts, accountQuery, statusFilter]);

  useTauriFileDrop(tab === "import" && !isTaskRunning, handleImportPaths, setDropHover);



  const refresh = useCallback(async () => {

    try {

      const data = await api.listAccounts();

      setAccounts(data);
      setProxyDrafts({});
      const cfg = await api.getConfig().catch(() => null);
      if (cfg?.proxy_list) {
        setProxyPool(
          cfg.proxy_list
            .split("\n")
            .map((line) => line.trim())
            .filter(Boolean),
        );
      }

    } catch (error) {

      toast.error(error instanceof Error ? error.message : "加载账号失败");

    }

  }, []);



  useEffect(() => {

    refresh();

  }, [refresh]);



  useEffect(() => {

    if (currentTask?.type !== "connect_accounts") return;

    if (currentTask.status === "running") {

      const timer = setInterval(() => {

        void refresh();

      }, 2000);

      return () => clearInterval(timer);

    }

    if (["completed", "error", "stopped"].includes(currentTask.status)) {

      void refresh();

    }

  }, [currentTask?.id, currentTask?.status, currentTask?.type, refresh]);



  useEffect(() => {

    if (tab === "profile") {

      api.getProfileConfig().then(setProfileConfig).catch(() => {});

    }

  }, [tab]);



  useEffect(() => {

    if (!qrLoginId) return;



    const poll = async () => {

      try {

        const status = await api.getQrLoginStatus(qrLoginId);

        setQrStatus(status.status);

        if (status.qr_image) setQrImage(status.qr_image);



        if (status.status === "success") {

          toast.success("扫码登录成功");

          setQrLoginId("");

          setQrImage("");

          setQrPassword("");

          await refresh();

        } else if (status.status === "expired") {

          toast.info("二维码已过期，请点击刷新");

        } else if (status.status === "error") {

          toast.error(status.error || "扫码登录失败");

        }

      } catch {

        // ignore transient poll errors

      }

    };



    poll();

    const timer = setInterval(poll, 2000);

    return () => clearInterval(timer);

  }, [qrLoginId, refresh]);



  useEffect(() => {

    return () => {

      if (qrLoginId) {

        api.cancelQrLogin(qrLoginId).catch(() => {});

      }

    };

  }, [qrLoginId]);



  async function handleStartLogin() {

    if (isTaskRunning) {

      toast.error(TASK_BLOCK_MSG);

      return;

    }

    if (!phone.trim()) return;

    setLoading(true);

    try {

      await api.startLogin(phone.trim());

      setCodeSent(true);

      toast.success("验证码已发送，请查收 Telegram");

    } catch (error) {

      toast.error(error instanceof Error ? error.message : "发送验证码失败");

    } finally {

      setLoading(false);

    }

  }



  async function handleVerifyLogin() {

    if (isTaskRunning) {

      toast.error(TASK_BLOCK_MSG);

      return;

    }

    if (!phone.trim() || !code.trim()) {

      toast.error("请填写手机号和验证码");

      return;

    }

    setLoading(true);

    try {

      await api.verifyLogin(phone.trim(), code.trim(), password || undefined);

      setCodeSent(false);

      setPhone("");

      setCode("");

      setPassword("");

      toast.success("登录成功");

      await refresh();

    } catch (error) {

      toast.error(error instanceof Error ? error.message : "登录失败");

    } finally {

      setLoading(false);

    }

  }



  async function handleStartQrLogin() {

    if (isTaskRunning) {

      toast.error(TASK_BLOCK_MSG);

      return;

    }

    setLoading(true);

    try {

      if (qrLoginId) {

        await api.cancelQrLogin(qrLoginId);

      }

      const result = await api.startQrLogin();

      const data = result.data as { login_id: string; qr_image: string };

      setQrLoginId(data.login_id);

      setQrImage(data.qr_image);

      setQrStatus("waiting");

      toast.info(result.message || "请使用 Telegram 扫描二维码登录");

    } catch (error) {

      toast.error(error instanceof Error ? error.message : "生成二维码失败");

    } finally {

      setLoading(false);

    }

  }



  async function handleRefreshQr() {

    if (!qrLoginId) return;

    setLoading(true);

    try {

      const result = await api.refreshQrLogin(qrLoginId);

      const data = result.data as { qr_image: string };

      setQrImage(data.qr_image);

      setQrStatus("waiting");

      toast.success("二维码已刷新");

    } catch (error) {

      toast.error(error instanceof Error ? error.message : "刷新失败");

    } finally {

      setLoading(false);

    }

  }



  async function handleCompleteQrLogin() {

    if (!qrLoginId || !qrPassword.trim()) return;

    setLoading(true);

    try {

      await api.completeQrLogin(qrLoginId, qrPassword.trim());

      setQrLoginId("");

      setQrImage("");

      setQrPassword("");

      toast.success("扫码登录成功");

      await refresh();

    } catch (error) {

      toast.error(error instanceof Error ? error.message : "二级密码验证失败");

    } finally {

      setLoading(false);

    }

  }



  async function handleCancelQr() {

    if (!qrLoginId) return;

    await api.cancelQrLogin(qrLoginId).catch(() => {});

    setQrLoginId("");

    setQrImage("");

    setQrStatus("");

    setQrPassword("");

  }



  function toggleCheck(id: string) {

    setCheckedIds((prev) =>

      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id],

    );

  }



  function toggleCheckAll() {

    const visibleIds = visibleAccounts.map((account) => account.id);
    const allVisibleChecked =
      visibleIds.length > 0 && visibleIds.every((id) => checkedIds.includes(id));
    if (allVisibleChecked) {
      setCheckedIds((prev) => prev.filter((id) => !visibleIds.includes(id)));
    } else {
      setCheckedIds((prev) => Array.from(new Set([...prev, ...visibleIds])));
    }

  }



  async function batchConnect() {

    if (checkedIds.length === 0) return;

    await run(() => api.startConnectAccounts(checkedIds), checkedIds);

  }



  async function batchDisconnect() {

    if (checkedIds.length === 0) return;

    setLoading(true);

    for (const id of checkedIds) {

      await api.disconnectAccount(id).catch(() => {});

    }

    await refresh();

    setLoading(false);

  }



  async function batchCheckStatus() {

    if (checkedIds.length === 0) {

      toast.error("请先勾选账号");

      return;

    }

    setLoading(true);

    try {

      const result = await api.checkAccountsStatus(checkedIds);

      toast.info(result.message);

      const rows = (result.data?.results as Array<Record<string, unknown>>) || [];

      if (rows.length === 1) {

        const row = rows[0];

        setStatusDetail({

          accountId: String(row.account_id || ""),

          summary: String(row.summary || ""),

          fullText: String(row.full_text || ""),

          verifyLinks: (row.verify_links as string[]) || [],

        });

      } else if (rows.length > 1) {

        const limited = rows.filter((r) => r.limited);

        const text = rows

          .map((r) => `${r.account_id}: ${r.summary}`)

          .join("\n");

        setStatusDetail({

          accountId: `批量 ${rows.length} 个`,

          summary: result.message,

          fullText: text + (limited.length ? `\n\n受限账号: ${limited.map((r) => r.account_id).join(", ")}` : ""),

          verifyLinks: rows.flatMap((r) => (r.verify_links as string[]) || []),

        });

      }

    } catch (error) {

      toast.error(error instanceof Error ? error.message : "检测失败");

    } finally {

      setLoading(false);

    }

  }



  async function batchPrivacy() {
    if (checkedIds.length === 0) {
      toast.error("请先勾选账号");
      return;
    }
    setPrivacyOpen(true);
  }

  async function applyPrivacyBatch() {
    if (checkedIds.length === 0) {
      toast.error("请先勾选账号");
      return;
    }
    setLoading(true);
    try {
      const result = await api.privacyBatch({
        account_ids: checkedIds,
        phone: privacyPhone,
        last_seen: privacyLastSeen,
        profile_photo: privacyPhoto,
        invite: privacyInvite,
      });
      toast.success(result.message);
      setPrivacyOpen(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "隐私设置失败");
    } finally {
      setLoading(false);
    }
  }

  async function batchKickDevices() {
    if (checkedIds.length === 0) {
      toast.error("请先勾选账号");
      return;
    }
    if (!confirm(`确定踢掉已选 ${checkedIds.length} 个账号的全部其他设备？`)) return;
    setLoading(true);
    for (const id of checkedIds) {
      try {
        const result = await api.kickAccountDevices(id);
        toast.info(`[${id}] ${result.message}`);
      } catch (error) {
        toast.error(error instanceof Error ? error.message : `[${id}] 踢设备失败`);
      }
    }
    setLoading(false);
  }

  async function openDevices(accountId: string) {
    setDeviceAccountId(accountId);
    setDevices([]);
    setSelectedDeviceHashes([]);
    setDevicesLoading(true);
    try {
      const result = await api.listAccountDevices(accountId);
      const list = (result.data?.devices as typeof devices) || [];
      setDevices(list);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载设备失败");
      setDeviceAccountId(null);
    } finally {
      setDevicesLoading(false);
    }
  }

  async function kickSelectedDevices() {
    if (!deviceAccountId) return;
    if (selectedDeviceHashes.length === 0) {
      toast.error("请勾选要踢的设备");
      return;
    }
    setDevicesLoading(true);
    try {
      const result = await api.kickAccountDevices(deviceAccountId, selectedDeviceHashes);
      toast.success(result.message);
      const refreshed = await api.listAccountDevices(deviceAccountId);
      setDevices((refreshed.data?.devices as typeof devices) || []);
      setSelectedDeviceHashes([]);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "踢设备失败");
    } finally {
      setDevicesLoading(false);
    }
  }

  async function kickAllOtherDevices() {
    if (!deviceAccountId) return;
    if (!confirm("确定踢掉该账号全部其他设备（保留当前）？")) return;
    setDevicesLoading(true);
    try {
      const result = await api.kickAccountDevices(deviceAccountId);
      toast.success(result.message);
      const refreshed = await api.listAccountDevices(deviceAccountId);
      setDevices((refreshed.data?.devices as typeof devices) || []);
      setSelectedDeviceHashes([]);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "踢设备失败");
    } finally {
      setDevicesLoading(false);
    }
  }



  async function copyAccountInfo(account: AccountInfo) {

    const text = [

      account.phone || account.id,

      account.username ? `@${account.username}` : "",

      account.first_name,

      account.last_name,

    ]

      .filter(Boolean)

      .join(" | ");

    try {

      await navigator.clipboard.writeText(text);

      toast.success(`已复制: ${text}`);

    } catch {

      toast.error("复制失败");

    }

  }



  async function handleImportFiles(files: FileList | null) {

    if (isTaskRunning) {

      toast.error(TASK_BLOCK_MSG);

      return;

    }

    if (!files || files.length === 0) return;

    setLoading(true);

    try {

      const result = await api.importSessions(files);

      toast.success(result.message);

      await refresh();

    } catch (error) {

      toast.error(error instanceof Error ? error.message : "导入失败");

    } finally {

      setLoading(false);

      if (fileRef.current) fileRef.current.value = "";

    }

  }



  async function handleImportPaths(paths: string[]) {

    if (isTaskRunning) {

      toast.error(TASK_BLOCK_MSG);

      return;

    }

    if (!paths.length) return;

    setLoading(true);

    try {

      const result = await api.importSessionPaths(paths);

      if (result.success) toast.success(result.message);

      else toast.error(result.message || "导入失败");

      await refresh();

    } catch (error) {

      toast.error(error instanceof Error ? error.message : "导入失败");

    } finally {

      setLoading(false);

    }

  }



  async function handleConvertTdata() {

    if (isTaskRunning) {

      toast.error(TASK_BLOCK_MSG);

      return;

    }

    setLoading(true);

    try {

      const result = await api.convertTdata(tdataPath.trim(), tdataSessionName.trim());

      if (result.success) {

        toast.success(result.message);

        const errors = Array.isArray(result.data?.errors) ? result.data.errors : [];

        if (errors.length > 0) {

          toast.error(errors.slice(0, 3).map(String).join("；"));

        }

        setTdataPath("");

        setTdataSessionName("");

        await refresh();

      } else {

        toast.error(result.message || "导入失败");

      }

    } catch (error) {

      toast.error(error instanceof Error ? error.message : "转换失败");

    } finally {

      setLoading(false);

    }

  }



  async function handleAssignProxies() {
    const ids = checkedIds.length ? checkedIds : accounts.map((item) => item.id);
    if (!ids.length) {
      toast.error("请先导入账号");
      return;
    }
    if (!proxyPool.length) {
      toast.error("设置里还没有 HTTP/SOCKS 代理列表。FlClash 的 Shadowsocks 节点不能直接分配。");
      return;
    }
    try {
      const result = await api.assignAccountProxies(ids);
      toast.success(result.message);
      await refresh();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "分配失败");
    }
  }

  function openChatHistory(accountId: string) {
    setChatAccountId(accountId);
    setChatTarget("");
    setChatMessages([]);
  }

  async function handleFetchChatHistory() {
    if (!chatAccountId || !chatTarget.trim()) return;
    setChatLoading(true);
    try {
      const messages = await api.getChatHistory(chatAccountId, chatTarget.trim());
      setChatMessages(messages);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "获取聊天记录失败");
    } finally {
      setChatLoading(false);
    }
  }

  async function openCustomAd(accountId: string) {
    try {
      const data = await api.getAccountCustomAd(accountId);
      setAdDraft(data.message);
      setAdAccountId(accountId);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载独立广告失败");
    }
  }

  async function handleSaveCustomAd() {
    if (!adAccountId) return;
    try {
      await api.setAccountCustomAd(adAccountId, adDraft);
      setAdAccountId(null);
      toast.success("独立广告语已保存");
      await refresh();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "保存失败");
    }
  }

  function handleProfileUpdate() {

    run(() =>

      api.startProfileUpdate({

        account_ids: selectedAccounts,

        use_random_config: useRandomConfig,

        update_first_name: updateFirstName,

        update_last_name: updateLastName,

        update_about: updateAbout,

        update_username: updateUsername,

        update_avatar: updateAvatar,

        update_password: updatePassword,

        first_name: firstName,

        last_name: lastName,

        about,

        username,

        old_password: oldPassword,

        new_password: newPassword,

        interval_min: 5,

        interval_max: 15,

        remove_2fa: remove2fa,

      }),

      selectedAccounts,

    );

  }



  return (

    <div className="accounts-page">

      <div className="tab-bar">

        <button className={tab === "list" ? "active" : ""} onClick={() => setTab("list")}>

          账号列表

        </button>

        <button className={tab === "import" ? "active" : ""} onClick={() => setTab("import")}>

          导入 Session

        </button>

        <button className={tab === "profile" ? "active" : ""} onClick={() => setTab("profile")}>

          批量改资料

        </button>

      </div>



      {tab === "list" && (

        <>

          <div className="panel-grid login-grid">

            <div className="card">

              <h3>手机号登录</h3>

              <div className="form-stack">

                <input

                  placeholder="手机号（含国家码，如 +86138...）"

                  value={phone}

                  onChange={(e) => setPhone(e.target.value)}

                />

                <input

                  placeholder="验证码"

                  value={code}

                  onChange={(e) => setCode(e.target.value)}

                />

                <input

                  type="password"

                  placeholder="二级密码（如账号已开启）"

                  value={password}

                  onChange={(e) => setPassword(e.target.value)}

                />

                <div className="button-row">

                  <button onClick={handleStartLogin} disabled={loading || isTaskRunning}>

                    {codeSent ? "重新发送验证码" : "发送验证码"}

                  </button>

                  <button onClick={handleVerifyLogin} disabled={loading || !codeSent || isTaskRunning}>

                    确认登录

                  </button>

                </div>

              </div>

            </div>



            <div className="card">

              <h3>扫码登录</h3>

              <div className="qr-login-panel">

                {qrImage ? (

                  <img

                    className="qr-image"

                    src={`data:image/png;base64,${qrImage}`}

                    alt="Telegram 登录二维码"

                  />

                ) : (

                  <div className="qr-placeholder">点击下方按钮生成二维码</div>

                )}

                {qrStatus === "need_password" && (

                  <div className="form-stack" style={{ marginTop: 12 }}>

                    <input

                      type="password"

                      placeholder="二级密码"

                      value={qrPassword}

                      onChange={(e) => setQrPassword(e.target.value)}

                    />

                    <button onClick={handleCompleteQrLogin} disabled={loading}>

                      提交二级密码

                    </button>

                  </div>

                )}

                <div className="button-row" style={{ marginTop: 12 }}>

                  {!qrLoginId ? (

                    <button onClick={handleStartQrLogin} disabled={loading || isTaskRunning}>

                      扫码登录

                    </button>

                  ) : (

                    <>

                      <button onClick={handleRefreshQr} disabled={loading}>

                        刷新二维码

                      </button>

                      <button className="secondary" onClick={handleCancelQr}>

                        取消

                      </button>

                    </>

                  )}

                </div>

                {qrStatus && (

                  <p className="muted" style={{ marginTop: 8 }}>

                    状态:{" "}

                    {qrStatus === "waiting" && "等待扫码"}

                    {qrStatus === "need_password" && "需要二级密码"}

                    {qrStatus === "expired" && "已过期"}

                    {qrStatus === "success" && "登录成功"}

                    {qrStatus === "error" && "失败"}

                  </p>

                )}

              </div>

            </div>

          </div>



          <div className="card table-card">

            <div className="card-header">

              <h3>账号列表 ({accounts.length})</h3>

              <div className="button-row">

                <button onClick={refresh}>刷新</button>
                <button
                  className="secondary"
                  onClick={() => void handleAssignProxies()}
                  disabled={loading || accounts.length === 0}
                  title="按设置里的代理列表，给勾选账号各分一条不同节点；未勾选则全部分配"
                >
                  按节点分配代理
                </button>

                <button onClick={batchConnect} disabled={loading || taskLoading || isRunning || checkedIds.length === 0}>

                  批量连接 ({checkedIds.length})

                </button>

                <button

                  className="secondary"

                  onClick={batchDisconnect}

                  disabled={loading || checkedIds.length === 0}

                >

                  批量断开

                </button>

                <button

                  className="secondary"

                  onClick={batchCheckStatus}

                  disabled={loading || checkedIds.length === 0}

                >

                  检测账号状态

                </button>

                <button

                  className="secondary"

                  onClick={batchPrivacy}

                  disabled={loading || checkedIds.length === 0}

                >

                  批量隐私

                </button>

                <button

                  className="secondary"

                  onClick={batchKickDevices}

                  disabled={loading || checkedIds.length === 0}

                >

                  踢其他设备

                </button>

                <button className="secondary" onClick={() => setTab("import")}>

                  导入 Session

                </button>

              </div>

            </div>

            <div className="button-row" style={{ padding: "0 4px 12px", alignItems: "center" }}>
              <input
                className="account-search"
                style={{ maxWidth: 280 }}
                value={accountQuery}
                onChange={(e) => setAccountQuery(e.target.value)}
                placeholder="搜索手机号 / 用户名 / 代理"
              />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                style={{ width: 140 }}
              >
                <option value="all">全部状态</option>
                <option value="online">在线</option>
                <option value="offline">离线</option>
                <option value="connecting">连接中</option>
                <option value="error">异常</option>
              </select>
              <span className="muted">
                显示 {visibleAccounts.length} / {accounts.length}
              </span>
            </div>

            <table>

              <thead>

                <tr>

                  <th className="col-check">

                    <input

                      type="checkbox"

                      checked={
                        visibleAccounts.length > 0 &&
                        visibleAccounts.every((account) => checkedIds.includes(account.id))
                      }

                      onChange={toggleCheckAll}

                    />

                  </th>

                  <th>手机号</th>

                  <th>用户ID</th>

                  <th>用户名</th>

                  <th>昵称</th>

                  <th>状态</th>

                  <th>加群状态</th>

                  <th>群发状态</th>

                  <th>群发成功</th>

                  <th>独立广告</th>

                  <th>JSON</th>

                  <th>代理</th>

                  <th>操作</th>

                </tr>

              </thead>

              <tbody>

                {visibleAccounts.length === 0 ? (

                  <tr>

                    <td colSpan={13} className="empty-cell">

                      {accounts.length === 0 ? "暂无账号" : "没有符合筛选的账号"}

                    </td>

                  </tr>

                ) : (

                  visibleAccounts.map((account) => (

                    <tr key={account.id} className={checkedIds.includes(account.id) ? "row-selected" : ""}>

                      <td className="col-check">

                        <input

                          type="checkbox"

                          checked={checkedIds.includes(account.id)}

                          onChange={() => toggleCheck(account.id)}

                        />

                      </td>

                      <td>{account.phone || account.id}</td>

                      <td>{account.id}</td>

                      <td>{account.username ? `@${account.username}` : "-"}</td>

                      <td>

                        {[account.first_name, account.last_name].filter(Boolean).join(" ") || "-"}

                      </td>

                      <td>

                        <span className={`badge badge-${account.status}`}>

                          {STATUS_LABEL[account.status]}

                        </span>

                        {account.error && <span className="error-text">{account.error}</span>}

                      </td>

                      <td>{account.join_status || "-"}</td>

                      <td>{account.broadcast_status || "-"}</td>

                      <td>{account.broadcast_success_count ?? 0}</td>

                      <td>{account.has_custom_ad ? "已设置" : "-"}</td>

                      <td>{account.has_session_json ? "有" : "-"}</td>

                      <td>
                        <select
                          style={{ width: 168, fontSize: 12 }}
                          value={proxyDrafts[account.id] ?? account.proxy ?? ""}
                          onChange={(e) => {
                            const value = e.target.value;
                            setProxyDrafts((prev) => ({ ...prev, [account.id]: value }));
                            void api
                              .setAccountProxy(account.id, value)
                              .then((result) => {
                                toast.success(result.message || (value ? "已绑定该节点" : "已改为自动轮询"));
                                return refresh();
                              })
                              .catch((error) =>
                                toast.error(error instanceof Error ? error.message : "更新代理失败"),
                              );
                          }}
                        >
                          <option value="">自动轮询</option>
                          {(proxyDrafts[account.id] ?? account.proxy ?? "") &&
                          !proxyPool.includes(proxyDrafts[account.id] ?? account.proxy ?? "") ? (
                            <option value={proxyDrafts[account.id] ?? account.proxy}>
                              {proxyDrafts[account.id] ?? account.proxy}
                            </option>
                          ) : null}
                          {proxyPool.map((item) => (
                            <option key={item} value={item}>
                              {item}
                            </option>
                          ))}
                        </select>
                      </td>

                      <td className="actions">

                        <button
                          className="secondary"
                          onClick={() => openCustomAd(account.id)}
                        >
                          独立广告
                        </button>

                        <button
                          className="secondary"
                          onClick={() => copyAccountInfo(account)}
                        >
                          复制
                        </button>

                        <button
                          className="secondary"
                          onClick={async () => {
                            setLoading(true);
                            try {
                              const result = await api.checkAccountStatus(account.id);
                              const data = result.data || {};
                              setStatusDetail({
                                accountId: account.id,
                                summary: result.message,
                                fullText: String(data.full_text || ""),
                                verifyLinks: (data.verify_links as string[]) || [],
                              });
                              toast.info(result.message);
                            } catch (e) {
                              toast.error(e instanceof Error ? e.message : "检测失败");
                            } finally {
                              setLoading(false);
                            }
                          }}
                          disabled={loading}
                        >
                          状态
                        </button>

                        <button
                          className="secondary"
                          onClick={() => openDevices(account.id)}
                          disabled={loading || account.status !== "online"}
                        >
                          设备
                        </button>

                        <button
                          className="secondary"
                          onClick={() => openChatHistory(account.id)}
                          disabled={account.status !== "online"}
                        >
                          聊天记录
                        </button>

                        {account.status === "online" ? (

                          <button

                            className="secondary"

                            onClick={async () => {

                              await api.disconnectAccount(account.id);

                              refresh();

                            }}

                          >

                            断开

                          </button>

                        ) : (

                          <button

                            onClick={async () => {

                              setLoading(true);

                              try {

                                await api.connectAccount(account.id);

                                await refresh();

                              } catch (e) {

                                toast.error(e instanceof Error ? e.message : "连接失败");

                              } finally {

                                setLoading(false);

                              }

                            }}

                          >

                            连接

                          </button>

                        )}

                        <button

                          className="danger"

                          onClick={async () => {

                            if (confirm("确定删除？")) {

                              await api.deleteAccount(account.id);

                              setCheckedIds((prev) => prev.filter((id) => id !== account.id));

                              refresh();

                            }

                          }}

                        >

                          删除

                        </button>

                      </td>

                    </tr>

                  ))

                )}

              </tbody>

            </table>

          </div>

        </>

      )}



      {tab === "import" && (

        <div className="card" style={{ maxWidth: 520 }}>

          <h3>导入 Session 文件</h3>

          {isTaskRunning && (

            <p className="error-text">{TASK_BLOCK_MSG}</p>

          )}

          <p className="muted">

            支持同时选择 .session 与同名 .json（可多选/拖拽），将自动配对导入；也可稍后单独补传 json

          </p>

          <div

            className={`drop-zone${isTaskRunning ? " disabled" : ""}${dropHover ? " drag-over" : ""}`}

            onClick={() => !isTaskRunning && fileRef.current?.click()}

            onDragOver={(e) => {

              e.preventDefault();

              e.currentTarget.classList.add("drag-over");

            }}

            onDragLeave={(e) => e.currentTarget.classList.remove("drag-over")}

            onDrop={(e) => {

              e.preventDefault();

              e.currentTarget.classList.remove("drag-over");

              handleImportFiles(e.dataTransfer.files);

            }}

          >

            <p>点击选择或拖拽 .session / .json 到此处（建议成对选择）</p>

            <input

              ref={fileRef}

              type="file"

              accept=".session,.json,application/json"

              multiple

              hidden

              onChange={(e) => handleImportFiles(e.target.files)}

            />

          </div>



          <div className="card" style={{ marginTop: 16 }}>

            <h3>tdata 转 Session</h3>

            <p className="muted">

              对标直登号目录：把账号包放到 data/tdata（手机号/tdata，或手机号/.session+.json），留空即扫描该目录，也可填写单个账号或整个父目录一次性导入。

            </p>

            <div className="form-stack">

              <input

                placeholder="留空则扫描 data/tdata，例如 E:\\project\\AiProject\\TelegramTools\\data\\tdata"

                value={tdataPath}

                onChange={(e) => setTdataPath(e.target.value)}

              />

              <input

                placeholder="session 名称（仅单个账号时可选，批量导入忽略）"

                value={tdataSessionName}

                onChange={(e) => setTdataSessionName(e.target.value)}

              />

              <button onClick={handleConvertTdata} disabled={loading || isTaskRunning}>

                转换并导入

              </button>

            </div>

          </div>

        </div>

      )}



      {tab === "profile" && (

        <div className="task-page-layout">

          <div className="task-form">

            <div className="card">

              <h3>选择账号</h3>

              <AccountSelector selected={selectedAccounts} onChange={setSelectedAccounts} />

            </div>

            <div className="card">

              <h3>修改项（勾选要修改的字段）</h3>

              <div className="checkbox-grid">

                <label className="checkbox-row">

                  <input

                    type="checkbox"

                    checked={updateLastName}

                    onChange={(e) => setUpdateLastName(e.target.checked)}

                  />

                  姓氏

                </label>

                <label className="checkbox-row">

                  <input

                    type="checkbox"

                    checked={updateFirstName}

                    onChange={(e) => setUpdateFirstName(e.target.checked)}

                  />

                  名字

                </label>

                <label className="checkbox-row">

                  <input

                    type="checkbox"

                    checked={updateAvatar}

                    onChange={(e) => setUpdateAvatar(e.target.checked)}

                  />

                  头像

                </label>

                <label className="checkbox-row">

                  <input

                    type="checkbox"

                    checked={updateAbout}

                    onChange={(e) => setUpdateAbout(e.target.checked)}

                  />

                  简介

                </label>

                <label className="checkbox-row">

                  <input

                    type="checkbox"

                    checked={updateUsername}

                    onChange={(e) => setUpdateUsername(e.target.checked)}

                  />

                  用户名

                </label>

                <label className="checkbox-row">

                  <input

                    type="checkbox"

                    checked={updatePassword}

                    onChange={(e) => setUpdatePassword(e.target.checked)}

                  />

                  二级密码

                </label>

                <label className="checkbox-row">

                  <input

                    type="checkbox"

                    checked={remove2fa}

                    onChange={(e) => {

                      setRemove2fa(e.target.checked);

                      if (e.target.checked) setUpdatePassword(false);

                    }}

                  />

                  清除二级密码（忘记/关闭）

                </label>

              </div>

            </div>

            <div className="card">

              <h3>资料来源</h3>

              <label className="checkbox-row">

                <input

                  type="checkbox"

                  checked={useRandomConfig}

                  onChange={(e) => setUseRandomConfig(e.target.checked)}

                />

                从 data/配置/ 随机读取（名字、姓氏、用户名、简介）

              </label>

              {!useRandomConfig && (

                <div className="form-stack" style={{ marginTop: 12 }}>

                  <input

                    placeholder="姓氏"

                    value={lastName}

                    onChange={(e) => setLastName(e.target.value)}

                    disabled={!updateLastName}

                  />

                  <input

                    placeholder="名字"

                    value={firstName}

                    onChange={(e) => setFirstName(e.target.value)}

                    disabled={!updateFirstName}

                  />

                  <input

                    placeholder="用户名（不含 @）"

                    value={username}

                    onChange={(e) => setUsername(e.target.value)}

                    disabled={!updateUsername}

                  />

                  <textarea

                    placeholder="简介"

                    value={about}

                    onChange={(e) => setAbout(e.target.value)}

                    disabled={!updateAbout}

                    rows={3}

                  />

                </div>

              )}

              {(updatePassword || remove2fa) && (

                <div className="form-stack" style={{ marginTop: 12 }}>

                  <input

                    type="password"

                    placeholder={remove2fa ? "当前二级密码（必填）" : "旧二级密码（首次设置可留空）"}

                    value={oldPassword}

                    onChange={(e) => setOldPassword(e.target.value)}

                  />

                  {!remove2fa && (

                    <input

                      type="password"

                      placeholder="新二级密码"

                      value={newPassword}

                      onChange={(e) => setNewPassword(e.target.value)}

                    />

                  )}

                </div>

              )}

              <div className="config-status">

                {Object.entries(profileConfig).map(([key, val]) => (

                  <span key={key} className="config-chip">

                    {key}: {val.count ?? 0} 条

                  </span>

                ))}

              </div>

            </div>

            <div className="button-row">

              <button onClick={handleProfileUpdate} disabled={taskLoading || isRunning}>

                开始批量修改

              </button>

              {isRunning && (

                <button className="danger" onClick={stop} disabled={taskLoading}>

                  停止

                </button>

              )}

            </div>

          </div>

        </div>

      )}



      {chatAccountId && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
          onClick={() => setChatAccountId(null)}
        >
          <div
            className="card"
            style={{ width: 560, maxHeight: "80vh", overflow: "auto" }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3>聊天记录</h3>
            <p className="muted">账号: {chatAccountId}</p>
            <div className="form-stack">
              <input
                placeholder="目标：@用户名 或 群链接"
                value={chatTarget}
                onChange={(e) => setChatTarget(e.target.value)}
              />
              <button onClick={handleFetchChatHistory} disabled={chatLoading || !chatTarget.trim()}>
                {chatLoading ? "加载中..." : "获取记录"}
              </button>
            </div>
            {chatMessages.length > 0 && (
              <div style={{ marginTop: 12, maxHeight: 400, overflow: "auto" }}>
                {chatMessages.map((msg) => (
                  <div
                    key={msg.id}
                    style={{
                      padding: "6px 0",
                      borderBottom: "1px solid var(--border)",
                      textAlign: msg.out ? "right" : "left",
                    }}
                  >
                    <div className="muted" style={{ fontSize: 11 }}>
                      {msg.sender} · {msg.date}
                    </div>
                    <div>{msg.text || "(无文本)"}</div>
                  </div>
                ))}
              </div>
            )}
            <div className="button-row" style={{ marginTop: 12 }}>
              <button className="secondary" onClick={() => setChatAccountId(null)}>关闭</button>
            </div>
          </div>
        </div>
      )}

      {adAccountId && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
          onClick={() => setAdAccountId(null)}
        >
          <div
            className="card"
            style={{ width: 520, maxHeight: "80vh", overflow: "auto" }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3>账号独立广告语</h3>
            <p className="muted">账号: {adAccountId}。设置后群发时优先使用此内容，留空则删除独立广告。</p>
            <textarea
              rows={8}
              value={adDraft}
              onChange={(e) => setAdDraft(e.target.value)}
              placeholder="输入该账号专属广告，支持 *** 多话术"
            />
            <div className="button-row" style={{ marginTop: 12 }}>
              <button onClick={handleSaveCustomAd}>保存</button>
              <button className="secondary" onClick={() => setAdAccountId(null)}>取消</button>
            </div>
          </div>
        </div>
      )}

      {statusDetail && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
          onClick={() => setStatusDetail(null)}
        >
          <div
            className="card"
            style={{ width: 560, maxHeight: "80vh", overflow: "auto" }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3>账号状态 · SpamBot 全文</h3>
            <p className="muted">账号: {statusDetail.accountId}</p>
            <p><strong>{statusDetail.summary}</strong></p>
            {statusDetail.verifyLinks.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <p className="muted">验证链接（可手动打开提交）：</p>
                {statusDetail.verifyLinks.map((link) => (
                  <div key={link}>
                    <a href={link} target="_blank" rel="noreferrer">{link}</a>
                  </div>
                ))}
              </div>
            )}
            <pre style={{ whiteSpace: "pre-wrap", fontSize: 12, background: "rgba(0,0,0,0.25)", padding: 12, borderRadius: 8 }}>
              {statusDetail.fullText || "（无全文）"}
            </pre>
            <div className="button-row" style={{ marginTop: 12 }}>
              <button
                className="secondary"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(
                      [statusDetail.summary, statusDetail.fullText, ...statusDetail.verifyLinks].filter(Boolean).join("\n\n"),
                    );
                    toast.success("已复制全文");
                  } catch {
                    toast.error("复制失败");
                  }
                }}
              >
                复制全文
              </button>
              <button className="secondary" onClick={() => setStatusDetail(null)}>关闭</button>
            </div>
          </div>
        </div>
      )}

      {privacyOpen && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
          onClick={() => setPrivacyOpen(false)}
        >
          <div className="card" style={{ width: 480 }} onClick={(e) => e.stopPropagation()}>
            <h3>批量隐私设置</h3>
            <p className="muted">将应用到已勾选的 {checkedIds.length} 个账号</p>
            <div className="form-stack">
              <label>
                手机号可见性
                <select value={privacyPhone} onChange={(e) => setPrivacyPhone(e.target.value)}>
                  <option value="disallow_all">所有人不可见</option>
                  <option value="allow_all">所有人可见</option>
                </select>
              </label>
              <label>
                最后上线时间
                <select value={privacyLastSeen} onChange={(e) => setPrivacyLastSeen(e.target.value)}>
                  <option value="disallow_all">所有人不可见</option>
                  <option value="allow_all">所有人可见</option>
                </select>
              </label>
              <label>
                头像可见性
                <select value={privacyPhoto} onChange={(e) => setPrivacyPhoto(e.target.value)}>
                  <option value="allow_all">所有人可见</option>
                  <option value="disallow_all">所有人不可见</option>
                </select>
              </label>
              <label>
                邀请进群权限
                <select value={privacyInvite} onChange={(e) => setPrivacyInvite(e.target.value)}>
                  <option value="disallow_all">禁止被邀请</option>
                  <option value="allow_all">允许被邀请</option>
                </select>
              </label>
            </div>
            <div className="button-row" style={{ marginTop: 12 }}>
              <button onClick={applyPrivacyBatch} disabled={loading}>应用</button>
              <button className="secondary" onClick={() => setPrivacyOpen(false)}>取消</button>
            </div>
          </div>
        </div>
      )}

      {deviceAccountId && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
          onClick={() => setDeviceAccountId(null)}
        >
          <div
            className="card"
            style={{ width: 640, maxHeight: "80vh", overflow: "auto" }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3>在线设备 · {deviceAccountId}</h3>
            <p className="muted">可勾选后精踢；当前设备不可踢</p>
            {devicesLoading ? (
              <p className="muted">加载中...</p>
            ) : devices.length === 0 ? (
              <p className="muted">暂无设备数据</p>
            ) : (
              <div className="device-list">
                {devices.map((d) => (
                  <label key={String(d.hash)} className={`device-item${d.current ? " current" : ""}`}>
                    <input
                      type="checkbox"
                      disabled={d.current || !d.hash}
                      checked={selectedDeviceHashes.includes(Number(d.hash))}
                      onChange={() => {
                        const h = Number(d.hash);
                        setSelectedDeviceHashes((prev) =>
                          prev.includes(h) ? prev.filter((x) => x !== h) : [...prev, h],
                        );
                      }}
                    />
                    <div>
                      <div>
                        <strong>{d.device_model || d.app_name || "未知设备"}</strong>
                        {d.current && <span className="badge badge-online">当前</span>}
                      </div>
                      <div className="muted" style={{ fontSize: 12 }}>
                        {[d.platform, d.system_version, d.app_name, d.app_version].filter(Boolean).join(" · ")}
                      </div>
                      <div className="muted" style={{ fontSize: 12 }}>
                        {[d.ip, d.country, d.date_active].filter(Boolean).join(" · ")}
                      </div>
                    </div>
                  </label>
                ))}
              </div>
            )}
            <div className="button-row" style={{ marginTop: 12 }}>
              <button onClick={kickSelectedDevices} disabled={devicesLoading || selectedDeviceHashes.length === 0}>
                踢选中
              </button>
              <button className="secondary" onClick={kickAllOtherDevices} disabled={devicesLoading}>
                踢全部其他
              </button>
              <button className="secondary" onClick={() => setDeviceAccountId(null)}>
                关闭
              </button>
            </div>
          </div>
        </div>
      )}

    </div>

  );

}


