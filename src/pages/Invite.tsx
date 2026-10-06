import { useState } from "react";
import { api } from "../api/client";
import { AccountSelector } from "../components/AccountSelector";
import { StickyActions } from "../components/StickyActions";
import { useToast } from "../context/ToastContext";
import { usePersistedAccounts } from "../hooks/usePersistedAccounts";
import { parseLines, useTaskRunner } from "../hooks/useTaskRunner";

export function InvitePage() {
  const toast = useToast();
  const [selectedAccounts, setSelectedAccounts] = usePersistedAccounts();
  const [adminAccountId, setAdminAccountId] = useState("");
  const [groupLink, setGroupLink] = useState("");
  const [userTargets, setUserTargets] = useState("");
  const [intervalMin, setIntervalMin] = useState(60);
  const [intervalMax, setIntervalMax] = useState(120);
  const [makePublic, setMakePublic] = useState(false);
  const [accountLoopCount, setAccountLoopCount] = useState(1);
  const [stopAfterN, setStopAfterN] = useState(0);
  const [threadCount, setThreadCount] = useState(10);
  const [saveResultFiles, setSaveResultFiles] = useState(true);
  const [resultWithTimestamp, setResultWithTimestamp] = useState(true);
  const [adminBusy, setAdminBusy] = useState(false);
  const { loading, isRunning, run, stop } = useTaskRunner("invite");

  function handleStart() {
    run(() =>
      api.startInvite({
        account_ids: selectedAccounts,
        group_link: groupLink.trim(),
        user_targets: parseLines(userTargets),
        interval_min: intervalMin,
        interval_max: intervalMax,
        make_public: makePublic,
        account_loop_count: accountLoopCount,
        stop_after_n: stopAfterN,
        thread_count: threadCount,
        save_result_files: saveResultFiles,
        result_with_timestamp: resultWithTimestamp,
      }),
      selectedAccounts,
      { requireAccounts: true },
    );
  }

  async function handleSetAdmins(promote: boolean) {
    const adminId = adminAccountId.trim() || selectedAccounts[0] || "";
    if (!adminId) {
      toast.error("请填写主管理员账号（需有添加管理员权限）");
      return;
    }
    if (!groupLink.trim()) {
      toast.error("请填写目标群组");
      return;
    }
    if (selectedAccounts.length === 0) {
      toast.error("请先勾选要设为拉人号的账号");
      return;
    }
    setAdminBusy(true);
    try {
      const res = await api.setInviteAdmins({
        admin_account_id: adminId,
        group_link: groupLink.trim(),
        account_ids: selectedAccounts,
        promote,
      });
      if (res.success) toast.success(res.message);
      else toast.error(res.message || "操作失败");
      const fails = (res.data?.results || []).filter((r) => !r.ok);
      for (const f of fails.slice(0, 5)) {
        toast.error(`[${f.account_id}] ${f.message}`);
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "设管失败");
    } finally {
      setAdminBusy(false);
    }
  }

  return (
    <div className="task-page-layout">
      <div className="task-form">
        <div className="card">
          <h3>选择拉人账号</h3>
          <AccountSelector selected={selectedAccounts} onChange={setSelectedAccounts} />
        </div>

        <div className="card">
          <h3>目标群组</h3>
          <input
            value={groupLink}
            onChange={(e) => setGroupLink(e.target.value)}
            placeholder="https://t.me/yourgroup 或 @groupname"
          />
        </div>

        <div className="card">
          <h3>设管理员（建议先做）</h3>
          <p className="tip-banner">
            非管理员号拉不动多少人。请先用主管理号把上方勾选账号设为「可拉人」管理员，再开始拉人。
            小号需已在群内。
          </p>
          <label>
            主管理员账号（填手机号/账号 ID，默认用勾选列表第一个）
            <input
              value={adminAccountId}
              onChange={(e) => setAdminAccountId(e.target.value)}
              placeholder={selectedAccounts[0] || "主管理账号"}
            />
          </label>
          <div className="button-row" style={{ marginTop: 10 }}>
            <button
              className="secondary"
              disabled={adminBusy || isRunning}
              onClick={() => handleSetAdmins(true)}
            >
              批量设为拉人管理员
            </button>
            <button
              className="secondary danger"
              disabled={adminBusy || isRunning}
              onClick={() => handleSetAdmins(false)}
            >
              批量取消管理员
            </button>
          </div>
        </div>

        <div className="card">
          <h3>要拉入的用户</h3>
          <p className="muted">每行一个：手机号或 @用户名（可使用采集结果）</p>
          <textarea
            rows={6}
            value={userTargets}
            onChange={(e) => setUserTargets(e.target.value)}
            placeholder={"+8613800138000\n@username"}
          />
        </div>

        <div className="card">
          <h3>拉人间隔（秒）</h3>
          <p className="muted">按账号独立冷却，多号不会互相卡住</p>
          <div className="interval-row">
            <label>
              最小
              <input
                type="number"
                value={intervalMin}
                onChange={(e) => setIntervalMin(Number(e.target.value))}
                min={1}
              />
            </label>
            <label>
              最大
              <input
                type="number"
                value={intervalMax}
                onChange={(e) => setIntervalMax(Number(e.target.value))}
                min={1}
              />
            </label>
          </div>
        </div>

        <div className="card">
          <h3>高级选项</h3>
          <label className="checkbox-row">
            <input type="checkbox" checked={makePublic}
              onChange={(e) => setMakePublic(e.target.checked)} />
            拉人前设为公开群
          </label>
          <div className="interval-row">
            <label>
              账号循环次数
              <input type="number" value={accountLoopCount} min={1}
                onChange={(e) => setAccountLoopCount(Number(e.target.value))} />
            </label>
            <label>
              成功 N 人后停止（0=不限）
              <input type="number" value={stopAfterN} min={0}
                onChange={(e) => setStopAfterN(Number(e.target.value))} />
            </label>
            <label>
              线程数
              <input type="number" value={threadCount} min={1} max={10}
                onChange={(e) => setThreadCount(Number(e.target.value))} />
            </label>
          </div>
          <label className="checkbox-row" style={{ marginTop: 8 }}>
            <input type="checkbox" checked={saveResultFiles} onChange={(e) => setSaveResultFiles(e.target.checked)} />
            写入成功/失败文件（data/日志/拉人成功.txt、拉人失败.txt）
          </label>
          <label className="checkbox-row">
            <input type="checkbox" checked={resultWithTimestamp}
              onChange={(e) => setResultWithTimestamp(e.target.checked)} disabled={!saveResultFiles} />
            结果文件附带时间戳
          </label>
        </div>

        <StickyActions summary={<>已选 {selectedAccounts.length} 个拉人号</>}>
          <button onClick={handleStart} disabled={loading || isRunning}>
            开始拉人
          </button>
          {isRunning && (
            <button className="danger" onClick={stop} disabled={loading}>
              停止任务
            </button>
          )}
        </StickyActions>
      </div>
    </div>
  );
}
