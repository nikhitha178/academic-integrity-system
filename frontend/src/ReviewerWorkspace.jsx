import { useCallback, useEffect, useState } from 'react';
import { apiRequest } from './api/client';
import EvidencePanel from './EvidencePanel';

const FINDINGS = [
  {
    value: 'ACADEMIC_MISCONDUCT_FOUND',
    label: 'Academic misconduct found',
  },
  {
    value: 'NO_MISCONDUCT_FOUND',
    label: 'No misconduct found',
  },
  {
    value: 'INSUFFICIENT_EVIDENCE',
    label: 'Insufficient evidence',
  },
];

const STATUS_LABELS = {
  UNDER_INVESTIGATION: 'Under investigation',
  DECIDED: 'Decided',
  APPEALED: 'Appealed',
  CLOSED: 'Closed',
};

export default function ReviewerWorkspace({ token, user, onLogout }) {
  const [cases, setCases] = useState([]);
  const [selectedCaseId, setSelectedCaseId] = useState('');
  const [finding, setFinding] = useState('INSUFFICIENT_EVIDENCE');
  const [sanction, setSanction] = useState('No sanction recommended');
  const [rationale, setRationale] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const loadCases = useCallback(async () => {
    setLoading(true);
    setError('');

    try {
      const result = await apiRequest(
        '/cases?limit=100&offset=0',
        {},
        token,
      );

      const items = result.items || [];
      setCases(items);

      setSelectedCaseId(current => {
        if (items.some(item => item.case_id === current)) {
          return current;
        }
        return items[0]?.case_id || '';
      });
    } catch (err) {
      setError(err.message || 'Unable to load assigned cases.');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadCases();
  }, [loadCases]);

  const selectedCase = cases.find(
    item => item.case_id === selectedCaseId,
  );

  async function submitDecision(event) {
    event.preventDefault();
    if (!selectedCase) return;

    setError('');
    setNotice('');

    if (selectedCase.case_status !== 'UNDER_INVESTIGATION') {
      setError('A decision can only be submitted for a case under investigation.');
      return;
    }

    if (rationale.trim().length < 10) {
      setError('Please provide a rationale of at least 10 characters.');
      return;
    }

    setSubmitting(true);

    try {
      await apiRequest(
        `/cases/${encodeURIComponent(selectedCase.case_id)}/decision`,
        {
          method: 'POST',
          body: JSON.stringify({
            finding,
            sanction_recommended: sanction.trim(),
            rationale_text: rationale.trim(),
          }),
        },
        token,
      );

      setNotice(`Decision submitted for ${selectedCase.case_id}.`);
      setRationale('');
      await loadCases();
    } catch (err) {
      setError(err.message || 'Unable to submit the decision.');
    } finally {
      setSubmitting(false);
    }
  }

  const pageStyle = {
    minHeight: '100vh',
    background: '#f5f7fb',
    color: '#182230',
    padding: '24px',
    fontFamily: 'inherit',
  };

  const panelStyle = {
    background: '#ffffff',
    border: '1px solid #e2e8f0',
    borderRadius: '12px',
    padding: '20px',
    marginBottom: '20px',
  };

  const fieldStyle = {
    display: 'block',
    width: '100%',
    boxSizing: 'border-box',
    padding: '10px 12px',
    border: '1px solid #cbd5e1',
    borderRadius: '7px',
    marginTop: '6px',
    marginBottom: '16px',
    font: 'inherit',
    background: '#fff',
  };

  const buttonStyle = {
    padding: '10px 16px',
    border: 'none',
    borderRadius: '7px',
    background: '#2457c5',
    color: '#fff',
    font: 'inherit',
    cursor: 'pointer',
  };

  return (
    <main className="reviewer-workspace">
      <header className="reviewer-header reviewer-panel">
        <div>
          <h1 style={{ margin: '0 0 6px' }}>Reviewer Workspace</h1>
          <p style={{ margin: 0, color: '#64748b' }}>
            Signed in as {user.username} · Case Reviewer
          </p>
        </div>

        <button type="button" onClick={onLogout} className="reviewer-button">
          Sign out
        </button>
      </header>

      {
        error && (
          <div
            role="alert"
            style={{
              ...panelStyle,
              color: '#b42318',
              borderColor: '#f2b8b5',
            }}
          >
            {error}
          </div>
        )
      }

      {
        notice && (
          <div
            role="status"
            style={{
              ...panelStyle,
              color: '#166534',
              borderColor: '#bbf7d0',
            }}
          >
            {notice}
          </div>
        )
      }

      <section className="reviewer-panel">
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: '12px',
            flexWrap: 'wrap',
          }}
        >
          <div>
            <h2 style={{ marginTop: 0 }}>My assigned cases</h2>
            <p style={{ color: '#64748b' }}>
              Cases are loaded using your signed-in account's permissions.
            </p>
          </div>

          <button
            type="button"
            onClick={loadCases}
            disabled={loading}
            className="reviewer-button"
          >
            {loading ? 'Refreshing…' : 'Refresh cases'}
          </button>
        </div>

        {loading ? (
          <p>Loading cases…</p>
        ) : cases.length === 0 ? (
          <p>No accessible cases were found for your account.</p>
        ) : (
          <>
            <label htmlFor="reviewer-case">
              Select a case ({cases.length} loaded)
            </label>
            <select
              id="reviewer-case"
              value={selectedCaseId}
              onChange={event => {
                setSelectedCaseId(event.target.value);
                setError('');
                setNotice('');
              }}
              style={fieldStyle}
            >
              {cases.map(item => (
                <option key={item.case_id} value={item.case_id}>
                  {item.case_id} — {STATUS_LABELS[item.case_status] || item.case_status}
                </option>
              ))}
            </select>
          </>
        )}
      </section>

      {
        selectedCase && (
          <>
            <section className="reviewer-panel">
              <h2>Case details</h2>
              <p><strong>Case ID:</strong> {selectedCase.case_id}</p>
              <p><strong>Submission ID:</strong> {selectedCase.submission_id}</p>
              <p>
                <strong>Status:</strong>{' '}
                {STATUS_LABELS[selectedCase.case_status] || selectedCase.case_status}
              </p>
              <p><strong>Created:</strong> {selectedCase.created_at
                ? new Date(selectedCase.created_at).toLocaleString()
                : 'Not available'}
              </p>
            </section>

            <EvidencePanel
              token={token}
              cases={cases}
              selectedCase={selectedCaseId}
            />

            <section className="reviewer-panel">
              <h2>Submit case decision</h2>
              <p style={{ color: '#64748b' }}>
                Review the available evidence and provide a reasoned finding.
                Submitted decisions are recorded by the backend.
              </p>

              {selectedCase.case_status !== 'UNDER_INVESTIGATION' ? (
                <p>
                  This case is not under investigation, so a new decision cannot
                  be submitted from this form.
                </p>
              ) : (
                <form onSubmit={submitDecision}>
                  <label htmlFor="decision-finding">Finding</label>
                  <select
                    id="decision-finding"
                    value={finding}
                    onChange={event => setFinding(event.target.value)}
                    style={fieldStyle}
                    required
                  >
                    {FINDINGS.map(item => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </select>

                  <label htmlFor="decision-sanction">
                    Recommended sanction
                  </label>
                  <input
                    id="decision-sanction"
                    value={sanction}
                    onChange={event => setSanction(event.target.value)}
                    maxLength={80}
                    required
                    style={fieldStyle}
                  />

                  <label htmlFor="decision-rationale">Rationale</label>
                  <textarea
                    id="decision-rationale"
                    value={rationale}
                    onChange={event => setRationale(event.target.value)}
                    minLength={10}
                    maxLength={10000}
                    rows={6}
                    required
                    placeholder="Explain how the evidence supports your finding."
                    style={fieldStyle}
                  />

                  <button
                    type="submit"
                    disabled={submitting || !sanction.trim() || rationale.trim().length < 10}
                    style={{
                      ...buttonStyle,
                      opacity: submitting ? 0.65 : 1,
                    }}
                  >
                    {submitting ? 'Submitting…' : 'Submit decision'}
                  </button>
                </form>
              )}
            </section>
          </>
        )
      }
    </main >
  );
}
