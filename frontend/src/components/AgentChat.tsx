import React, { useCallback, useState, useEffect } from "react";
import { ChatMessageList } from "./ChatMessageList";
import { ChatInput } from "./ChatInput";
import { SyntheticResponseCard } from "./SyntheticResponseCard";
import { UiAutomationResponseCard } from "./UiAutomationResponseCard";

const getApiBase = (): string => {
  if (typeof import.meta.env.VITE_API_URL === "string" && import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL.replace(/\/$/, "");
  }
  if (import.meta.env.DEV) {
    // Use empty string so Vite proxy (vite.config.ts) forwards /chats, /synthetic, /ui to backend
    return "";
  }
  return "";
};

export type AgentType = "synthetic" | "ui-automation";

type Sender = "user" | "agent";

interface BaseMessage {
  id: string;
  sender: Sender;
  text: string;
  createdAt: string;
  isLoading?: boolean;
}

interface SyntheticPayload {
  kind: "synthetic";
  runId: number;
  schemaId?: number;
  rowsGenerated: number;
  dataPreview: any[];
}

interface UiAutomationPayload {
  kind: "ui";
  status: string;
  testCaseId?: number;
  executionId?: number;
  plan?: any;
  script?: string;
  healingHistory?: any;
  // NEW: Enhanced System V2 fields
  isV2?: boolean;
  passed?: boolean;
  total_steps?: number;
  executed_steps?: number;
  failed_step?: number | null;
  duration_ms?: number;
  checkpoints?: Array<{
    step_id: number;
    description: string;
    state: string;
    timestamp: string;
    success: boolean;
    error: string | null;
  }>;
  assertion_count?: number;
  action_count?: number;
}

type MessagePayload = SyntheticPayload | UiAutomationPayload | null;

export interface ChatMessage extends BaseMessage {
  payload: MessagePayload;
}

interface ChatListItem {
  id: number;
  agent_type: string;
  title: string | null;
  updated_at: string;
  message_count: number;
}

interface AgentChatProps {
  agentType: AgentType;
}

const agentTypeForApi = (t: AgentType): string =>
  t === "synthetic" ? "synthetic" : "ui-automation";

export const AgentChat: React.FC<AgentChatProps> = ({ agentType }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatId, setChatId] = useState<number | null>(null);
  const [chats, setChats] = useState<ChatListItem[]>([]);
  const [chatsLoading, setChatsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [scriptLanguage, setScriptLanguage] = useState<"javascript" | "typescript">("javascript");
  const [useSyntheticData, setUseSyntheticData] = useState(false);
  const [visibleBrowser, setVisibleBrowser] = useState(true);
  const [startUrl, setStartUrl] = useState("");
  const [liveTick, setLiveTick] = useState(0);
  const [runStage, setRunStage] = useState<string | null>(null);
  const [liveScreenshotError, setLiveScreenshotError] = useState(false);

  const apiBase = getApiBase();
  const apiAgentType = agentTypeForApi(agentType);

  const fetchChats = useCallback(async () => {
    setChatsLoading(true);
    try {
      const url = `${apiBase}/chats?agent_type=${encodeURIComponent(apiAgentType)}&limit=50`;
      const res = await fetch(url);
      if (res.ok) {
        const list: ChatListItem[] = await res.json();
        setChats(list);
      }
      // On error, keep previous list so we don't wipe the sidebar
    } catch {
      // Keep existing chats on network error
    } finally {
      setChatsLoading(false);
    }
  }, [apiBase, apiAgentType]);

  useEffect(() => {
    fetchChats();
  }, [fetchChats]);

  const loadChat = useCallback(
    async (id: number) => {
      try {
        const res = await fetch(`${apiBase}/chats/${id}`);
        if (!res.ok) return;
        const data = await res.json();
        const msgs: ChatMessage[] = (data.messages || []).map((m: any) => ({
          id: String(m.id),
          sender: m.sender,
          text: m.text,
          createdAt: m.created_at || new Date().toISOString(),
          payload: m.payload ?? null
        }));
        setMessages(msgs);
        setChatId(id);
      } catch {
        setMessages([]);
        setChatId(null);
      }
    },
    [apiBase]
  );

  const handleNewChat = useCallback(() => {
    setChatId(null);
    setMessages([]);
    // Refetch so the chat we're leaving (if any) appears in the sidebar and stays stored
    fetchChats();
  }, [fetchChats]);

  const handleDeleteChat = useCallback(
    async (id: number, e: React.MouseEvent) => {
      e.stopPropagation();
      if (!confirm("Delete this chat?")) return;
      try {
        const res = await fetch(`${apiBase}/chats/${id}`, { method: "DELETE" });
        if (res.ok) {
          if (chatId === id) {
            setChatId(null);
            setMessages([]);
          }
          fetchChats();
        }
      } catch {
        fetchChats();
      }
    },
    [apiBase, chatId, fetchChats]
  );

  // Poll current run status and live screenshot tick while a UI run is in progress (1s for smooth Cursor-style browser view)
  useEffect(() => {
    if (agentType !== "ui-automation" || !isSending) {
      setRunStage(null);
      return;
    }
    setLiveScreenshotError(false);
    const pollStatus = async () => {
      try {
        const res = await fetch(`${apiBase}/ui/current-run/status`);
        if (res.ok) {
          const data = await res.json();
          if (data.running && data.stage) {
            setRunStage(data.stage);
          }
        }
      } catch {
        // ignore
      }
    };
    pollStatus();
    const statusInterval = window.setInterval(pollStatus, 1000);
    const tickInterval = window.setInterval(() => setLiveTick(prev => prev + 1), 1000);
    return () => {
      window.clearInterval(statusInterval);
      window.clearInterval(tickInterval);
    };
  }, [agentType, isSending, apiBase]);

  const handleSend = useCallback(
    async (text: string, fileText?: string) => {
      if (!text.trim() && !fileText) return;

      const now = new Date().toISOString();
      const userMsg: ChatMessage = {
        id: `u-${now}`,
        sender: "user",
        text,
        createdAt: now,
        payload: null
      };

      setMessages(prev => [...prev, userMsg]);
      setIsSending(true);

      const combinedText =
        fileText && fileText.trim().length > 0
          ? `${text}\n\n--- Uploaded test case ---\n${fileText}`
          : text;

      try {
        if (agentType === "synthetic") {
          const res = await fetch(`${apiBase}/synthetic/generate-from-text`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              user_input: combinedText,
              model: "GaussianCopula",
              chat_id: chatId ?? undefined
            })
          });

          if (!res.ok) {
            const msg =
              res.status === 404
                ? "Synthetic endpoint not found (404). Check backend is running."
                : `Synthetic agent error: ${res.status} ${res.statusText}`;
            throw new Error(msg);
          }

          const data = await res.json();
          if (data.chat_id != null) setChatId(data.chat_id);

          const agentMsg: ChatMessage = {
            id: `a-${Date.now()}`,
            sender: "agent",
            text:
              data.message ||
              `Generated synthetic data run #${data.run_id} with ${data.rows_generated ?? data.data?.length ?? 0} rows.`,
            createdAt: new Date().toISOString(),
            payload: {
              kind: "synthetic",
              runId: data.run_id,
              schemaId: data.schema_id,
              rowsGenerated: data.rows_generated ?? data.data?.length ?? 0,
              dataPreview: Array.isArray(data.data) ? data.data.slice(0, 50) : []
            }
          };
          setMessages(prev => [...prev, agentMsg]);
        } else {
          // UI Automation: Use Enhanced Deterministic System V2
          const res = await fetch(`${apiBase}/ui-automation-v2/run`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                natural_language: combinedText,
                visible_browser: visibleBrowser,
                start_url: startUrl.trim() || undefined,
                use_planner_agents: true,
                use_generator_hints: true,
                use_healer_agent_in_v2: true,
                chat_id: chatId ?? undefined
              })
            });

            if (!res.ok) {
              const msg =
                res.status === 404
                  ? "Enhanced System V2 endpoint not found (404). Make sure backend is updated with ui_automation_v2 router."
                  : `Enhanced System V2 error: ${res.status} ${res.statusText}`;
              throw new Error(msg);
            }

            const data = await res.json();
            if (data.chat_id != null) setChatId(data.chat_id);

            const agentMsg: ChatMessage = {
              id: `a-${Date.now()}`,
              sender: "agent",
              text: data.passed
                ? `✅ Test PASSED - ${data.executed_steps}/${data.total_steps} steps (${(data.duration_ms / 1000).toFixed(1)}s)`
                : `❌ Test FAILED at step ${data.failed_step} - ${data.error}`,
              createdAt: new Date().toISOString(),
              payload: {
                kind: "ui",
                status: data.passed ? "passed" : "failed",
                isV2: true,
                passed: data.passed,
                total_steps: data.total_steps,
                executed_steps: data.executed_steps,
                failed_step: data.failed_step,
                duration_ms: data.duration_ms,
                checkpoints: data.checkpoints ?? [],
                assertion_count: data.assertion_count,
                action_count: data.action_count,
                plan: data.plan ?? null,
                script: data.script ?? null,
                healingHistory: null
              }
            };
            setMessages(prev => [...prev, agentMsg]);
        }
        fetchChats();
      } catch (err) {
        const errorText =
          err instanceof Error ? err.message : "Unknown error while calling agent";
        const errorMsg: ChatMessage = {
          id: `e-${Date.now()}`,
          sender: "agent",
          text: `Sorry, something went wrong: ${errorText}`,
          createdAt: new Date().toISOString(),
          payload: null
        };
        setMessages(prev => [...prev, errorMsg]);
      } finally {
        setIsSending(false);
      }
    },
    [agentType, scriptLanguage, useSyntheticData, visibleBrowser, chatId, apiBase, fetchChats]
  );

  return (
    <div className="agent-chat-root">
      <aside className="agent-chat-sidebar">
        <button type="button" className="chat-sidebar-new" onClick={handleNewChat}>
          + New chat
        </button>
        {chatsLoading ? (
          <div className="chat-sidebar-loading">Loading…</div>
        ) : (
          <ul className="chat-sidebar-list">
            {chats.length === 0 && (
              <li className="chat-sidebar-empty">
                No previous chats. Send a message to create one.
              </li>
            )}
            {chats.map(c => (
              <li
                key={c.id}
                className={"chat-sidebar-item" + (chatId === c.id ? " chat-sidebar-item-active" : "")}
                onClick={() => loadChat(c.id)}
              >
                <span className="chat-sidebar-item-title" title={c.title || "Chat"}>
                  {c.title || "New chat"}
                </span>
                <button
                  type="button"
                  className="chat-sidebar-item-delete"
                  onClick={e => handleDeleteChat(c.id, e)}
                  aria-label="Delete chat"
                  title="Delete this chat"
                >
                  Delete
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>

      <div className="agent-chat-main">
        <div className="agent-chat-header">
          <div>
            <div className="agent-title">
              {agentType === "synthetic" ? "Synthetic Data Agent" : "UI Automation Agent"}
            </div>
            <div className="agent-description">
              {agentType === "synthetic"
                ? "Chat with an agent that crawls your app flows and generates SDV-compatible synthetic data."
                : "Chat with an agent that plans, generates, heals, and executes Playwright UI tests."}
            </div>
          </div>

          {agentType === "ui-automation" && (
            <div className="agent-settings">
              <label className="agent-setting">
                <span>Script language</span>
                <select
                  value={scriptLanguage}
                  onChange={e => setScriptLanguage(e.target.value as "javascript" | "typescript")}
                >
                  <option value="javascript">JavaScript</option>
                  <option value="typescript">TypeScript</option>
                </select>
              </label>
              <label className="agent-setting">
                <span>Use synthetic data</span>
                <input
                  type="checkbox"
                  checked={useSyntheticData}
                  onChange={e => setUseSyntheticData(e.target.checked)}
                />
              </label>
              <label className="agent-setting">
                <span>Show browser during run</span>
                <input
                  type="checkbox"
                  checked={visibleBrowser}
                  onChange={e => setVisibleBrowser(e.target.checked)}
                />
              </label>
              <label className="agent-setting">
                <span>Start URL (optional)</span>
                <input
                  type="text"
                  placeholder="e.g. https://www.lg.com/in"
                  value={startUrl}
                  onChange={e => setStartUrl(e.target.value)}
                  style={{ width: "220px" }}
                />
              </label>
            </div>
          )}
        </div>

        <div className="agent-chat-body">
          {agentType === "ui-automation" && (
            <div className="live-view-container">
              <div className="live-view-header">
                <span>Live browser (updates every ~2s during run)</span>
                <span className="live-view-status">
                  {isSending
                    ? runStage
                      ? (() => {
                          const labels: Record<string, string> = {
                            plan: "Planning…",
                            generate: "Generating script…",
                            validate: "Validating…",
                            execute: "Executing in browser (may take 3–8 min)…",
                            heal: "Healing & re-running…"
                          };
                          return labels[runStage] || `Running (${runStage})…`;
                        })()
                      : "Starting…"
                    : "Idle"}
                </span>
              </div>
              {isSending ? (
                (runStage === "execute" || runStage === "heal") && !liveScreenshotError ? (
                  <img
                    className="live-view-image"
                    src={`${apiBase}/ui/current-run/live-screenshot?t=${liveTick}`}
                    alt="Live UI run"
                    onError={() => setLiveScreenshotError(true)}
                  />
                ) : (
                  <div className="live-view-placeholder">
                    {runStage
                      ? "Browser view will appear when execution starts. Run can take 3–8 minutes."
                      : "Starting run…"}
                  </div>
                )
              ) : (
                <div className="live-view-placeholder">
                  Start a UI automation run to see the browser inside the app (Cursor-style).
                </div>
              )}
            </div>
          )}
          <ChatMessageList
            messages={messages}
            renderPayload={msg => {
              if (!msg.payload) return null;
              if (msg.payload.kind === "synthetic") {
                return <SyntheticResponseCard payload={msg.payload} />;
              }
              if (msg.payload.kind === "ui") {
                return <UiAutomationResponseCard payload={msg.payload} />;
              }
              return null;
            }}
          />
        </div>

        <div className="agent-chat-footer">
          <ChatInput onSend={handleSend} disabled={isSending} />
        </div>
      </div>
    </div>
  );
};
