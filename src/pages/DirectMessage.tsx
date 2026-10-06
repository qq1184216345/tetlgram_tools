import { useState } from "react";
import { api } from "../api/client";
import { AccountSelector } from "../components/AccountSelector";
import { MediaUpload } from "../components/MediaUpload";
import { StickyActions } from "../components/StickyActions";
import { useToast } from "../context/ToastContext";
import { usePersistedAccounts } from "../hooks/usePersistedAccounts";
import { parseLines, useTaskRunner } from "../hooks/useTaskRunner";

export function DirectMessagePage() {
  const toast = useToast();
  const [selectedAccounts, setSelectedAccounts] = usePersistedAccounts();
  const [targets, setTargets] = useState("");
  const [message, setMessage] = useState("");
  const [parseMode, setParseMode] = useState("");
  const [intervalMin, setIntervalMin] = useState(60);
  const [intervalMax, setIntervalMax] = useState(120);
  const [useRichTags, setUseRichTags] = useState(false);
  const [usePostbot, setUsePostbot] = useState(false);
  const [postbotCode, setPostbotCode] = useState("");
  const [targetType, setTargetType] = useState<"user" | "group">("user");
  const [sendMode, setSendMode] = useState<"text" | "image" | "file" | "forward" | "sticker" | "contact">("text");
  const [mediaPath, setMediaPath] = useState("");
  const [forwardLinks, setForwardLinks] = useState("");
  const [forwardHideSource, setForwardHideSource] = useState(true);
  const [contactTarget, setContactTarget] = useState("");
  const [contactFirstName, setContactFirstName] = useState("");
  const [contactLastName, setContactLastName] = useState("");
  const [multiLineMode, setMultiLineMode] = useState(false);
  const [randomPrefixLen, setRandomPrefixLen] = useState(0);
  const [randomSuffixLen, setRandomSuffixLen] = useState(0);
  const [threadCount, setThreadCount] = useState(10);
  const [startHour, setStartHour] = useState(0);
  const [endHour, setEndHour] = useState(24);
  const [useDailyWindow, setUseDailyWindow] = useState(false);
  const [useSchedule, setUseSchedule] = useState(false);
  const [scheduleStartAt, setScheduleStartAt] = useState("");
  const [scheduleEndAt, setScheduleEndAt] = useState("");
  const [autoSpambot, setAutoSpambot] = useState(false);
  const [voiceCall, setVoiceCall] = useState(false);
  const [trialMode, setTrialMode] = useState(true);
  const [trialLimit, setTrialLimit] = useState(3);
  const [saveResultFiles, setSaveResultFiles] = useState(true);
  const [resultWithTimestamp, setResultWithTimestamp] = useState(true);
  const { currentTask, loading, isRunning, isPaused, run, stop, pause, resume } =
    useTaskRunner("dm");

  function buildDmPayload(targetList: string[]) {
    return {
      account_ids: selectedAccounts,
      targets: targetList,
      message,
      parse_mode: parseMode || null,
      interval_min: intervalMin,
      interval_max: intervalMax,
      use_rich_tags: useRichTags,
      use_postbot: usePostbot,
      postbot_code: postbotCode,
      target_type: targetType,
      send_mode: sendMode,
      media_path: mediaPath,
      multi_line_mode: multiLineMode,
      random_prefix_len: randomPrefixLen,
      random_suffix_len: randomSuffixLen,
      thread_count: threadCount,
      start_hour: useDailyWindow ? startHour : 0,
      end_hour: useDailyWindow ? endHour : 24,
      schedule_start_at: useSchedule ? scheduleStartAt : "",
      schedule_end_at: useSchedule ? scheduleEndAt : "",
      auto_spambot_unban: autoSpambot,
      forward_channel: "",
      forward_message_id: 0,
      forward_message_links: parseLines(forwardLinks),
      forward_hide_source: forwardHideSource,
      contact_target: contactTarget,
      contact_first_name: contactFirstName,
      contact_last_name: contactLastName,
      voice_call: voiceCall,
      save_result_files: saveResultFiles,
      result_with_timestamp: resultWithTimestamp,
    };
  }

  function resolveTargets(source: string[] = parseLines(targets)): string[] {
    if (!trialMode) return source;
    const limit = Math.max(1, trialLimit);
    return source.slice(0, limit);
  }

  function handleStart() {
    const all = parseLines(targets);
    const list = resolveTargets(all);
    if (trialMode && all.length > list.length) {
      toast.info(`试发模式：仅发送前 ${list.length}/${all.length} 个目标`);
    }
    run(() => api.startDm(buildDmPayload(list)), selectedAccounts, { requireAccounts: true });
  }

  function handleRetryFailed(failedTargets: string[]) {
    const unique = [...new Set(failedTargets.map((t) => t.trim()).filter(Boolean))];
    if (!unique.length) {
      toast.error("没有可重试的失败目标");
      return;
    }
    setTargets(unique.join("\n"));
    const list = resolveTargets(unique);
    if (trialMode && unique.length > list.length) {
      toast.info(`试发模式：重试仅取前 ${list.length} 个`);
    }
    run(() => api.startDm(buildDmPayload(list)), selectedAccounts, { requireAccounts: true });
  }

  async function handleVoiceCallOnce() {
    const lines = parseLines(targets);
    if (!selectedAccounts[0] || !lines[0]) {
      toast.error("请选择账号并填写至少一个目标用户");
      return;
    }
    if (!confirm("语音通话为实验功能，多数情况不会真正接通。仍要发送通话请求吗？")) {
      return;
    }
    try {
      const result = await api.voiceCall(selectedAccounts[0], lines[0]);
      toast.info(result.message);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "发起通话失败");
    }
  }

  return (
    <div className="task-page-layout">
      <div className="task-form">
        <div className="card">
          <h3>选择账号</h3>
          <AccountSelector selected={selectedAccounts} onChange={setSelectedAccounts} />
        </div>

        <div className="card">
          <h3>目标类型</h3>
          <select value={targetType} onChange={(e) => setTargetType(e.target.value as "user" | "group")}>
            <option value="user">用户</option>
            <option value="group">群组</option>
          </select>
        </div>

        <div className="card">
          <h3>{targetType === "user" ? "目标用户" : "目标群组"}</h3>
          <p className="muted">
            {targetType === "user"
              ? "每行一个：手机号（+86138...）或 @用户名。所选账号都会向下列全部目标发送。"
              : "每行一个：群链接或 @群用户名。所选账号都会向下列全部目标发送。"}
          </p>
          <textarea
            rows={6}
            value={targets}
            onChange={(e) => setTargets(e.target.value)}
            placeholder={targetType === "user" ? "+8613800138000\n@username" : "https://t.me/group\n@groupname"}
          />
        </div>

        <div className="card">
          <h3>发送类型</h3>
          <div className="send-mode-row">
            {(["text", "image", "file", "forward", "sticker", "contact"] as const).map((mode) => (
              <button key={mode} className={`mode-btn ${sendMode === mode ? "active" : ""}`}
                onClick={() => setSendMode(mode)} disabled={usePostbot && mode !== "text"}>
                {{ text: "文本", image: "图片", file: "文件", forward: "转发频道", sticker: "贴纸", contact: "名片" }[mode]}
              </button>
            ))}
          </div>
        </div>

        {sendMode === "forward" || sendMode === "sticker" ? (
          <div className="card">
            <h3>{sendMode === "sticker" ? "转发贴纸（频道关联）" : "转发频道消息"}</h3>
            <textarea rows={4} value={forwardLinks} onChange={(e) => setForwardLinks(e.target.value)}
              placeholder={sendMode === "sticker"
                ? "每行一个贴纸消息链接\nhttps://t.me/stickerchannel/123"
                : "每行一个消息链接\nhttps://t.me/channel/123"} />
            <label className="checkbox-row">
              <input type="checkbox" checked={forwardHideSource}
                onChange={(e) => setForwardHideSource(e.target.checked)} />
              隐藏来源
            </label>
          </div>
        ) : sendMode === "contact" ? (
          <div className="card">
            <h3>发送联系人名片</h3>
            <input value={contactTarget} onChange={(e) => setContactTarget(e.target.value)}
              placeholder="@username 或 +手机号" />
            <div className="interval-row">
              <label>显示名<input value={contactFirstName} onChange={(e) => setContactFirstName(e.target.value)} /></label>
              <label>姓氏<input value={contactLastName} onChange={(e) => setContactLastName(e.target.value)} /></label>
            </div>
          </div>
        ) : sendMode === "text" ? (
        <div className="card">
          <h3>私信内容</h3>
          <textarea
            rows={5}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="输入私信内容...\n多版本话术用 *** 分隔"
            disabled={usePostbot}
          />
          <label>
            文本格式
            <select value={parseMode} onChange={(e) => setParseMode(e.target.value)} disabled={usePostbot}>
              <option value="">纯文本</option>
              <option value="html">HTML</option>
              <option value="md">Markdown</option>
            </select>
          </label>
          <label className="checkbox-row">
            <input type="checkbox" checked={useRichTags} onChange={(e) => setUseRichTags(e.target.checked)} disabled={usePostbot} />
            彩虹富文本标签
          </label>
          <label className="checkbox-row">
            <input type="checkbox" checked={usePostbot} onChange={(e) => {
              const on = e.target.checked;
              setUsePostbot(on);
              if (on) {
                setSendMode("text");
                setUseRichTags(false);
              }
            }} />
            PostBot 模式
          </label>
          {usePostbot && (
            <>
              <p className="tip-banner">
                已启用 PostBot：上方文案、富文本、图片/文件/转发/贴纸/名片均不生效，只会发送 PostBot 代码。
                请在 @postbot 生成代码后粘贴到下方。
              </p>
              <label>
                PostBot 代码
                <input value={postbotCode} onChange={(e) => setPostbotCode(e.target.value)}
                  placeholder="粘贴 @postbot 生成的代码" />
              </label>
            </>
          )}
        </div>
        ) : (
        <div className="card">
          <h3>{sendMode === "image" ? "图片" : "文件"}</h3>
          <MediaUpload
            accept={sendMode === "image" ? "image/*" : undefined}
            onUploaded={(path) => setMediaPath(path)}
          />
          <label>
            说明文字（可选）
            <textarea rows={3} value={message} onChange={(e) => setMessage(e.target.value)} />
          </label>
        </div>
        )}

        <div className="card">
          <h3>高级选项</h3>
          <label className="checkbox-row">
            <input type="checkbox" checked={multiLineMode} onChange={(e) => setMultiLineMode(e.target.checked)} />
            多行模式（*** 分隔整段话术，随机选一段）
          </label>
          <label className="checkbox-row">
            <input type="checkbox" checked={saveResultFiles} onChange={(e) => setSaveResultFiles(e.target.checked)} />
            写入成功/失败文件（data/日志/私信成功.txt、私信失败.txt）
          </label>
          <label className="checkbox-row">
            <input type="checkbox" checked={resultWithTimestamp}
              onChange={(e) => setResultWithTimestamp(e.target.checked)} disabled={!saveResultFiles} />
            结果文件附带时间戳（格式：2026年8月30日20时21分45秒:@用户）
          </label>
          <div className="interval-row">
            <label>
              消息前随机字符
              <input type="number" value={randomPrefixLen} min={0} max={20}
                onChange={(e) => setRandomPrefixLen(Number(e.target.value))} />
            </label>
            <label>
              消息后随机字符
              <input type="number" value={randomSuffixLen} min={0} max={20}
                onChange={(e) => setRandomSuffixLen(Number(e.target.value))} />
            </label>
            <label>
              线程数
              <input type="number" value={threadCount} min={1} max={10}
                onChange={(e) => setThreadCount(Number(e.target.value))} />
            </label>
          </div>
        </div>

        <div className="card">
          <h3>发送间隔与定时</h3>
          <p className="tip-banner">
            勾选的每个账号都会向全部目标各发一遍（非分流）。间隔按账号独立计算，多号互不排队。防封建议：默认 60–120 秒。新号先开「试发模式」测额度；可设定时开始/结束与每日时段。
          </p>
          <div className="interval-row">
            <label>最小<input type="number" value={intervalMin}
              onChange={(e) => setIntervalMin(Number(e.target.value))} min={1} /></label>
            <label>最大<input type="number" value={intervalMax}
              onChange={(e) => setIntervalMax(Number(e.target.value))} min={1} /></label>
          </div>
          <label className="checkbox-row" style={{ marginTop: 10 }}>
            <input type="checkbox" checked={useSchedule}
              onChange={(e) => setUseSchedule(e.target.checked)} />
            定时开始 / 结束（具体日期时间）
          </label>
          {useSchedule && (
            <div className="interval-row" style={{ marginTop: 8 }}>
              <label>
                开始时间
                <input type="datetime-local" value={scheduleStartAt}
                  onChange={(e) => setScheduleStartAt(e.target.value)} />
              </label>
              <label>
                结束时间（可选）
                <input type="datetime-local" value={scheduleEndAt}
                  onChange={(e) => setScheduleEndAt(e.target.value)} />
              </label>
            </div>
          )}
          <label className="checkbox-row" style={{ marginTop: 10 }}>
            <input type="checkbox" checked={useDailyWindow}
              onChange={(e) => {
                const on = e.target.checked;
                setUseDailyWindow(on);
                if (on && startHour === 0 && endHour === 24) {
                  setStartHour(9);
                  setEndHour(22);
                }
              }} />
            每日发送时段
          </label>
          {useDailyWindow && (
            <div className="interval-row" style={{ marginTop: 8 }}>
              <label>开始(时)<input type="number" value={startHour} min={0} max={23}
                onChange={(e) => setStartHour(Number(e.target.value))} /></label>
              <label>结束(时)<input type="number" value={endHour} min={0} max={24}
                onChange={(e) => setEndHour(Number(e.target.value))} /></label>
            </div>
          )}
          <label className="checkbox-row" style={{ marginTop: 8 }}>
            <input type="checkbox" checked={trialMode} onChange={(e) => setTrialMode(e.target.checked)} />
            试发模式（只发列表前 N 个，测号额度）
          </label>
          {trialMode && (
            <label>
              试发条数
              <input
                type="number"
                value={trialLimit}
                min={1}
                max={50}
                onChange={(e) => setTrialLimit(Math.max(1, Number(e.target.value) || 1))}
              />
            </label>
          )}
          <label className="checkbox-row" style={{ marginTop: 8 }}>
            <input type="checkbox" checked={autoSpambot} onChange={(e) => setAutoSpambot(e.target.checked)} />
            频繁限制时自动向 SpamBot 申请解封
          </label>
          <details style={{ marginTop: 10 }}>
            <summary className="muted" style={{ cursor: "pointer" }}>实验功能（语音通话）</summary>
            <p className="tip-banner" style={{ marginTop: 8 }}>
              仅能发送通话信令，多数情况不会真正响铃接通。需要可靠通话请用官方 Telegram 客户端。
            </p>
            <label className="checkbox-row">
              <input type="checkbox" checked={voiceCall} onChange={(e) => setVoiceCall(e.target.checked)} />
              私信任务改为发起语音通话（替代发消息）
            </label>
          </details>
        </div>

        <StickyActions summary={<>已选 {selectedAccounts.length} 个账号{trialMode ? " · 试发模式开" : ""}</>}>
          <button onClick={handleStart} disabled={loading || isRunning}>
            开始私信
          </button>
          <button
            className="secondary"
            onClick={handleVoiceCallOnce}
            disabled={loading || isRunning}
            title="实验功能：仅发送通话请求"
          >
            实验：单次语音请求
          </button>
          {!!currentTask?.failed_items?.length && !isRunning && (
            <button
              className="secondary"
              disabled={loading}
              onClick={() =>
                handleRetryFailed(
                  (currentTask.failed_items ?? []).map((i) => i.target).filter(Boolean),
                )
              }
            >
              重试失败目标
            </button>
          )}
          {isRunning && !isPaused && (
            <button className="secondary" onClick={pause} disabled={loading}>暂停</button>
          )}
          {isPaused && (
            <button className="secondary" onClick={resume} disabled={loading}>继续</button>
          )}
          {isRunning && (
            <button className="danger" onClick={stop} disabled={loading}>停止任务</button>
          )}
        </StickyActions>
      </div>
    </div>
  );
}
