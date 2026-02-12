import React from "react";

interface UiAutomationPayload {
  kind: "ui";
  status: string;
  testCaseId?: number;
  executionId?: number;
  plan?: any;
  script?: string | null;
  healingHistory?: any;
}

interface Props {
  payload: UiAutomationPayload;
}

export const UiAutomationResponseCard: React.FC<Props> = ({ payload }) => {
  const { status, testCaseId, executionId, plan, script, healingHistory } = payload;

  const steps = plan?.steps ?? [];

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">UI automation result</div>
          <div className="card-subtitle">
            Status: <span className={`status-pill status-${status}`}>{status}</span>
          </div>
        </div>
        <div className="card-meta">
          {typeof testCaseId === "number" && (
            <span className="meta-item">Test case #{testCaseId}</span>
          )}
          {typeof executionId === "number" && (
            <span className="meta-item">Execution #{executionId}</span>
          )}
        </div>
      </div>

      {steps.length > 0 && (
        <section className="card-section">
          <h4 className="section-title">Planner test plan</h4>
          <ol className="steps-list">
            {steps.map((step: any) => (
              <li key={step.step ?? step.description}>
                <div className="step-line">
                  <span className="step-index">{step.step}</span>
                  <span className="step-action">{step.action}</span>
                  <span className="step-description">{step.description}</span>
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}

      {script && (
        <section className="card-section">
          <h4 className="section-title">Generated script (excerpt)</h4>
          <pre className="code-block">
            <code>{String(script).slice(0, 4000)}</code>
          </pre>
        </section>
      )}

      {healingHistory && (
        <section className="card-section">
          <h4 className="section-title">Self-healing summary</h4>
          <ul className="healing-list">
            <li>
              Healed:{" "}
              <span className={healingHistory.healed ? "status-pill status-passed" : ""}>
                {healingHistory.healed ? "Yes" : "No"}
              </span>
            </li>
            {healingHistory.screenshot && (
              <li>Screenshot captured at: {healingHistory.screenshot}</li>
            )}
          </ul>
        </section>
      )}
    </div>
  );
};

