import { useState } from "react";
import { api } from "../api/client";
import { AccountSelector } from "../components/AccountSelector";
import { usePersistedAccounts } from "../hooks/usePersistedAccounts";
import { parseLines, useTaskRunner } from "../hooks/useTaskRunner";



type Tab = "members" | "groups";



const BOT_OPTIONS = ["soso", "hao123", "jiso", "kuai", "smss", "damo"];



export function ScrapePage() {

  const [tab, setTab] = useState<Tab>("members");

  const [selectedAccounts, setSelectedAccounts] = usePersistedAccounts();

  const [groupLinks, setGroupLinks] = useState("");

  const [keywords, setKeywords] = useState("");

  const [botUsername, setBotUsername] = useState("soso");

  const [activeDays, setActiveDays] = useState(0);

  const [requireName, setRequireName] = useState(false);

  const [hiddenGroupMode, setHiddenGroupMode] = useState(false);

  const [messageLimit, setMessageLimit] = useState(2000);

  const [minMembers, setMinMembers] = useState(0);

  const [filterChannels, setFilterChannels] = useState(true);

  const [savePath, setSavePath] = useState("");
  const [groupThreadCount, setGroupThreadCount] = useState(0);

  const { loading, isRunning, run, stop } = useTaskRunner(
    "scrape_members",
    "scrape_groups",
  );



  function handleStart() {

    if (tab === "members") {

      run(() =>

        api.startScrapeMembers({

          account_ids: selectedAccounts,

          group_links: parseLines(groupLinks),

          active_days: activeDays,

          require_name: requireName,

          hidden_group_mode: hiddenGroupMode,

          message_limit: Math.min(50000, Math.max(1, messageLimit || 2000)),

          save_path: savePath,

        }),

        selectedAccounts,

        { requireAccounts: true },

      );

    } else {

      run(() =>

        api.startScrapeGroups({

          account_ids: selectedAccounts,

          keywords: parseLines(keywords),

          bot_username: botUsername,

          min_members: minMembers,

          filter_channels: filterChannels,

          save_path: savePath,

          thread_count: groupThreadCount,

        }),

        selectedAccounts,

        { requireAccounts: true },

      );

    }

  }



  return (

    <div className="broadcast-page">

      <div className="tab-bar">

        <button className={tab === "members" ? "active" : ""} onClick={() => setTab("members")}>

          群成员采集

        </button>

        <button className={tab === "groups" ? "active" : ""} onClick={() => setTab("groups")}>

          关键词搜群

        </button>

      </div>



      <div className="task-page-layout">

        <div className="task-form">

          <div className="card">

            <h3>选择账号</h3>

            <AccountSelector selected={selectedAccounts} onChange={setSelectedAccounts} />

          </div>



          {tab === "members" ? (

            <>

              <div className="card">

                <h3>目标群组</h3>

                <p className="muted">每行一个群组链接</p>

                <textarea

                  rows={6}

                  value={groupLinks}

                  onChange={(e) => setGroupLinks(e.target.value)}

                  placeholder={"https://t.me/example\n@groupname"}

                />

              </div>

              <div className="card">

                <h3>筛选选项</h3>

                <label>

                  近期活跃天数（0=不筛选）

                  <input

                    type="number"

                    value={activeDays}

                    min={0}

                    max={30}

                    onChange={(e) => setActiveDays(Number(e.target.value))}

                  />

                </label>

                <label className="checkbox-row">

                  <input

                    type="checkbox"

                    checked={requireName}

                    onChange={(e) => setRequireName(e.target.checked)}

                  />

                  需要姓氏/名字

                </label>

                <label>

                  采集方式

                  <select

                    value={hiddenGroupMode ? "speakers" : "members"}

                    onChange={(e) => setHiddenGroupMode(e.target.value === "speakers")}

                  >

                    <option value="members">群成员列表</option>

                    <option value="speakers">最新发言用户</option>

                  </select>

                </label>

                {hiddenGroupMode && (

                  <label>

                    提取最新发言条数

                    <input

                      type="number"

                      value={messageLimit}

                      min={1}

                      max={50000}

                      onChange={(e) => setMessageLimit(Math.max(1, Number(e.target.value) || 1))}

                    />

                  </label>

                )}

                {hiddenGroupMode && (

                  <p className="muted">只提取最近 {messageLimit || 0} 条消息里发过言的用户，适合隐藏成员的群。</p>

                )}

              </div>

            </>

          ) : (

            <>

              <div className="card">

                <h3>搜索关键词</h3>

                <textarea

                  rows={5}

                  value={keywords}

                  onChange={(e) => setKeywords(e.target.value)}

                  placeholder={"加密货币\n副业赚钱"}

                />

                <label>
                  并行线程数（0=与关键词数相同）
                  <input
                    type="number"
                    min={0}
                    max={20}
                    value={groupThreadCount}
                    onChange={(e) => setGroupThreadCount(Number(e.target.value))}
                  />
                </label>

              </div>

              <div className="card">

                <h3>搜索机器人</h3>

                <select value={botUsername} onChange={(e) => setBotUsername(e.target.value)}>

                  {BOT_OPTIONS.map((bot) => (

                    <option key={bot} value={bot}>

                      {bot}

                    </option>

                  ))}

                </select>

                <input

                  style={{ marginTop: 8 }}

                  value={botUsername}

                  onChange={(e) => setBotUsername(e.target.value)}

                  placeholder="或手动输入机器人用户名"

                />

              </div>

              <div className="card">

                <h3>筛选选项</h3>

                <label>

                  群人数大于

                  <input

                    type="number"

                    value={minMembers}

                    min={0}

                    onChange={(e) => setMinMembers(Number(e.target.value))}

                  />

                </label>

                <label className="checkbox-row">

                  <input

                    type="checkbox"

                    checked={filterChannels}

                    onChange={(e) => setFilterChannels(e.target.checked)}

                  />

                  过滤频道（只保留群组）

                </label>

              </div>

            </>

          )}



          <div className="card">

            <h3>保存路径</h3>

            <input

              value={savePath}

              onChange={(e) => setSavePath(e.target.value)}

              placeholder="留空则保存到 data/采集/"

            />

          </div>



          <div className="button-row">

            <button onClick={handleStart} disabled={loading || isRunning}>

              {tab === "members" ? "开始采集成员" : "开始搜索群组"}

            </button>

            {isRunning && (

              <button className="danger" onClick={stop} disabled={loading}>

                停止任务

              </button>

            )}

          </div>

        </div>

      </div>

    </div>

  );

}


