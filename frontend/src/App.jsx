import { useState, useEffect } from "react";
import "./App.css";

function formatMoney(amount) {
  const num = parseFloat(amount);
  if (isNaN(num)) return amount;
  return "$" + num.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function App() {
  const [org, setOrg] = useState("northwind");
  const [transactions, setTransactions] = useState([]);
  const [lineItems, setLineItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadResult, setUploadResult] = useState(null);
  const [busyActionId, setBusyActionId] = useState(null);

  useEffect(() => {
    fetchData();
  }, [org]);

  async function fetchData() {
    setLoading(true);
    setError(null);
    try {
      const headers = { "X-Organization": org };
      const [resTxn, resItems] = await Promise.all([
        fetch("/api/transactions/", { headers }),
        fetch("/api/capital-call-items/", { headers }),
      ]);

      if (!resTxn.ok || !resItems.ok) {
        throw new Error("failed to load data for this organization");
      }

      const txns = await resTxn.json();
      const items = await resItems.json();

      setTransactions(txns);
      setLineItems(items);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleUpload(e) {
    e.preventDefault();
    if (!selectedFile) return;

    setBusyActionId("upload");
    setUploadResult(null);
    setError(null);

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const res = await fetch("/api/transactions/upload/", {
        method: "POST",
        headers: { "X-Organization": org },
        body: formData,
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "upload failed");
      }

      setUploadResult(data);
      fetchData();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyActionId(null);
    }
  }

  async function handleApprove(matchId) {
    setBusyActionId(`approve-${matchId}`);
    try {
      const res = await fetch(`/api/matches/${matchId}/confirm/`, {
        method: "POST",
        headers: { "X-Organization": org },
      });
      if (!res.ok) {
        const data = await res.json();
        alert(data.error || "failed to approve match");
      }
      fetchData();
    } catch (err) {
      alert(err.message);
    } finally {
      setBusyActionId(null);
    }
  }

  async function handleReject(matchId) {
    setBusyActionId(`reject-${matchId}`);
    try {
      const res = await fetch(`/api/matches/${matchId}/reject/`, {
        method: "POST",
        headers: { "X-Organization": org },
      });
      if (!res.ok) {
        const data = await res.json();
        alert(data.error || "failed to reject match");
      }
      fetchData();
    } catch (err) {
      alert(err.message);
    } finally {
      setBusyActionId(null);
    }
  }

  async function handleIgnore(txnId) {
    setBusyActionId(`ignore-${txnId}`);
    try {
      const res = await fetch(`/api/transactions/${txnId}/ignore/`, {
        method: "POST",
        headers: { "X-Organization": org },
      });
      if (!res.ok) {
        const data = await res.json();
        alert(data.error || "failed to ignore transaction");
      }
      fetchData();
    } catch (err) {
      alert(err.message);
    } finally {
      setBusyActionId(null);
    }
  }

  return (
    <div className="container">
      {/* header */}
      <div className="top-bar">
        <div>
          <h1>FundFlow</h1>
          <p className="subtitle">Capital Call & Bank Reconciliation</p>
        </div>
        <div className="org-selector">
          <label>organization:</label>
          <select value={org} onChange={(e) => setOrg(e.target.value)}>
            <option value="northwind">Northwind Ventures</option>
            <option value="bluebird">Bluebird Capital</option>
          </select>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {/* upload card */}
      <div className="card">
        <h2>upload bank statement csv</h2>
        <form onSubmit={handleUpload} className="upload-form">
          <input
            type="file"
            accept=".csv"
            onChange={(e) => setSelectedFile(e.target.files[0])}
          />
          <button
            type="submit"
            disabled={!selectedFile || busyActionId === "upload"}
            className="btn-upload"
          >
            {busyActionId === "upload" ? "uploading..." : "upload csv"}
          </button>
        </form>

        {uploadResult && (
          <div className="summary-box">
            <strong>summary:</strong> {uploadResult.imported} imported, {uploadResult.duplicates} duplicates
            {uploadResult.errors && uploadResult.errors.length > 0 && (
              <ul style={{ color: "#991b1b" }}>
                {uploadResult.errors.map((err, i) => (
                  <li key={i}>line {err.line}: {err.message}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {/* line item panel */}
      <div className="card">
        <div className="card-header">
          <h2>capital call line items</h2>
          <span className="count-label">{lineItems.length} records</span>
        </div>

        {loading ? (
          <p className="subtitle">loading line items...</p>
        ) : lineItems.length === 0 ? (
          <p className="subtitle">no line items found.</p>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>call</th>
                  <th>date</th>
                  <th>investor</th>
                  <th>expected ref</th>
                  <th>called</th>
                  <th>funded</th>
                  <th>remaining</th>
                  <th>status</th>
                </tr>
              </thead>
              <tbody>
                {lineItems.map((item) => (
                  <tr key={item.id}>
                    <td>{item.capital_call_name}</td>
                    <td>{item.call_date}</td>
                    <td><strong>{item.investor_name}</strong></td>
                    <td><span className="code-ref">{item.expected_reference}</span></td>
                    <td>{formatMoney(item.amount_called)}</td>
                    <td>{formatMoney(item.amount_funded)}</td>
                    <td><strong>{formatMoney(item.remaining_amount)}</strong></td>
                    <td><span className={`badge badge-${item.status}`}>{item.status.replace("_", " ")}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* transactions table */}
      <div className="card">
        <div className="card-header">
          <h2>bank transactions</h2>
          <span className="count-label">{transactions.length} records</span>
        </div>

        {loading ? (
          <p className="subtitle">loading transactions...</p>
        ) : transactions.length === 0 ? (
          <p className="subtitle">no transactions found.</p>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>date</th>
                  <th>description</th>
                  <th>amount</th>
                  <th>status</th>
                  <th>suggested match</th>
                  <th>reason</th>
                  <th>actions</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((t) => {
                  const canIgnore = t.status === "suggested" || t.status === "needs_review";

                  return (
                    <tr key={t.id}>
                      <td style={{ whiteSpace: "nowrap" }}>{t.date}</td>
                      <td>
                        <strong>{t.description}</strong>
                        <div className="sub-ref">ref: {t.bank_reference}</div>
                      </td>
                      <td className={t.transaction_type === "debit" ? "debit" : "credit"}>
                        {formatMoney(t.amount)}
                      </td>
                      <td><span className={`badge badge-${t.status}`}>{t.status.replace("_", " ")}</span></td>
                      <td>
                        {t.matches && t.matches.length > 0 ? (
                          t.matches.map((m) => (
                            <div key={m.id} style={{ marginBottom: "6px" }}>
                              <strong>{m.investor_name}</strong>
                                <span className="sub-ref"> ({m.expected_reference})</span>
                                <div>
                                  <span className={`badge badge-${m.status}`}>{m.status}</span>
                                </div>
                                <div style={{ fontSize: "13px", color: "#475569", marginTop: "4px" }}>
                                  {m.reason}
                                </div>
                            </div>
                          ))
                        ) : (
                          <span style={{ color: "#94a3b8" }}>—</span>
                        )}
                      </td>
                      <td style={{ maxWidth: "260px", color: "#475569" }}>
                        {t.matches && t.matches.length > 0 ? (
                          t.matches.map((m) => (
                            <div key={m.id} style={{ marginBottom: "6px" }}>{m.reason}</div>
                          ))
                        ) : (
                          <span style={{ color: "#94a3b8" }}>—</span>
                        )}
                      </td>
                      <td>
                        <div className="actions-cell">
                          {t.matches &&
                            t.matches
                              .filter((m) => m.status === "proposed")
                              .map((m) => (
                                <div key={m.id} className="action-group">
                                  <button
                                    onClick={() => handleApprove(m.id)}
                                    disabled={busyActionId !== null}
                                    className="btn-approve"
                                  >
                                    {busyActionId === `approve-${m.id}` ? "..." : "approve"}
                                  </button>
                                  <button
                                    onClick={() => handleReject(m.id)}
                                    disabled={busyActionId !== null}
                                    className="btn-reject"
                                  >
                                    {busyActionId === `reject-${m.id}` ? "..." : "reject"}
                                  </button>
                                </div>
                              ))}

                          {canIgnore && (
                            <button
                              onClick={() => handleIgnore(t.id)}
                              disabled={busyActionId !== null}
                              className="btn-ignore"
                            >
                              {busyActionId === `ignore-${t.id}` ? "..." : "ignore"}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}