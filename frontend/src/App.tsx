import React, { useState } from "react";
import { AgentChat } from "./components/AgentChat";

type AgentType = "synthetic" | "ui-automation";

export default function App() {
  const [activeAgent, setActiveAgent] = useState<AgentType>("synthetic");

  return (
    <div className="app-root">
      <header className="app-header">
        <div>
          <div className="app-title">Enterprise Test Agents</div>
          <div className="app-subtitle">
            Conversational agents for Synthetic Data Generation and UI Automation
          </div>
        </div>
        <div className="app-badge">Alpha</div>
      </header>

      <main className="app-main">
        <div className="agent-tabs">
          <button
            className={
              "agent-tab" + (activeAgent === "synthetic" ? " agent-tab-active" : "")
            }
            onClick={() => setActiveAgent("synthetic")}
          >
            Synthetic Data Agent
          </button>
          <button
            className={
              "agent-tab" +
              (activeAgent === "ui-automation" ? " agent-tab-active" : "")
            }
            onClick={() => setActiveAgent("ui-automation")}
          >
            UI Automation Agent
          </button>
        </div>

        <section className="agent-section">
          {activeAgent === "synthetic" ? (
            <AgentChat key="synthetic" agentType="synthetic" />
          ) : (
            <AgentChat key="ui-automation" agentType="ui-automation" />
          )}
        </section>
      </main>
    </div>
  );
}

