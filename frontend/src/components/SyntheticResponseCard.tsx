import React from "react";

import type { ChatMessage } from "./AgentChat";

interface SyntheticPayload {
  kind: "synthetic";
  runId: number;
  schemaId?: number;
  rowsGenerated: number;
  dataPreview: any[];
}

interface Props {
  payload: SyntheticPayload;
}

export const SyntheticResponseCard: React.FC<Props> = ({ payload }) => {
  const { runId, schemaId, rowsGenerated, dataPreview } = payload;

  const columns =
    dataPreview && dataPreview.length > 0
      ? Object.keys(dataPreview[0] as Record<string, unknown>)
      : [];

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">Synthetic data generated</div>
          <div className="card-subtitle">
            Run #{runId} • {rowsGenerated} rows
          </div>
        </div>
        {schemaId && <div className="badge">Schema #{schemaId}</div>}
      </div>

      {columns.length > 0 ? (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                {columns.map(col => (
                  <th key={col}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {dataPreview.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {columns.map(col => (
                    <td key={col}>{String((row as Record<string, unknown>)[col] ?? "")}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <div className="card-footer-note">
            Showing up to {dataPreview.length} preview rows. Full dataset is stored in the
            database.
          </div>
        </div>
      ) : (
        <div className="card-empty">No preview data returned from the agent.</div>
      )}
    </div>
  );
};

