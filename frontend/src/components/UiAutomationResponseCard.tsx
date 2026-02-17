import React from "react";

interface UiAutomationPayload {
  kind: "ui";
  status: string;
  testCaseId?: number;
  executionId?: number;
  plan?: any;
  script?: string | null;
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

interface Props {
  payload: UiAutomationPayload;
}

export const UiAutomationResponseCard: React.FC<Props> = ({ payload }) => {
  const { status, testCaseId, executionId, plan, script, healingHistory, isV2, checkpoints } = payload;

  const steps = plan?.steps ?? [];

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">
            {isV2 ? "Enhanced System V2 Result" : "UI automation result"}
          </div>
          <div className="card-subtitle">
            Status: <span className={`status-pill status-${status}`}>{status}</span>
            {isV2 && payload.duration_ms && (
              <> · Duration: {(payload.duration_ms / 1000).toFixed(1)}s</>
            )}
          </div>
        </div>
        <div className="card-meta">
          {typeof testCaseId === "number" && (
            <span className="meta-item">Test case #{testCaseId}</span>
          )}
          {typeof executionId === "number" && (
            <span className="meta-item">Execution #{executionId}</span>
          )}
          {isV2 && payload.assertion_count !== undefined && (
            <span className="meta-item">Assertions: {payload.assertion_count}</span>
          )}
          {isV2 && payload.action_count !== undefined && (
            <span className="meta-item">Actions: {payload.action_count}</span>
          )}
        </div>
      </div>

      {isV2 && checkpoints && checkpoints.length > 0 && (
        <section className="card-section">
          <h4 className="section-title">Execution Checkpoints</h4>
          <ol className="steps-list">
            {checkpoints.map((cp) => (
              <li key={cp.step_id}>
                <div className="step-line">
                  <span className={`step-index ${cp.success ? 'success' : 'error'}`}>
                    {cp.success ? '✅' : '❌'} Step {cp.step_id}
                  </span>
                  <span className="step-description">{cp.description}</span>
                  <span className="step-action">State: {cp.state}</span>
                  {cp.error && <div className="error-text">{cp.error}</div>}
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}

      {steps.length > 0 && (
        <section className="card-section">
          <h4 className="section-title">{isV2 ? "Test Plan" : "Planner test plan"}</h4>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #ddd', textAlign: 'left' }}>
                <th style={{ padding: '8px', width: '60px' }}>#</th>
                <th style={{ padding: '8px', width: '120px' }}>Action</th>
                <th style={{ padding: '8px' }}>Description</th>
              </tr>
            </thead>
            <tbody>
              {steps.map((step: any, idx: number) => (
                <tr key={step.step ?? idx} style={{ borderBottom: '1px solid #eee' }}>
                  <td style={{ padding: '8px' }}>{step.step ?? idx + 1}</td>
                  <td style={{ padding: '8px', textTransform: 'lowercase' }}>{step.intent || step.type || step.action}</td>
                  <td style={{ padding: '8px' }}>{step.description || step.target || step.value || ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
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

