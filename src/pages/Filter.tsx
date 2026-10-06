import { useState } from "react";
import { api } from "../api/client";
import { AccountSelector } from "../components/AccountSelector";
import { StickyActions } from "../components/StickyActions";
import { usePersistedAccounts } from "../hooks/usePersistedAccounts";
import { parseLines, useTaskRunner } from "../hooks/useTaskRunner";

type FilterMode = "caps" | "ad_length";

export function FilterPage() {
  const [selectedAccounts, setSelectedAccounts] = usePersistedAccounts();
  const [titleKeyword, setTitleKeyword] = useState("");
  const [groupLinks, setGroupLinks] = useState("");
  const [minMembers, setMinMembers] = useState(1000);
  const [maxMembers, setMaxMembers] = useState(10000);
  const [requireSticker, setRequireSticker] = useState(false);
  const [requireForum, setRequireForum] = useState(false);
  const [requireSendText, setRequireSendText] = useState(true);
  const [requireSendLinks, setRequireSendLinks] = useState(true);
  const [requireSendPhotos, setRequireSendPhotos] = useState(false);
  const [requireSendVideos, setRequireSendVideos] = useState(false);
  const [excludeBotAdmins, setExcludeBotAdmins] = useState(false);
  const [mode, setMode] = useState<FilterMode>("caps");
  const [adMessageLimit, setAdMessageLimit] = useState(10);
  const [maxAdChars, setMaxAdChars] = useState(150);
  const [intervalSec, setIntervalSec] = useState(5);
  const [exportBusy, setExportBusy] = useState(false);
  const [exportMsg, setExportMsg] = useState("");
  const { loading, isRunning, run, stop } = useTaskRunner("filter_groups");

  function handleStart() {
    run(() =>
      api.startFilterGroups({
        account_ids: selectedAccounts,
        title_keyword: titleKeyword,
        min_members: minMembers,
        max_members: maxMembers,
        require_sticker: requireSticker,
        require_forum: requireForum,
        require_send_text: requireSendText,
        require_send_links: requireSendLinks,
        require_send_photos: requireSendPhotos,
        require_send_videos: requireSendVideos,
        exclude_bot_admins: excludeBotAdmins,
        group_links: parseLines(groupLinks),
        mode,
        ad_message_limit: adMessageLimit,
        max_ad_chars: maxAdChars,
        interval_sec: intervalSec,
      }),
      selectedAccounts,
      { requireAccounts: true },
    );
  }

  async function handleExport(exportMode: "all" | "addlist" | "both") {
    if (!selectedAccounts.length) {
      setExportMsg("请先选择账号");
      return;
    }
    setExportBusy(true);
    setExportMsg("");
    try {
      const res = await api.exportAccountGroups({
        account_ids: selectedAccounts,
        mode: exportMode,
      });
      setExportMsg(res.message || "导出完成");
    } catch (e) {
      setExportMsg(e instanceof Error ? e.message : "导出失败");
    } finally {
      setExportBusy(false);
    }
  }

  return (
    <div className="task-page-layout">
      <div className="task-form">
        <div className="card">
          <h3>选择账号</h3>
          <AccountSelector selected={selectedAccounts} onChange={setSelectedAccounts} />
          <p className="muted">留空链接列表时，扫描该账号已加入的群组；填写链接则按链接筛选</p>
        </div>

        <div className="card">
          <h3>筛群模式</h3>
          <div className="interval-row">
            <label className="checkbox-row">
              <input
                type="radio"
                name="filter-mode"
                checked={mode === "caps"}
                onChange={() => setMode("caps")}
              />
              方式一：人数 + 可发权限
            </label>
            <label className="checkbox-row">
              <input
                type="radio"
                name="filter-mode"
                checked={mode === "ad_length"}
                onChange={() => setMode("ad_length")}
              />
              方式二：长短广告分类
            </label>
          </div>
          <label>
            筛群间隔（秒）
            <input
              type="number"
              value={intervalSec}
              min={0}
              onChange={(e) => setIntervalSec(Number(e.target.value))}
            />
          </label>
        </div>

        <div className="card">
          <h3>群链接（可选）</h3>
          <textarea
            rows={5}
            value={groupLinks}
            onChange={(e) => setGroupLinks(e.target.value)}
            placeholder={"https://t.me/group1\n@group2\n留空=扫描已加入群"}
          />
        </div>

        {mode === "caps" ? (
          <div className="card">
            <h3>筛选条件（方式一）</h3>
            <div className="form-stack">
              <label>
                群名称关键词（留空匹配全部）
                <input
                  value={titleKeyword}
                  onChange={(e) => setTitleKeyword(e.target.value)}
                  placeholder="例如：交易、副业"
                />
              </label>
              <div className="interval-row">
                <label>
                  最少成员数
                  <input
                    type="number"
                    value={minMembers}
                    onChange={(e) => setMinMembers(Number(e.target.value))}
                    min={0}
                  />
                </label>
                <label>
                  最多成员数（0=不限）
                  <input
                    type="number"
                    value={maxMembers}
                    onChange={(e) => setMaxMembers(Number(e.target.value))}
                    min={0}
                  />
                </label>
              </div>
              <label className="checkbox-row">
                <input type="checkbox" checked={requireSendText}
                  onChange={(e) => setRequireSendText(e.target.checked)} />
                可发文字
              </label>
              <label className="checkbox-row">
                <input type="checkbox" checked={requireSendLinks}
                  onChange={(e) => setRequireSendLinks(e.target.checked)} />
                可发链接
              </label>
              <label className="checkbox-row">
                <input type="checkbox" checked={requireSendPhotos}
                  onChange={(e) => setRequireSendPhotos(e.target.checked)} />
                可发图片
              </label>
              <label className="checkbox-row">
                <input type="checkbox" checked={requireSendVideos}
                  onChange={(e) => setRequireSendVideos(e.target.checked)} />
                可发视频
              </label>
              <label className="checkbox-row">
                <input type="checkbox" checked={requireSticker}
                  onChange={(e) => setRequireSticker(e.target.checked)} />
                可发贴纸
              </label>
              <label className="checkbox-row">
                <input type="checkbox" checked={excludeBotAdmins}
                  onChange={(e) => setExcludeBotAdmins(e.target.checked)} />
                排除有机器人管理的群
              </label>
              <label className="checkbox-row">
                <input type="checkbox" checked={requireForum}
                  onChange={(e) => setRequireForum(e.target.checked)} />
                仅话题/论坛群（Forum）
              </label>
              <p className="muted">结果写入 data/采集/符合要求群链接.txt</p>
            </div>
          </div>
        ) : (
          <div className="card">
            <h3>长短广告（方式二）</h3>
            <p className="muted">
              读取最近 N 条消息：字数都小于阈值 → 短广告群；否则 → 长广告群
            </p>
            <div className="interval-row">
              <label>
                最新消息条数 N
                <input
                  type="number"
                  value={adMessageLimit}
                  min={1}
                  max={100}
                  onChange={(e) => setAdMessageLimit(Number(e.target.value))}
                />
              </label>
              <label>
                广告字数都要小于
                <input
                  type="number"
                  value={maxAdChars}
                  min={1}
                  onChange={(e) => setMaxAdChars(Number(e.target.value))}
                />
              </label>
            </div>
            <p className="muted">结果：筛群短广告群.txt / 筛群长广告群.txt</p>
          </div>
        )}

        <StickyActions summary={<>已选 {selectedAccounts.length} 个账号</>}>
          <button onClick={handleStart} disabled={loading || isRunning}>
            开始筛选
          </button>
          {isRunning && (
            <button className="danger" onClick={stop} disabled={loading}>
              停止
            </button>
          )}
        </StickyActions>

        <div className="card">
          <h3>导出登录账号群链接</h3>
          <p className="muted">
            「一键加群」会生成 Telegram 官方 addlist 文件夹链接（https://t.me/addlist/...）
          </p>
          <div className="button-row">
            <button onClick={() => handleExport("addlist")} disabled={exportBusy}>
              导出账号分组链接（一键加群）
            </button>
            <button onClick={() => handleExport("all")} disabled={exportBusy}>
              导出账号全部群链接
            </button>
            <button onClick={() => handleExport("both")} disabled={exportBusy}>
              全部导出
            </button>
          </div>
          {exportMsg && <p className="muted">{exportMsg}</p>}
        </div>
      </div>
    </div>
  );
}
