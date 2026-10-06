import { useState } from "react";
import { api } from "../api/client";
import { AccountSelector } from "../components/AccountSelector";
import { StickyActions } from "../components/StickyActions";
import { usePersistedAccounts } from "../hooks/usePersistedAccounts";
import { parseLines, useTaskRunner } from "../hooks/useTaskRunner";

export function WarmGroupPage() {
  const [selectedAccounts, setSelectedAccounts] = usePersistedAccounts();
  const [groupLink, setGroupLink] = useState("");
  const [groupLinks, setGroupLinks] = useState("");
  const [messages, setMessages] = useState("");
  const [rounds, setRounds] = useState(1);
  const [joinOnly, setJoinOnly] = useState(false);
  const [intervalMin, setIntervalMin] = useState(30);
  const [intervalMax, setIntervalMax] = useState(90);
  const { loading, isRunning, run, stop } = useTaskRunner("warm_group");

  function handleStart() {
    const links = parseLines(groupLinks);
    run(() =>
      api.startWarmGroup({
        account_ids: selectedAccounts,
        group_links: links,
        group_link: groupLink.trim() || undefined,
        messages: parseLines(messages),
        interval_min: intervalMin,
        interval_max: intervalMax,
        rounds,
        join_only: joinOnly,
      }),
      selectedAccounts,
      { requireAccounts: true },
    );
  }

  return (
    <div className="task-page-layout">
      <div className="task-form">
        <div className="card">
          <h3>选择账号</h3>
          <AccountSelector selected={selectedAccounts} onChange={setSelectedAccounts} />
          <p className="muted">多账号轮流在群内发送消息，模拟互动</p>
        </div>

        <div className="card">
          <h3>目标群组（单个，可选）</h3>
          <input
            value={groupLink}
            onChange={(e) => setGroupLink(e.target.value)}
            placeholder="https://t.me/yourgroup 或 @groupname"
          />
        </div>

        <div className="card">
          <h3>目标群组（多个）</h3>
          <p className="muted">每行一个群链接，优先于上方单个群组</p>
          <textarea
            rows={4}
            value={groupLinks}
            onChange={(e) => setGroupLinks(e.target.value)}
            placeholder={"https://t.me/group1\n@group2"}
          />
        </div>

        <div className="card">
          <h3>话术库</h3>
          <p className="muted">每行一条话术，随机按账号轮流发送</p>
          <textarea
            rows={6}
            value={messages}
            onChange={(e) => setMessages(e.target.value)}
            placeholder={"大家好！\n确实不错\n学到了"}
            disabled={joinOnly}
          />
        </div>

        <div className="card">
          <h3>运行参数</h3>
          <label className="checkbox-row">
            <input type="checkbox" checked={joinOnly}
              onChange={(e) => setJoinOnly(e.target.checked)} />
            仅加群（不发送消息）
          </label>
          <div className="form-stack">
            <label>
              循环轮数
              <input
                type="number"
                value={rounds}
                onChange={(e) => setRounds(Number(e.target.value))}
                min={1}
              />
            </label>
            <div className="interval-row">
              <label>
                单账号间隔最小（秒）
                <input
                  type="number"
                  value={intervalMin}
                  onChange={(e) => setIntervalMin(Number(e.target.value))}
                  min={1}
                />
              </label>
              <label>
                间隔最大（秒）
                <input
                  type="number"
                  value={intervalMax}
                  onChange={(e) => setIntervalMax(Number(e.target.value))}
                  min={1}
                />
              </label>
            </div>
          </div>
        </div>

        <StickyActions summary={<>已选 {selectedAccounts.length} 个账号</>}>
          <button onClick={handleStart} disabled={loading || isRunning}>
            开始炒群
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
