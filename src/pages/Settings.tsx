import { useEffect, useMemo, useState } from "react";
import { api, ApiPreset, AppConfig, DeviceProfile } from "../api/client";
import { useToast } from "../context/ToastContext";
import { checkForAppUpdate } from "../lib/checkUpdate";
import { startAppUpdate } from "../lib/installUpdate";
import { useRegisterPageAction } from "../context/PageHeroContext";

const PROXY_PRESETS = [
  { label: "Clash", value: "127.0.0.1:7890", proxy_type: "http" },
  { label: "V2ray", value: "127.0.0.1:10809", proxy_type: "socks5" },
  { label: "QuickQ", value: "127.0.0.1:10900", proxy_type: "socks5" },
  { label: "Nekoray", value: "127.0.0.1:2080", proxy_type: "socks5" },
];

type AppInfo = {
  version: string;
  data_dir: string;
  project_root: string;
  backend_host: string;
  backend_port: number;
  suggested_data_dir: string;
  update_manifest_url: string;
};

export function SettingsPage() {
  const toast = useToast();
  const [config, setConfig] = useState<AppConfig>({
    api_id: 0,
    api_hash: "",
    socks5_ip: "",
    socks5_port: 0,
    proxy_state: false,
    proxy_type: "socks5",
    proxy_list: "",
    use_system_proxy: false,
    success_account_path: "",
    failed_account_path: "",
    ai_api_url: "",
    ai_api_key: "",
    ai_model: "gpt-4o-mini",
    ai_verify_enabled: false,
    device_profile: "apple_desktop",
  });
  const [apiPresets, setApiPresets] = useState<ApiPreset[]>([]);
  const [deviceProfiles, setDeviceProfiles] = useState<DeviceProfile[]>([]);
  const [apiPresetId, setApiPresetId] = useState("custom");
  const [appInfo, setAppInfo] = useState<AppInfo | null>(null);
  const [customDataDir, setCustomDataDir] = useState("");
  const [checkingUpdate, setCheckingUpdate] = useState(false);
  const [probingProxies, setProbingProxies] = useState(false);

  useEffect(() => {
    api.getConfig().then(setConfig).catch(() => {});
    api.getApiPresets().then(setApiPresets).catch(() => {});
    api.getDeviceProfiles().then(setDeviceProfiles).catch(() => {});
    api
      .getAppInfo()
      .then((info) => {
        setAppInfo(info);
        setCustomDataDir(info.suggested_data_dir);
      })
      .catch(() => {});
  }, []);

  const multiOpenCommand = useMemo(() => {
    const dataDir = (customDataDir || appInfo?.suggested_data_dir || "").trim();
    const root = appInfo?.project_root || "E:\\project\\AiProject\\TelegramTools";
    if (!dataDir) return "";
    return [
      `$env:PAPERWING_DATA = "${dataDir}"`,
      `cd "${root}"`,
      `.\\dev.bat`,
    ].join("; ");
  }, [appInfo, customDataDir]);

  function applyApiPreset(presetId: string) {
    setApiPresetId(presetId);
    const preset = apiPresets.find((p) => p.id === presetId);
    if (preset && presetId !== "custom") {
      setConfig((prev) => ({
        ...prev,
        api_id: Number(preset.api_id),
        api_hash: String(preset.api_hash),
      }));
    }
  }

  async function handleSave() {
    try {
      await api.saveConfig(config);
      toast.success("配置已保存");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "保存失败");
    }
  }

  useRegisterPageAction("settings", () => void handleSave(), "保存配置");

  async function handleDetectProxy() {
    try {
      const result = await api.detectSystemProxy();
      if (result.success && result.data?.proxy) {
        const found = String(result.data.proxy);
        const isHttp = found.startsWith("http://") || found.startsWith("https://");
        setConfig((prev) => ({
          ...prev,
          proxy_state: true,
          use_system_proxy: true,
          proxy_type: isHttp ? "http" : found.startsWith("socks") ? "socks5" : "http",
          proxy_list: found.replace(/^https?:\/\//, "").replace(/^socks5:\/\//, ""),
        }));
        toast.success(`已检测到系统代理: ${found}`);
      } else {
        toast.info(result.message || "未检测到系统代理");
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "检测失败");
    }
  }

  async function handleProbeProxies() {
    const list = (config.proxy_list || "").trim();
    if (!list) {
      toast.error("代理列表是空的");
      return;
    }
    setProbingProxies(true);
    try {
      const result = await api.probeProxies(config.proxy_type || "socks5", list);
      const items = Array.isArray(result.data?.items)
        ? (result.data.items as Array<{ line?: string; ok?: boolean }>)
        : [];
      const dead = items.filter((item) => !item.ok).slice(0, 3);
      if (!result.success && dead.length === 0) {
        toast.error(result.message || "检测失败");
        return;
      }
      if (dead.length) {
        toast.info(
          `${result.message}。不通：${dead.map((item) => item.line).filter(Boolean).join("；")}`,
        );
      } else {
        toast.success(result.message);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "检测失败");
    } finally {
      setProbingProxies(false);
    }
  }

  async function handleTestProxy() {
    toast.info("正在按当前页面配置测试 Telegram 连接...");
    try {
      await api.saveConfig(config);
      const result = await api.testProxy({
        proxy_state: config.proxy_state,
        use_system_proxy: config.use_system_proxy,
        proxy_type: config.proxy_type,
        proxy_list: config.proxy_list,
      });
      if (result.success) {
        toast.success(result.message || "连接成功");
      } else {
        toast.error(result.message || "连接失败");
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "测试失败");
    }
  }

  async function copyText(text: string, okMsg: string) {
    try {
      await navigator.clipboard.writeText(text);
      toast.success(okMsg);
    } catch {
      toast.error("复制失败，请手动选择文本");
    }
  }

  async function handleCheckUpdate() {
    if (!appInfo) {
      toast.error("无法获取版本信息");
      return;
    }
    setCheckingUpdate(true);
    try {
      const result = await checkForAppUpdate(appInfo.version);
      if (result.status === "error") {
        toast.error(result.message);
        return;
      }
      if (result.status === "latest") {
        toast.success(`已是最新版本 ${result.local}`);
        return;
      }
      const tip = [
        `发现新版本 ${result.remote}（当前 ${result.local}）`,
        result.force ? "此版本为强制更新" : "",
        result.notes ? `说明: ${result.notes}` : "",
      ]
        .filter(Boolean)
        .join("\n");
      if (!result.url) {
        toast.error(`${tip}\n请联系客服获取安装包`);
        return;
      }
      if (confirm(`${tip}\n\n是否立即下载并安装？软件将关闭并打开安装程序。`)) {
        toast.info("正在下载安装包...");
        await startAppUpdate(result.url);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "检查更新失败");
    } finally {
      setCheckingUpdate(false);
    }
  }

  return (
    <div className="settings-page">
      <div className="settings-col">
      <div className="card">
        <h3>Telegram API 配置</h3>
        <p className="muted">
          请在{" "}
          <a href="https://my.telegram.org" target="_blank" rel="noreferrer">
            my.telegram.org
          </a>{" "}
          申请自己的 api_id 和 api_hash。
        </p>
        <div className="form-stack">
          <label>
            API 预设
            <select value={apiPresetId} onChange={(e) => applyApiPreset(e.target.value)}>
              {apiPresets.map((preset) => (
                <option key={preset.id} value={preset.id}>
                  {preset.label}
                </option>
              ))}
              {apiPresets.length === 0 && <option value="custom">自定义</option>}
            </select>
          </label>
          <label>
            API ID
            <input
              type="number"
              value={config.api_id || ""}
              onChange={(e) => setConfig({ ...config, api_id: Number(e.target.value) })}
            />
          </label>
          <label>
            API Hash
            <input
              value={config.api_hash}
              onChange={(e) => setConfig({ ...config, api_hash: e.target.value })}
            />
          </label>
        </div>
      </div>

      <div className="card">
        <h3>登录设备指纹</h3>
        <p className="muted">
          模拟官方客户端设备信息上报。建议与 API 预设大致匹配（如 Desktop API + 苹果/Windows 桌面）。
          修改后需重新连接账号才会生效；已登录 session 换指纹可能触发二次验证。
        </p>
        <div className="form-stack">
          <label>
            开发者登录端
            <select
              value={config.device_profile || "apple_desktop"}
              onChange={(e) => setConfig({ ...config, device_profile: e.target.value })}
            >
              {(deviceProfiles.length
                ? deviceProfiles
                : [
                    { id: "apple_desktop", label: "苹果桌面（推荐）", device_model: "", system_version: "", app_version: "" },
                    { id: "windows_desktop", label: "Windows 桌面", device_model: "", system_version: "", app_version: "" },
                    { id: "android", label: "Android 手机", device_model: "", system_version: "", app_version: "" },
                    { id: "ios", label: "iPhone", device_model: "", system_version: "", app_version: "" },
                    { id: "default", label: "默认（Telethon）", device_model: "", system_version: "", app_version: "" },
                  ]
              ).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
          {!!deviceProfiles.find((p) => p.id === (config.device_profile || "apple_desktop")) && (
            <p className="muted" style={{ margin: 0 }}>
              {(() => {
                const p = deviceProfiles.find((x) => x.id === (config.device_profile || "apple_desktop"));
                return p
                  ? `${p.device_model} · ${p.system_version} · App ${p.app_version}`
                  : "";
              })()}
            </p>
          )}
        </div>
      </div>

      <div className="card">
        <h3>代理配置</h3>
        <p className="muted">
          在下面填写 HTTP 或 SOCKS 代理，每行一个。带 `http://` 或 `socks5://` 的行会各自保留协议。若用 FlClash / Clash，直接填本机端口（常见是 127.0.0.1:7890，类型选 HTTP），所有账号会走当前选中的那一个节点。要一人一个出口，把多条代理填进列表，再到账号列表点「按节点分配」。
        </p>
        <div className="form-stack">
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={config.proxy_state}
              onChange={(e) => setConfig({ ...config, proxy_state: e.target.checked })}
            />
            启用代理
          </label>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={config.use_system_proxy}
              onChange={(e) => setConfig({ ...config, use_system_proxy: e.target.checked })}
            />
            自动检测系统 HTTP 代理
          </label>
          <label>
            代理类型
            <select
              value={config.proxy_type}
              onChange={(e) => setConfig({ ...config, proxy_type: e.target.value })}
            >
              <option value="socks5">SOCKS5</option>
              <option value="http">HTTP 代理</option>
            </select>
          </label>
          <label>
            代理列表（每行一个）
            <textarea
              rows={5}
              value={config.proxy_list}
              onChange={(e) => setConfig({ ...config, proxy_list: e.target.value })}
              placeholder={"127.0.0.1:7890\n127.0.0.1:1080:user:pass"}
            />
          </label>
          <div className="button-row">
            {PROXY_PRESETS.map((preset) => (
              <button
                key={preset.label}
                type="button"
                className="secondary"
                onClick={() =>
                  setConfig((prev) => ({
                    ...prev,
                    proxy_state: true,
                    proxy_type: preset.proxy_type,
                    proxy_list: preset.value,
                  }))
                }
              >
                {preset.label}
              </button>
            ))}
            <button className="secondary" onClick={handleProbeProxies} disabled={probingProxies}>
              {probingProxies ? "检测中..." : "检测列表端口"}
            </button>
            <button className="secondary" onClick={handleDetectProxy}>
              检测系统代理
            </button>
            <button className="secondary" onClick={handleTestProxy}>
              测试网络连接
            </button>
          </div>
          <label>
            成功账号保存路径
            <input
              value={config.success_account_path}
              onChange={(e) => setConfig({ ...config, success_account_path: e.target.value })}
              placeholder="留空使用默认目录"
            />
          </label>
          <label>
            失效账号保存路径
            <input
              value={config.failed_account_path}
              onChange={(e) => setConfig({ ...config, failed_account_path: e.target.value })}
              placeholder="留空使用默认目录"
            />
          </label>
        </div>
      </div>
      </div>

      <div className="settings-col">
      <div className="card">
        <h3>AI 中转站（复杂加群验证）</h3>
        <p className="muted">
          兼容 OpenAI Chat Completions 接口。开启后，加群智能验证规则未命中时会请求大模型。
        </p>
        <div className="button-row" style={{ marginBottom: 12 }}>
          <button
            type="button"
            onClick={() =>
              setConfig({
                ...config,
                ai_api_url: "https://api.minimaxi.com/v1",
                ai_model: "MiniMax-M3",
                ai_verify_enabled: true,
              })
            }
          >
            填入 MiniMax（国内）
          </button>
          <button
            type="button"
            onClick={() =>
              setConfig({
                ...config,
                ai_api_url: "https://api.minimax.io/v1",
                ai_model: "MiniMax-M3",
                ai_verify_enabled: true,
              })
            }
          >
            填入 MiniMax（国际）
          </button>
        </div>
        <div className="form-stack">
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={config.ai_verify_enabled}
              onChange={(e) => setConfig({ ...config, ai_verify_enabled: e.target.checked })}
            />
            启用 AI 过复杂群验证
          </label>
          <label>
            API 地址（如 https://api.minimaxi.com/v1 或中转站 /v1）
            <input
              value={config.ai_api_url}
              onChange={(e) => setConfig({ ...config, ai_api_url: e.target.value })}
              placeholder="https://api.minimaxi.com/v1"
            />
          </label>
          <label>
            API Key
            <input
              type="password"
              value={config.ai_api_key}
              onChange={(e) => setConfig({ ...config, ai_api_key: e.target.value })}
              placeholder="sk-cp-..."
            />
          </label>
          <label>
            模型名
            <input
              value={config.ai_model}
              onChange={(e) => setConfig({ ...config, ai_model: e.target.value })}
              placeholder="MiniMax-M3"
            />
          </label>
        </div>
      </div>

      <div className="card">
        <h3>协议号登录官方 Telegram 客户端</h3>
        <p className="muted">用于在官方 App / Desktop 上手动管理协议号（接码、看验证码、养号）。</p>
        <ol className="help-steps">
          <li>先在本软件「账号中心」登录该协议号并保持连接。</li>
          <li>打开官方 Telegram，输入该号手机号，点下一步请求验证码。</li>
          <li>
            回到本软件：打开该账号聊天记录，找到与 <code>777000</code> / Telegram 的对话，复制最新验证码填回官方客户端。
          </li>
          <li>
            若提示二级密码：打开对应 session 旁的 <code>.json</code>，查找 <code>twoFA</code> / <code>2fa</code> 字段填入。
          </li>
        </ol>
        <p className="tip-banner">
          注意：同号多端同时操作有掉线风险；验证码也可能发到其它已在线设备而不是短信。
        </p>
      </div>

      <div className="card">
        <h3>软件多开向导</h3>
        <p className="muted">
          每个实例使用独立数据目录，避免 session / 配置 / 任务互相冲突。复制下面命令到新的 PowerShell 窗口运行即可。
        </p>
        <div className="form-stack">
          <label>
            当前数据目录
            <input value={appInfo?.data_dir || "加载中..."} readOnly />
          </label>
          <label>
            第二实例数据目录（可改）
            <input
              value={customDataDir}
              onChange={(e) => setCustomDataDir(e.target.value)}
              placeholder="例如 E:\PaperWing-data-2"
            />
          </label>
          <label>
            启动命令（PowerShell）
            <textarea rows={3} value={multiOpenCommand} readOnly />
          </label>
        </div>
        <div className="button-row" style={{ marginTop: 8 }}>
          <button
            type="button"
            className="secondary"
            onClick={() => copyText(multiOpenCommand, "多开命令已复制")}
            disabled={!multiOpenCommand}
          >
            复制启动命令
          </button>
          <button
            type="button"
            className="secondary"
            onClick={() =>
              copyText(customDataDir || appInfo?.suggested_data_dir || "", "数据目录已复制")
            }
          >
            复制数据目录
          </button>
        </div>
        <p className="muted" style={{ marginTop: 8 }}>
          生产环境也可直接复制整份安装目录，各目录内 data/ 天然隔离。
        </p>
      </div>

      <div className="card">
        <h3>关于与更新</h3>
        <p className="muted">
          当前版本：{appInfo?.version || "—"} · 后端：
          {appInfo ? `${appInfo.backend_host}:${appInfo.backend_port}` : "—"}
        </p>
        <div className="button-row">
          <button type="button" className="secondary" onClick={handleCheckUpdate} disabled={checkingUpdate}>
            {checkingUpdate ? "检查中..." : "检查更新"}
          </button>
        </div>
        <p className="muted" style={{ marginTop: 8 }}>
          更新清单由授权云管理后台「版本」页维护（公开接口 /app/version）。检查更新会比对版本并提示下载；勾选强制更新时客户端会拦截旧版。
        </p>
      </div>

      <div className="card">
        <h3>注意事项</h3>
        <ul className="notes-list">
          <li>建议使用非中国大陆 IP，并设置合理的发送间隔（群发/私信默认已提高到 60–120 秒）</li>
          <li>协议号尽量使用 session + 同名 json 一起导入，耐用性更好</li>
          <li>新号私信请先开「试发模式」测额度；PeerFlood 后勿狂点重试</li>
          <li>任务运行中请勿重复登录或切换账号，以免连接冲突</li>
          <li>停止任务需等待当前线程完成；暂停可临时挂起任务</li>
          <li>多代理 IP 会按账号自动轮换分配</li>
          <li>语音通话为实验功能，不可替代官方客户端通话</li>
        </ul>
      </div>
      </div>
    </div>
  );
}
