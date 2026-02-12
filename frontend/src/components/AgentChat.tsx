import React, { useCallback, useState } from "react";
import { ChatMessageList } from "./ChatMessageList";
import { ChatInput } from "./ChatInput";
import { SyntheticResponseCard } from "./SyntheticResponseCard";
import { UiAutomationResponseCard } from "./UiAutomationResponseCard";

// API base URL: use env override, or in dev call backend directly so proxy is not required
const getApiBase = (): string => {
  if (typeof import.meta.env.VITE_API_URL === "string" && import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL.replace(/\/$/, "");
  }
  if (import.meta.env.DEV) {
    // Default dev port for this project. (8000 is commonly used by other local services.)
    return "http://localhost:8001";
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
}

type MessagePayload = SyntheticPayload | UiAutomationPayload | null;

export interface ChatMessage extends BaseMessage {
  payload: MessagePayload;
}

interface AgentChatProps {
  agentType: AgentType;
}

export const AgentChat: React.FC<AgentChatProps> = ({ agentType }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [scriptLanguage, setScriptLanguage] = useState<"javascript" | "typescript">(
    "javascript"
  );
  const [useSyntheticData, setUseSyntheticData] = useState(false);

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

      try {
        const combinedText =
          fileText && fileText.trim().length > 0
            ? `${text}\n\n--- Uploaded test case ---\n${fileText}`
            : text;

        const apiBase = getApiBase();

        if (agentType === "synthetic") {
          const res = await fetch(`${apiBase}/synthetic/generate-from-text`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              user_input: combinedText,
              model: "GaussianCopula"
            })
          });

          if (!res.ok) {
            const msg = res.status === 404
              ? "Synthetic endpoint not found (404). Check backend is running at http://localhost:8000"
              : `Synthetic agent error: ${res.status} ${res.statusText}`;
            throw new Error(msg);
          }

          const data = await res.json();

          const agentMsg: ChatMessage = {
            id: `a-${Date.now()}`,
            sender: "agent",
            text: `Generated synthetic data run #${data.run_id} with ${data.rows_generated ?? data.data?.length ?? 0} rows.`,
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
          const res = await fetch(`${apiBase}/ui/run`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              raw_input: combinedText,
              use_synthetic_data: useSyntheticData,
              synthetic_run_id: undefined,
              script_language: scriptLanguage
            })
          });

          if (!res.ok) {
            const msg = res.status === 404
              ? "UI automation endpoint not found (404). Check backend is running at http://localhost:8000"
              : `UI automation agent error: ${res.status} ${res.statusText}`;
            throw new Error(msg);
          }

          const data = await res.json();

          const agentMsg: ChatMessage = {
            id: `a-${Date.now()}`,
            sender: "agent",
            text: `UI automation ${data.status} for execution ${data.execution_id}.`,
            createdAt: new Date().toISOString(),
            payload: {
              kind: "ui",
              status: data.status,
              testCaseId: data.test_case_id,
              executionId: data.execution_id,
              // Prefer explicit plan/script fields, fall back gracefully if missing
              plan: data.plan ?? data.validation ?? null,
              script: data.script ?? null,
              healingHistory: {
                healed: data.healed,
                screenshot: data.screenshot
              }
            }
          };

          setMessages(prev => [...prev, agentMsg]);
        }
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
    [agentType, scriptLanguage, useSyntheticData]
  );

  return (
    <div className="agent-chat-root">
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
                onChange={e =>
                  setScriptLanguage(e.target.value as "javascript" | "typescript")
                }
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
          </div>
        )}
      </div>

      <div className="agent-chat-body">
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
  );
};

