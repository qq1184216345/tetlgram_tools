import { useState } from "react";
import { api } from "../api/client";
import { AccountSelector } from "../components/AccountSelector";
import { usePersistedAccounts } from "../hooks/usePersistedAccounts";
import { parseLines, useTaskRunner } from "../hooks/useTaskRunner";

type Tab = "extract" | "profiles" | "online" | "comment" | "clone";

function parsePostLines(text: string): Array<{ channel: string; message_id: number; comment?: string }> {
  const posts: Array<{ channel: string; message_id: number; comment?: string }> = [];
  for (const line of parseLines(text)) {
    // https://t.me/channel/123 或 channel/123 或 https://t.me/channel/123|评论内容
    const [left, comment] = line.split("|").map((s) => s.trim());
    const m = left.match(/(?:https?:\/\/)?t\.me\/([A-Za-z0-9_]+)\/(\d+)/i)
      || left.match(/^@?([A-Za-z0-9_]+)\/(\d+)$/);
    if (!m) continue;
    posts.push({
      channel: m[1],
      message_id: Number(m[2]),
      comment: comment || undefined,
    });
  }
  return posts;
}

export function ExtractPage() {
  const [tab, setTab] = useState<Tab>("extract");
  const [selectedAccounts, setSelectedAccounts] = usePersistedAccounts();
  const [sourceLinks, setSourceLinks] = useState("");
  const [messageLimit, setMessageLimit] = useState(1000);
  const [threadCount, setThreadCount] = useState(1);
  const [extractLinks, setExtractLinks] = useState(true);
  const [extractUsernames, setExtractUsernames] = useState(true);
  const [savePath, setSavePath] = useState("");
  const [validateLinks, setValidateLinks] = useState(false);
  const [minMembers, setMinMembers] = useState(0);
  const [maxMembers, setMaxMembers] = useState(0);
  const [onlyGroups, setOnlyGroups] = useState(true);

  const [postLines, setPostLines] = useState("");
  const [comment, setComment] = useState("");
  const [commentIntervalMin, setCommentIntervalMin] = useState(10);
  const [commentIntervalMax, setCommentIntervalMax] = useState(30);

  const [cloneSource, setCloneSource] = useState("");
  const [cloneTitle, setCloneTitle] = useState("");
  const [cloneAbout, setCloneAbout] = useState("");
  const [cloneLimit, setCloneLimit] = useState(50);
  const [bindProfile, setBindProfile] = useState(true);

  const [profileTargets, setProfileTargets] = useState("");
  const [profileInterval, setProfileInterval] = useState(5);
  const [onlineBusy, setOnlineBusy] = useState(false);
  const [onlineMsg, setOnlineMsg] = useState("");
  const [onlineAccounts, setOnlineAccounts] = useState<string[]>([]);

  const { loading, isRunning, run, stop } = useTaskRunner(
    "extract_links",
    "channel_comment",
    "clone_channel",
    "scrape_profiles",
  );

  function handleStartExtract() {
    run(() =>
      api.startExtractLinks({
        account_ids: selectedAccounts,
        source_links: parseLines(sourceLinks),
        message_limit: messageLimit,
        thread_count: threadCount,
        extract_links: extractLinks,
        extract_usernames: extractUsernames,
        save_path: savePath,
        validate_links: validateLinks,
        min_members: minMembers,
        max_members: maxMembers,
        only_groups: onlyGroups,
      }),
      selectedAccounts,
      { requireAccounts: true },
    );
  }

  function handleStartComment() {
    run(() =>
      api.startChannelComment({
        account_ids: selectedAccounts,
        posts: parsePostLines(postLines),
        comment,
        interval_min: commentIntervalMin,
        interval_max: commentIntervalMax,
      }),
      selectedAccounts,
      { requireAccounts: true },
    );
  }

  function handleStartClone() {
    run(() =>
      api.startCloneChannel({
        account_ids: selectedAccounts,
        source: cloneSource.trim(),
        title: cloneTitle,
        about: cloneAbout,
        message_limit: cloneLimit,
        bind_to_profile: bindProfile,
      }),
      selectedAccounts,
      { requireAccounts: true },
    );
  }

  function handleStartProfiles() {
    run(() =>
      api.startScrapeProfiles({
        account_ids: selectedAccounts,
        targets: parseLines(profileTargets),
        interval_sec: profileInterval,
      }),
      selectedAccounts,
      { requireAccounts: true },
    );
  }

  async function refreshOnline() {
    try {
      const res = await api.getKeepOnline();
      setOnlineAccounts(res.accounts || []);
    } catch {
      setOnlineAccounts([]);
    }
  }

  async function handleKeepOnline(enable: boolean) {
    if (enable && !selectedAccounts.length) {
      setOnlineMsg("请先选择账号");
      return;
    }
    setOnlineBusy(true);
    setOnlineMsg("");
    try {
      const res = await api.setKeepOnline({
        account_ids: selectedAccounts,
        enable,
        interval_sec: 60,
      });
      setOnlineMsg(res.message || (enable ? "已启用" : "已停止"));
      await refreshOnline();
    } catch (e) {
      setOnlineMsg(e instanceof Error ? e.message : "操作失败");
    } finally {
      setOnlineBusy(false);
    }
  }

  return (
    <div className="task-page-layout">
      <div className="task-form">
        <div className="tab-bar">
          <button className={tab === "extract" ? "active" : ""} onClick={() => setTab("extract")}>
            提取链接
          </button>
          <button className={tab === "profiles" ? "active" : ""} onClick={() => setTab("profiles")}>
            用户资料
          </button>
          <button
            className={tab === "online" ? "active" : ""}
            onClick={() => {
              setTab("online");
              void refreshOnline();
            }}
          >
            保持在线
          </button>
          <button className={tab === "comment" ? "active" : ""} onClick={() => setTab("comment")}>
            评论频道帖子
          </button>
          <button className={tab === "clone" ? "active" : ""} onClick={() => setTab("clone")}>
            克隆频道
          </button>
        </div>

        <div className="card">
          <h3>选择账号</h3>
          <AccountSelector selected={selectedAccounts} onChange={setSelectedAccounts} />
        </div>

        {tab === "extract" && (
          <>
            <div className="card">
              <h3>频道 / 群组链接</h3>
              <p className="muted">每行一个，从消息记录中提取链接和 @用户名</p>
              <textarea
                rows={6}
                value={sourceLinks}
                onChange={(e) => setSourceLinks(e.target.value)}
                placeholder={"https://t.me/channelname\n@groupname"}
              />
            </div>
            <div className="card">
              <h3>提取选项</h3>
              <label>
                筛选消息条数
                <input
                  type="number"
                  value={messageLimit}
                  min={100}
                  max={10000}
                  onChange={(e) => setMessageLimit(Number(e.target.value))}
                />
              </label>
              <div className="interval-row">
                <label>
                  线程数
                  <input
                    type="number"
                    value={threadCount}
                    min={1}
                    max={10}
                    onChange={(e) => setThreadCount(Number(e.target.value))}
                  />
                </label>
              </div>
              <label className="checkbox-row">
                <input type="checkbox" checked={extractLinks} onChange={(e) => setExtractLinks(e.target.checked)} />
                提取链接
              </label>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={extractUsernames}
                  onChange={(e) => setExtractUsernames(e.target.checked)}
                />
                提取 @用户名
              </label>
              <label className="checkbox-row">
                <input type="checkbox" checked={validateLinks} onChange={(e) => setValidateLinks(e.target.checked)} />
                提取后筛选校验群链接
              </label>
              {validateLinks && (
                <>
                  <label className="checkbox-row">
                    <input type="checkbox" checked={onlyGroups} onChange={(e) => setOnlyGroups(e.target.checked)} />
                    仅保留群组（剔除纯频道）
                  </label>
                  <div className="interval-row">
                    <label>
                      最少人数
                      <input type="number" value={minMembers} min={0} onChange={(e) => setMinMembers(Number(e.target.value))} />
                    </label>
                    <label>
                      最多人数（0=不限）
                      <input type="number" value={maxMembers} min={0} onChange={(e) => setMaxMembers(Number(e.target.value))} />
                    </label>
                  </div>
                </>
              )}
            </div>
            <div className="card">
              <h3>保存路径</h3>
              <input
                value={savePath}
                onChange={(e) => setSavePath(e.target.value)}
                placeholder="留空则保存到 data/采集/综合功能提取链接.txt"
              />
              <p className="muted">格式对齐竞品：首行「时间戳:源链接」，其后混排 t.me 链接与 @用户名</p>
            </div>
            <div className="button-row">
              <button onClick={handleStartExtract} disabled={loading || isRunning}>
                开始提取
              </button>
              {isRunning && (
                <button className="danger" onClick={stop} disabled={loading}>
                  停止
                </button>
              )}
            </div>
          </>
        )}

        {tab === "profiles" && (
          <>
            <div className="card">
              <h3>采集用户资料</h3>
              <p className="muted">每行一个 @用户名；结果写入 data/采集/过滤用户.txt</p>
              <textarea
                rows={8}
                value={profileTargets}
                onChange={(e) => setProfileTargets(e.target.value)}
                placeholder={"@user1\n@user2"}
              />
              <label>
                间隔（秒）
                <input
                  type="number"
                  value={profileInterval}
                  min={0}
                  onChange={(e) => setProfileInterval(Number(e.target.value))}
                />
              </label>
            </div>
            <div className="button-row">
              <button onClick={handleStartProfiles} disabled={loading || isRunning}>
                开始采集
              </button>
              {isRunning && (
                <button className="danger" onClick={stop} disabled={loading}>
                  停止
                </button>
              )}
            </div>
          </>
        )}

        {tab === "online" && (
          <>
            <div className="card">
              <h3>维持账号在线</h3>
              <p className="muted">每分钟向收藏夹发一条心跳，保持在群内显示在线</p>
              <p className="muted">
                当前运行：{onlineAccounts.length ? onlineAccounts.join("、") : "无"}
              </p>
            </div>
            <div className="button-row">
              <button onClick={() => handleKeepOnline(true)} disabled={onlineBusy}>
                启用保持在线
              </button>
              <button className="danger" onClick={() => handleKeepOnline(false)} disabled={onlineBusy}>
                停止
              </button>
              <button onClick={() => void refreshOnline()} disabled={onlineBusy}>
                刷新状态
              </button>
            </div>
            {onlineMsg && <p className="muted">{onlineMsg}</p>}
          </>
        )}

        {tab === "comment" && (
          <>
            <div className="card">
              <h3>频道帖子</h3>
              <p className="muted">每行一个：https://t.me/频道/消息ID 或 频道/消息ID，可用 | 追加专属评论</p>
              <textarea
                rows={6}
                value={postLines}
                onChange={(e) => setPostLines(e.target.value)}
                placeholder={"https://t.me/channelname/123\nchannelname/456|专属评论"}
              />
            </div>
            <div className="card">
              <h3>默认评论内容</h3>
              <textarea rows={4} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="未写专属评论时使用此内容" />
              <div className="interval-row" style={{ marginTop: 12 }}>
                <label>
                  间隔最小（秒）
                  <input type="number" value={commentIntervalMin} min={1} onChange={(e) => setCommentIntervalMin(Number(e.target.value))} />
                </label>
                <label>
                  间隔最大（秒）
                  <input type="number" value={commentIntervalMax} min={1} onChange={(e) => setCommentIntervalMax(Number(e.target.value))} />
                </label>
              </div>
            </div>
            <div className="button-row">
              <button onClick={handleStartComment} disabled={loading || isRunning}>
                开始评论
              </button>
              {isRunning && (
                <button className="danger" onClick={stop} disabled={loading}>
                  停止
                </button>
              )}
            </div>
          </>
        )}

        {tab === "clone" && (
          <>
            <div className="card">
              <h3>克隆源频道</h3>
              <p className="muted">将源频道近期帖子复制到新建频道，并可绑定到个人主页展示</p>
              <label>
                源频道
                <input value={cloneSource} onChange={(e) => setCloneSource(e.target.value)} placeholder="@channel 或 https://t.me/channel" />
              </label>
              <label>
                新频道标题（留空沿用源标题）
                <input value={cloneTitle} onChange={(e) => setCloneTitle(e.target.value)} />
              </label>
              <label>
                简介
                <input value={cloneAbout} onChange={(e) => setCloneAbout(e.target.value)} />
              </label>
              <label>
                复制消息条数
                <input type="number" value={cloneLimit} min={1} max={500} onChange={(e) => setCloneLimit(Number(e.target.value))} />
              </label>
              <label className="checkbox-row">
                <input type="checkbox" checked={bindProfile} onChange={(e) => setBindProfile(e.target.checked)} />
                绑定到个人主页
              </label>
            </div>
            <div className="button-row">
              <button onClick={handleStartClone} disabled={loading || isRunning}>
                开始克隆
              </button>
              {isRunning && (
                <button className="danger" onClick={stop} disabled={loading}>
                  停止
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
