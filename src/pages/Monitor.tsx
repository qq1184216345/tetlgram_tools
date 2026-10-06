import { useState } from "react";
import { api } from "../api/client";
import { AccountSelector } from "../components/AccountSelector";
import { usePersistedAccounts } from "../hooks/usePersistedAccounts";
import { parseLines, useTaskRunner } from "../hooks/useTaskRunner";



type MonitorMode = "dm_forward" | "keyword";



export function MonitorPage() {

  const [selectedAccounts, setSelectedAccounts] = usePersistedAccounts();

  const [mode, setMode] = useState<MonitorMode>("dm_forward");

  const [replyMessage, setReplyMessage] = useState("");

  const [parseMode, setParseMode] = useState("");

  const [forwardGroupLink, setForwardGroupLink] = useState("");

  const [monitorGroupPosts, setMonitorGroupPosts] = useState(false);

  const [keywords, setKeywords] = useState("");

  const [notifyGroupLink, setNotifyGroupLink] = useState("");

  const [dmOnMatch, setDmOnMatch] = useState("");

  const [globalMatch, setGlobalMatch] = useState(false);

  const [autoSpambot, setAutoSpambot] = useState(false);

  const { loading, isRunning, run, stop } = useTaskRunner("monitor");



  function handleStart() {

    run(() =>

      api.startMonitor({

        account_ids: selectedAccounts,

        mode,

        reply_message: replyMessage,

        parse_mode: parseMode || null,

        forward_group_link: forwardGroupLink,

        monitor_group_posts: monitorGroupPosts,

        keywords: parseLines(keywords),

        notify_group_link: notifyGroupLink,

        dm_on_match: dmOnMatch,

        global_match: globalMatch,

        auto_spambot_unban: autoSpambot,

      }),

      selectedAccounts,
      { requireAccounts: true },
    );

  }



  return (

    <div className="broadcast-page">

      <div className="tab-bar">

        <button

          className={mode === "dm_forward" ? "active" : ""}

          onClick={() => setMode("dm_forward")}

        >

          模式一：私信转发

        </button>

        <button

          className={mode === "keyword" ? "active" : ""}

          onClick={() => setMode("keyword")}

        >

          模式二：关键词监控

        </button>

      </div>



      <div className="task-page-layout">

        <div className="task-form">

          <div className="card">

            <h3>选择账号</h3>

            <AccountSelector selected={selectedAccounts} onChange={setSelectedAccounts} />

            <label className="checkbox-row">

              <input

                type="checkbox"

                checked={autoSpambot}

                onChange={(e) => setAutoSpambot(e.target.checked)}

              />

              账号受限时自动向 SpamBot 申请解封

            </label>

          </div>



          {mode === "dm_forward" ? (

            <>

              <div className="card">

                <h3>私信自动回复 + 转发到群</h3>

                <p className="muted">

                  收到私信后自动回复话术，并将消息转发到指定群组。账号须已加入目标群。

                </p>

                <label>

                  待转发群组链接

                  <input

                    value={forwardGroupLink}

                    onChange={(e) => setForwardGroupLink(e.target.value)}

                    placeholder="https://t.me/your_group"

                  />

                </label>

                <label>

                  自动回复话术

                  <textarea

                    rows={4}

                    value={replyMessage}

                    onChange={(e) => setReplyMessage(e.target.value)}

                    placeholder="您好，已收到您的消息..."

                  />

                </label>

                <label className="checkbox-row">

                  <input

                    type="checkbox"

                    checked={monitorGroupPosts}

                    onChange={(e) => setMonitorGroupPosts(e.target.checked)}

                  />

                  监控群顶帖（不勾选则监控私信）

                </label>

              </div>

            </>

          ) : (

            <>

              <div className="card">

                <h3>群关键词监控</h3>

                <p className="muted">匹配关键词后私信用户，并转发消息到通知群</p>

                <label>

                  监控关键词（每行一个）

                  <textarea

                    rows={4}

                    value={keywords}

                    onChange={(e) => setKeywords(e.target.value)}

                    placeholder={"优惠\n代理"}

                  />

                </label>

                <label>

                  转发通知群链接

                  <input

                    value={notifyGroupLink}

                    onChange={(e) => setNotifyGroupLink(e.target.value)}

                    placeholder="https://t.me/notify_group"

                  />

                </label>

                <label>

                  匹配后私信内容（留空则仅记录）

                  <textarea

                    rows={3}

                    value={dmOnMatch}

                    onChange={(e) => setDmOnMatch(e.target.value)}

                  />

                </label>

                <label className="checkbox-row">

                  <input

                    type="checkbox"

                    checked={globalMatch}

                    onChange={(e) => setGlobalMatch(e.target.checked)}

                  />

                  全局匹配（不勾选则模糊匹配）

                </label>

              </div>

            </>

          )}



          {mode === "dm_forward" && (

            <div className="card">

              <label>

                文本格式

                <select value={parseMode} onChange={(e) => setParseMode(e.target.value)}>

                  <option value="">纯文本</option>

                  <option value="html">HTML</option>

                  <option value="md">Markdown</option>

                </select>

              </label>

            </div>

          )}



          <div className="button-row">

            <button onClick={handleStart} disabled={loading || isRunning}>

              启动监控

            </button>

            {isRunning && (

              <button className="danger" onClick={stop} disabled={loading}>

                停止监控

              </button>

            )}

          </div>

          {isRunning && <p className="muted">监控持续运行，日志写入 data/日志/监控_日期.txt</p>}

        </div>

      </div>

    </div>

  );

}


