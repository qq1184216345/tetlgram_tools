import { useRef, useState } from "react";
import { api } from "../api/client";
import { AccountSelector } from "../components/AccountSelector";
import { CollapsibleCard } from "../components/CollapsibleCard";
import { MediaUpload } from "../components/MediaUpload";
import { StickyActions } from "../components/StickyActions";
import { useToast } from "../context/ToastContext";
import { usePersistedAccounts } from "../hooks/usePersistedAccounts";
import { useTaskRunner } from "../hooks/useTaskRunner";

type Tab = "broadcast" | "join";
type SendMode = "text" | "image" | "file" | "forward" | "contact" | "sticker";

function parseTargets(text: string): string[] {
  return text.split("\n").map((l) => l.trim()).filter(Boolean);
}

export function BroadcastPage() {
  const [tab, setTab] = useState<Tab>("broadcast");
  const [selectedAccounts, setSelectedAccounts] = usePersistedAccounts();
  const [targets, setTargets] = useState("");
  const [useJoinedGroups, setUseJoinedGroups] = useState(true);
  const [message, setMessage] = useState("");
  const [parseMode, setParseMode] = useState("");
  const [intervalMin, setIntervalMin] = useState(60);
  const [intervalMax, setIntervalMax] = useState(120);
  const [useRichTags, setUseRichTags] = useState(false);
  const [usePostbot, setUsePostbot] = useState(false);
  const [postbotCode, setPostbotCode] = useState("");
  const [sendMode, setSendMode] = useState<SendMode>("text");
  const [mediaPath, setMediaPath] = useState("");
  const [forwardChannel, setForwardChannel] = useState("");
  const [forwardMessageId, setForwardMessageId] = useState(0);
  const [forwardHideSource, setForwardHideSource] = useState(true);
  const [forwardLinks, setForwardLinks] = useState("");
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
  const [randomOrder, setRandomOrder] = useState(false);
  const [roundRestMin, setRoundRestMin] = useState(0);
  const [roundRestMax, setRoundRestMax] = useState(0);
  const [exitMutedGroups, setExitMutedGroups] = useState(false);
  const [combinedSend, setCombinedSend] = useState(false);
  const [autoDeleteAfter, setAutoDeleteAfter] = useState(0);
  const [removeMutedAccounts, setRemoveMutedAccounts] = useState(false);
  const [guestMode, setGuestMode] = useState(false);
  const [requestJoin, setRequestJoin] = useState(false);
  const [joinNoDuplicate, setJoinNoDuplicate] = useState(true);
  const [autoPassVerify, setAutoPassVerify] = useState(true);
  const [templateMsg, setTemplateMsg] = useState("");
  const linksFileRef = useRef<HTMLInputElement>(null);
  const { loading, isRunning, isPaused, run, stop, pause } = useTaskRunner(
    "broadcast",
    "join_group",
    "leave_groups",
  );
  const toast = useToast();

  function handleStart() {
    const targetList = parseTargets(targets);
    const effectiveStartHour = useDailyWindow ? startHour : 0;
    const effectiveEndHour = useDailyWindow ? endHour : 24;
    const effectiveScheduleStart = useSchedule ? scheduleStartAt : "";
    const effectiveScheduleEnd = useSchedule ? scheduleEndAt : "";
    if (tab === "broadcast") {
      if (!useJoinedGroups && targetList.length === 0) {
        toast.error("请填写指定群组链接");
        return;
      }
      if (sendMode === "text" && !usePostbot && !message.trim()) {
        toast.error("请填写要发送的内容");
        return;
      }
      if ((sendMode === "image" || sendMode === "file") && !mediaPath) {
        toast.error("请先上传文件");
        return;
      }
      if (usePostbot && !postbotCode.trim()) {
        toast.error("请粘贴 PostBot 代码");
        return;
      }
      run(() =>
        api.startBroadcast({
          account_ids: selectedAccounts,
          targets: useJoinedGroups ? [] : targetList,
          use_joined_groups: useJoinedGroups,
          message,
          parse_mode: parseMode || null,
          interval_min: intervalMin,
          interval_max: intervalMax,
          auto_join: false,
          use_rich_tags: useRichTags,
          use_postbot: usePostbot,
          postbot_code: postbotCode,
          send_mode: sendMode,
          media_path: mediaPath,
          forward_channel: forwardChannel,
          forward_message_id: forwardMessageId,
          forward_message_links: parseTargets(forwardLinks),
          forward_hide_source: forwardHideSource,
          multi_line_mode: multiLineMode,
          random_prefix_len: randomPrefixLen,
          random_suffix_len: randomSuffixLen,
          thread_count: threadCount,
          start_hour: effectiveStartHour,
          end_hour: effectiveEndHour,
          schedule_start_at: effectiveScheduleStart,
          schedule_end_at: effectiveScheduleEnd,
          auto_spambot_unban: autoSpambot,
          no_duplicate_join: false,
          random_order: randomOrder,
          round_rest_min: roundRestMin,
          round_rest_max: roundRestMax,
          exit_muted_groups: exitMutedGroups,
          combined_send: combinedSend,
          contact_target: contactTarget,
          contact_first_name: contactFirstName,
          contact_last_name: contactLastName,
          auto_delete_after_sec: autoDeleteAfter,
          remove_muted_accounts: removeMutedAccounts,
          guest_mode: guestMode,
        }),
        selectedAccounts,
        { requireAccounts: true },
      );
    } else {
      if (targetList.length === 0) {
        toast.error("请填写要加入的群组链接");
        return;
      }
      run(() =>
        api.startJoinGroup({
          account_ids: selectedAccounts,
          targets: targetList,
          interval_min: intervalMin,
          interval_max: intervalMax,
          start_hour: effectiveStartHour,
          end_hour: effectiveEndHour,
          schedule_start_at: effectiveScheduleStart,
          schedule_end_at: effectiveScheduleEnd,
          no_duplicate_join: joinNoDuplicate,
          request_join: requestJoin,
          auto_pass_verify: autoPassVerify,
          thread_count: threadCount,
        }),
        selectedAccounts,
        { requireAccounts: true },
      );
    }
  }

  function handleImportLinks(files: FileList | null) {
    if (!files?.[0]) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = (e.target?.result as string) ?? "";
      setTargets(text);
    };
    reader.readAsText(files[0]);
    if (linksFileRef.current) linksFileRef.current.value = "";
  }

  function handleLeaveAllGroups() {
    if (selectedAccounts.length === 0) return;
    if (!confirm("确定让所选账号退出所有群组？")) return;
    run(() => api.startLeaveGroups({ account_ids: selectedAccounts }), selectedAccounts);
  }

  function handleLeaveSpecificGroups() {
    if (selectedAccounts.length === 0) return;
    const list = parseTargets(targets);
    if (list.length === 0) return;
    if (!confirm(`确定退出列表中的 ${list.length} 个指定群/频道？`)) return;
    run(() =>
      api.startLeaveGroups({
        account_ids: selectedAccounts,
        targets: list,
        include_channels: true,
      }),
      selectedAccounts,
    );
  }

  async function handleLoadTemplate() {
    try {
      const templates = await api.getMessageTemplates();
      setMessage(templates.broadcast);
      setTemplateMsg("模板已加载");
    } catch (e) {
      setTemplateMsg(e instanceof Error ? e.message : "加载失败");
    }
  }

  async function handleSaveTemplate() {
    try {
      const existing = await api.getMessageTemplates();
      await api.saveMessageTemplates({ ...existing, broadcast: message });
      setTemplateMsg("模板已保存");
    } catch (e) {
      setTemplateMsg(e instanceof Error ? e.message : "保存失败");
    }
  }

  return (
    <div className="broadcast-page">
      <div className="tab-bar">
        <button className={tab === "broadcast" ? "active" : ""} onClick={() => setTab("broadcast")}>
          群发消息
        </button>
        <button className={tab === "join" ? "active" : ""} onClick={() => setTab("join")}>
          自动加群
        </button>
      </div>

      <div className="broadcast-layout">
        <div className="broadcast-form">
          <div className="card">
            <h3>选择账号</h3>
            <AccountSelector selected={selectedAccounts} onChange={setSelectedAccounts} />
          </div>

          <div className="card">
            <h3>目标群组</h3>
            {tab === "broadcast" ? (
              <>
                <label className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={useJoinedGroups}
                    onChange={(e) => setUseJoinedGroups(e.target.checked)}
                  />
                  发送所选账号已加入的全部群组
                </label>
                {useJoinedGroups ? (
                  <p className="muted" style={{ marginTop: 8, marginBottom: 8 }}>
                    每个账号各自向自己已加入的群发送，无需填写链接。取消勾选后可指定群组。
                  </p>
                ) : (
                  <>
                    <p className="muted">每行一个群链接或 @群名。所选账号都会向下列全部目标发送。</p>
                    <textarea rows={6} value={targets} onChange={(e) => setTargets(e.target.value)}
                      placeholder={"https://t.me/example\n@groupname"} />
                  </>
                )}
              </>
            ) : (
              <>
                <p className="muted">
                  {joinNoDuplicate
                    ? "每行一个群链接或 @群名。勾选「加群不重复」后，同一个群在已选账号里只需有一人加入。"
                    : "每行一个群链接或 @群名。所选账号都会加入下列全部目标。"}
                </p>
                <textarea rows={6} value={targets} onChange={(e) => setTargets(e.target.value)}
                  placeholder={"https://t.me/example\n@groupname"} />
              </>
            )}
            <div className="button-row" style={{ marginTop: 8 }}>
              {(tab === "join" || !useJoinedGroups) && (
                <button className="secondary" onClick={() => linksFileRef.current?.click()}>
                  导入链接文件
                </button>
              )}
              <input
                ref={linksFileRef}
                type="file"
                accept=".txt,.csv"
                hidden
                onChange={(e) => handleImportLinks(e.target.files)}
              />
            </div>
          </div>

          {tab === "broadcast" && (
            <>
              <div className="card">
                <h3>发送类型</h3>
                <div className="send-mode-row">
                  {(["text", "image", "file", "forward", "sticker", "contact"] as SendMode[]).map((mode) => (
                    <button
                      key={mode}
                      className={`mode-btn ${sendMode === mode ? "active" : ""}`}
                      onClick={() => setSendMode(mode)}
                      disabled={usePostbot && mode !== "text"}
                    >
                      {{ text: "文本", image: "图片", file: "文件", forward: "转发频道", sticker: "贴纸", contact: "名片" }[mode]}
                    </button>
                  ))}
                </div>
              </div>

              {sendMode === "forward" || sendMode === "sticker" ? (
                <div className="card">
                  <h3>{sendMode === "sticker" ? "转发贴纸（频道关联）" : "转发频道消息"}</h3>
                  <p className="muted">
                    {sendMode === "sticker"
                      ? "填写频道中贴纸消息的链接，每行一个，发送时随机选一条转发"
                      : "可填多条消息链接，每行一个，发送时随机选一条"}
                  </p>
                  <label>
                    频道消息链接（每行一个）
                    <textarea
                      rows={4}
                      value={forwardLinks}
                      onChange={(e) => setForwardLinks(e.target.value)}
                      placeholder={"https://t.me/channelname/123\nhttps://t.me/channelname/456"}
                    />
                  </label>
                  <label>
                    或单条：频道消息链接
                    <input
                      value={forwardChannel}
                      onChange={(e) => setForwardChannel(e.target.value)}
                      placeholder="https://t.me/channelname/123"
                    />
                  </label>
                  <label>
                    或：频道 + 消息 ID
                    <div className="interval-row">
                      <input placeholder="@channel 或 t.me/channel" value={forwardChannel}
                        onChange={(e) => setForwardChannel(e.target.value)} />
                      <input type="number" placeholder="消息ID" value={forwardMessageId || ""}
                        onChange={(e) => setForwardMessageId(Number(e.target.value))} />
                    </div>
                  </label>
                  <label className="checkbox-row">
                    <input type="checkbox" checked={forwardHideSource}
                      onChange={(e) => setForwardHideSource(e.target.checked)} />
                    隐藏来源（不显示转发自频道）
                  </label>
                </div>
              ) : sendMode === "contact" ? (
                <div className="card">
                  <h3>发送联系人名片</h3>
                  <label>
                    联系人（@用户名 或 +手机号）
                    <input
                      value={contactTarget}
                      onChange={(e) => setContactTarget(e.target.value)}
                      placeholder="@username 或 +8613800138000"
                    />
                  </label>
                  <div className="interval-row">
                    <label>
                      显示名（可选）
                      <input value={contactFirstName} onChange={(e) => setContactFirstName(e.target.value)} />
                    </label>
                    <label>
                      姓氏（可选）
                      <input value={contactLastName} onChange={(e) => setContactLastName(e.target.value)} />
                    </label>
                  </div>
                </div>
              ) : sendMode === "text" ? (
                <div className="card">
                  <h3>消息内容</h3>
                  <textarea rows={5} value={message} onChange={(e) => setMessage(e.target.value)}
                    placeholder={"输入要群发的消息内容...\n多版本话术用 *** 分隔"}
                    disabled={usePostbot} />
                  <div className="button-row" style={{ marginTop: 8 }}>
                    <button className="secondary" onClick={handleLoadTemplate} disabled={usePostbot}>加载模板</button>
                    <button className="secondary" onClick={handleSaveTemplate} disabled={usePostbot}>保存模板</button>
                    {templateMsg && <span className="muted">{templateMsg}</span>}
                  </div>
                  <label>
                    文本格式
                    <select value={parseMode} onChange={(e) => setParseMode(e.target.value)} disabled={usePostbot}>
                      <option value="">纯文本</option>
                      <option value="html">HTML</option>
                      <option value="md">Markdown</option>
                    </select>
                  </label>
                  <label className="checkbox-row">
                    <input type="checkbox" checked={useRichTags}
                      onChange={(e) => setUseRichTags(e.target.checked)} disabled={usePostbot} />
                    彩虹富文本标签
                  </label>
                  <label className="checkbox-row">
                    <input type="checkbox" checked={usePostbot}
                      onChange={(e) => {
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
                    label={`上传${sendMode === "image" ? "图片" : "文件"}`}
                    onUploaded={(path) => setMediaPath(path)}
                  />
                  <label>
                    说明文字（可选）
                    <textarea rows={3} value={message} onChange={(e) => setMessage(e.target.value)} />
                  </label>
                </div>
              )}
            </>
          )}

          {tab === "join" && (
            <div className="card">
              <h3>加群选项</h3>
              <label className="checkbox-row">
                <input type="checkbox" checked={joinNoDuplicate}
                  onChange={(e) => setJoinNoDuplicate(e.target.checked)} />
                加群不重复（勾选账号中已有一人在群内，其他账号不再加）
              </label>
              <label className="checkbox-row">
                <input type="checkbox" checked={requestJoin}
                  onChange={(e) => setRequestJoin(e.target.checked)} />
                申请加入（需管理员批准）
              </label>
              <label className="checkbox-row">
                <input type="checkbox" checked={autoPassVerify}
                  onChange={(e) => setAutoPassVerify(e.target.checked)} />
                智能过加群验证（算数/按钮）
              </label>
              <label>
                线程数
                <input type="number" value={threadCount} min={1} max={10}
                  onChange={(e) => setThreadCount(Math.max(1, Number(e.target.value)))} />
              </label>
            </div>
          )}

          <CollapsibleCard title="高级选项">
            {tab === "broadcast" && (
              <>
                <label className="checkbox-row">
                  <input type="checkbox" checked={randomOrder}
                    onChange={(e) => setRandomOrder(e.target.checked)} />
                  随机发送顺序
                </label>
                <label className="checkbox-row">
                  <input type="checkbox" checked={exitMutedGroups}
                    onChange={(e) => setExitMutedGroups(e.target.checked)} />
                  退出禁言群
                </label>
                <label className="checkbox-row">
                  <input type="checkbox" checked={removeMutedAccounts}
                    onChange={(e) => setRemoveMutedAccounts(e.target.checked)} />
                  删除群发禁言账号
                </label>
                <label className="checkbox-row">
                  <input type="checkbox" checked={guestMode}
                    onChange={(e) => setGuestMode(e.target.checked)} />
                  访客模式（不进群直接发）
                </label>
                <label className="checkbox-row">
                  <input type="checkbox" checked={combinedSend}
                    onChange={(e) => setCombinedSend(e.target.checked)} />
                  合并发送模式
                </label>
                <label className="checkbox-row">
                  <input type="checkbox" checked={autoDeleteAfter > 0}
                    onChange={(e) => setAutoDeleteAfter(e.target.checked ? 5 : 0)} />
                  发送后撤回（假消息）
                </label>
                {autoDeleteAfter > 0 && (
                  <label>
                    撤回延迟（秒）
                    <input type="number" value={autoDeleteAfter} min={1} max={300}
                      onChange={(e) => setAutoDeleteAfter(Math.max(1, Number(e.target.value)))} />
                  </label>
                )}
                <div className="interval-row">
                  <label>
                    轮次休息最小（秒）
                    <input type="number" value={roundRestMin} min={0}
                      onChange={(e) => setRoundRestMin(Number(e.target.value))} />
                  </label>
                  <label>
                    轮次休息最大（秒）
                    <input type="number" value={roundRestMax} min={0}
                      onChange={(e) => setRoundRestMax(Number(e.target.value))} />
                  </label>
                </div>
              </>
            )}
            {tab === "broadcast" && (
              <label className="checkbox-row">
                <input type="checkbox" checked={multiLineMode} onChange={(e) => setMultiLineMode(e.target.checked)} />
                多行模式（*** 分隔整段话术，随机选一段）
              </label>
            )}
            {tab === "broadcast" && (
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
            )}
          </CollapsibleCard>

          <div className="card">
            <h3>发送间隔与定时</h3>
            <p className="tip-banner">
              {tab === "broadcast" && useJoinedGroups
                ? "每个账号向自己已加入的群发送。勾选几个号就几个号同时发，第一条立刻出去。"
                : "勾选的每个账号都会向全部目标各做一遍。多号同时开工，第一条立刻执行。"}
              间隔只在首次成功之后生效。
            </p>
            <div className="interval-row">
              <label>最小间隔(秒)<input type="number" value={intervalMin}
                onChange={(e) => setIntervalMin(Number(e.target.value))} min={1} /></label>
              <label>最大间隔(秒)<input type="number" value={intervalMax}
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
                  <input
                    type="datetime-local"
                    value={scheduleStartAt}
                    onChange={(e) => setScheduleStartAt(e.target.value)}
                  />
                </label>
                <label>
                  结束时间（可选）
                  <input
                    type="datetime-local"
                    value={scheduleEndAt}
                    onChange={(e) => setScheduleEndAt(e.target.value)}
                  />
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
              每日发送时段（可跨夜，如 22–06）
            </label>
            {useDailyWindow && (
              <div className="interval-row" style={{ marginTop: 8 }}>
                <label>
                  开始(时)
                  <input type="number" value={startHour} min={0} max={23}
                    onChange={(e) => setStartHour(Number(e.target.value))} />
                </label>
                <label>
                  结束(时)
                  <input type="number" value={endHour} min={0} max={24}
                    onChange={(e) => setEndHour(Number(e.target.value))} />
                </label>
              </div>
            )}
            {(useSchedule || useDailyWindow) && (
              <p className="muted" style={{ marginTop: 8 }}>
                {useSchedule && scheduleStartAt
                  ? `将等待至 ${scheduleStartAt.replace("T", " ")} 再发`
                  : ""}
                {useSchedule && scheduleEndAt
                  ? `；超过 ${scheduleEndAt.replace("T", " ")} 自动停止`
                  : ""}
                {useDailyWindow
                  ? `；每日仅在 ${String(startHour).padStart(2, "0")}:00–${String(endHour).padStart(2, "0")}:00 发送`
                  : ""}
              </p>
            )}
            {tab === "broadcast" && (
              <label className="checkbox-row" style={{ marginTop: 8 }}>
                <input type="checkbox" checked={autoSpambot} onChange={(e) => setAutoSpambot(e.target.checked)} />
                禁言时自动向 SpamBot 申请解封
              </label>
            )}
          </div>

          <CollapsibleCard title="危险操作：退群" danger>
            <p className="muted">会让已选账号退出群组，请确认后再点。</p>
            <div className="button-row">
              <button className="danger" onClick={handleLeaveAllGroups}
                disabled={loading || isRunning || selectedAccounts.length === 0}>
                退出所有群
              </button>
              {(tab === "join" || !useJoinedGroups) && (
                <button className="danger" onClick={handleLeaveSpecificGroups}
                  disabled={loading || isRunning || selectedAccounts.length === 0}>
                  退出指定群/频道
                </button>
              )}
            </div>
          </CollapsibleCard>

          <StickyActions
            summary={
              <>
                已选 {selectedAccounts.length} 个账号
                {isPaused ? " · 已暂停，改配置后可继续" : ""}
              </>
            }
          >
            <button onClick={handleStart} disabled={loading || (isRunning && !isPaused)}>
              {isPaused
                ? "继续（最新配置）"
                : tab === "broadcast"
                  ? "开始群发"
                  : "开始加群"}
            </button>
            {isRunning && !isPaused && (
              <button className="secondary" onClick={pause} disabled={loading}>暂停</button>
            )}
            {isRunning && <button className="danger" onClick={stop} disabled={loading}>停止</button>}
          </StickyActions>
        </div>
      </div>
    </div>
  );
}
