
import { useCallback, useEffect, useState } from 'react';
import { apiRequest } from './api/client';

export default function IndependentAppealWorkspace({ token, user, onLogout }) {
  const [appeals, setAppeals] = useState([]);
  const [selectedId, setSelectedId] = useState('');
  const [selectedAppeal, setSelectedAppeal] = useState(null);
  const [outcome, setOutcome] = useState('UPHELD');
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const loadAppeals = useCallback(async () => {
    setLoading(true);
    setError('');

    try {
      const result = await apiRequest('/appeals', {}, token);
      const items = Array.isArray(result) ? result : [];
      setAppeals(items);

      setSelectedId((current) => {
        if (current && items.some((item) => item.appeal_id === current)) {
          return current;
        }
        return items[0]?.appeal_id || '';
      });
    } catch (err) {
      setError(err.message || 'Unable to load assigned appeals.');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadAppeals();
  }, [loadAppeals]);

  useEffect(() => {
    if (!selectedId) {
      setSelectedAppeal(null);
      return;
    }

    let cancelled = false;

    async function loadDetails() {
      setError('');
      setSelectedAppeal(null);

      try {
        const result = await apiRequest(`/appeals/${selectedId}`, {}, token);
        if (!cancelled) setSelectedAppeal(result);
      } catch (err) {
        if (!cancelled) {
          setError(err.message || 'Unable to load appeal details.');
        }
      }
    }

    loadDetails();
    return () => {
      cancelled = true;
    };
  }, [selectedId, token]);

  async function submitReview(event) {
    event.preventDefault();

    if (!selectedAppeal) return;

    const confirmed = window.confirm(
      `Submit the outcome "${outcome}" for appeal ${selectedAppeal.appeal_id}? This action will close the appeal.`
    );

    if (!confirmed) return;

    setSubmitting(true);
    setError('');
    setMessage('');

    try {
      await apiRequest(
        `/appeals/${selectedAppeal.appeal_id}/review`,
        {
          method: 'POST',
          body: JSON.stringify({ review_outcome: outcome }),
        },
        token
      );

      setMessage('Appeal review submitted successfully.');
      await loadAppeals();
    } catch (err) {
      setError(err.message || 'Unable to submit the appeal review.');
    } finally {
      setSubmitting(false);
    }
  }

  const pendingAppeals = appeals.filter(
    (appeal) => appeal.appeal_status === 'UNDER_INDEPENDENT_REVIEW'
  );

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-mark small-mark">AI</div>
          <div>
            <strong>Academic Integrity</strong>
            <p>Appeal Review Workspace</p>
          </div>
        </div>

        <div className="sidebar-user">
          <p className="eyebrow">SIGNED IN AS</p>
          <strong>{user?.username || 'Reviewer'}</strong>
          <p>Independent Appeal Reviewer</p>
        </div>

        <button className="secondary-button" onClick={onLogout}>
          Log out
        </button>
      </aside>

      <section className="main-content">
        <header className="page-header">
          <div>
            <p className="eyebrow">INDEPENDENT REVIEW</p>
            <h1>Appeal Review</h1>
            <p>Review assigned appeals and record an independent outcome.</p>
          </div>
          <button
            className="secondary-button"
            onClick={loadAppeals}
            disabled={loading}
          >
            Refresh appeals
          </button>
        </header>

        <section className="stats-grid">
          <article className="stat-card">
            <span>Total assigned appeals</span>
            <strong>{appeals.length}</strong>
          </article>
          <article className="stat-card">
            <span>Awaiting review</span>
            <strong>{pendingAppeals.length}</strong>
          </article>
          <article className="stat-card">
            <span>Completed reviews</span>
            <strong>{appeals.length - pendingAppeals.length}</strong>
          </article>
        </section>

        {error && <div className="session-message" role="alert">{error}</div>}
        {message && <div className="session-message" role="status">{message}</div>}

        <section className="table-card">
          <div className="table-heading">
            <div>
              <h2>Your assigned appeals</h2>
              <p>Only appeals accessible to your account are returned by the API.</p>
            </div>
          </div>

          {loading ? (
            <p>Loading appeals…</p>
          ) : appeals.length === 0 ? (
            <p>No accessible appeals were found for this account.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Appeal ID</th>
                    <th>Case ID</th>
                    <th>Status</th>
                    <th>Outcome</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {appeals.map((appeal) => (
                    <tr key={appeal.appeal_id}>
                      <td>{appeal.appeal_id}</td>
                      <td>{appeal.case_id}</td>
                      <td>{appeal.appeal_status}</td>
                      <td>{appeal.review_outcome || 'Pending'}</td>
                      <td>
                        <button
                          className="secondary-button"
                          onClick={() => {
                            setSelectedId(appeal.appeal_id);
                            setMessage('');
                          }}
                        >
                          View details
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {selectedAppeal && (
          <section className="table-card">
            <div className="table-heading">
              <div>
                <h2>Appeal details</h2>
                <p>{selectedAppeal.appeal_id} · Case {selectedAppeal.case_id}</p>
              </div>
            </div>

            <dl className="detail-list">
              <dt>Decision ID</dt>
              <dd>{selectedAppeal.decision_id}</dd>

              <dt>Assigned reviewer ID</dt>
              <dd>{selectedAppeal.independent_reviewer_id}</dd>

              <dt>Status</dt>
              <dd>{selectedAppeal.appeal_status}</dd>

              <dt>Submitted</dt>
              <dd>{selectedAppeal.submitted_at
                ? new Date(selectedAppeal.submitted_at).toLocaleString()
                : 'Not available'}</dd>

              <dt>Appeal reason</dt>
              <dd>{selectedAppeal.appeal_reason}</dd>

              <dt>Review outcome</dt>
              <dd>{selectedAppeal.review_outcome || 'Not yet reviewed'}</dd>
            </dl>

            {selectedAppeal.appeal_status === 'UNDER_INDEPENDENT_REVIEW' ? (
              <form onSubmit={submitReview} className="review-form">
                <label htmlFor="review-outcome">Review outcome</label>
                <select
                  id="review-outcome"
                  value={outcome}
                  onChange={(event) => setOutcome(event.target.value)}
                >
                  <option value="UPHELD">Upheld — retain the original decision</option>
                  <option value="OVERTURNED">Overturned — reverse the original decision</option>
                </select>

                <p>
                  Check the evidence and appeal reason before submitting.
                  Submission closes the appeal and updates the case status
                  according to the existing backend workflow.
                </p>

                <button type="submit" disabled={submitting}>
                  {submitting ? 'Submitting…' : 'Submit review outcome'}
                </button>
              </form>
            ) : (
              <p>This appeal is no longer awaiting independent review.</p>
            )}
          </section>
        )}
      </section>
    </main>
  );
}
