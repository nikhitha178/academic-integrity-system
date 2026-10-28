import { useCallback, useEffect, useState } from 'react';
import { apiRequest } from './api/client';
import './App.css';
import EvidencePanel from './EvidencePanel';
import ReviewerWorkspace from './ReviewerWorkspace';
import IndependentAppealWorkspace from './IndependentAppealWorkspace';
const STATUSES = [
  { value: '', label: 'All statuses' },
  { value: 'UNDER_INVESTIGATION', label: 'Under investigation' },
  { value: 'DECIDED', label: 'Decided' },
  { value: 'APPEALED', label: 'Appealed' },
  { value: 'CLOSED', label: 'Closed' },
];

function readableStatus(status = '') {
  return status.replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
}

function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const roles = [
    {
      value: 'Academic Administrator',
      label: 'Academic Administrator',
      description: 'Manage cases and reviewer assignments',
      icon: '🛡️',
    },
    {
      value: 'Case Reviewer',
      label: 'Case Reviewer',
      description: 'Review assigned cases and evidence',
      icon: '📋',
    },
    {
      value: 'Independent Appeal Reviewer',
      label: 'Independent Appeal Reviewer',
      description: 'Review appeals independently',
      icon: '⚖️',
    },
  ];

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');

    if (!role) {
      setError('Please select your account type.');
      return;
    }

    setBusy(true);

    try {
      const result = await apiRequest('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      });

      if (!result.access_token) {
        throw new Error('The server did not return an access token.');
      }

      onLogin(result.access_token, role);
    } catch (err) {
      setError(err.message || 'Login failed. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-layout">
      <section className="login-intro">
        <div className="brand-mark">AI</div>
        <p className="eyebrow">ACADEMIC INTEGRITY</p>
        <h1>Case Management System</h1>

        <p className="intro-copy">
          A centralized workspace for managing academic integrity cases
          and supporting a fair, transparent, and accountable review process.
        </p>

        <div className="login-note">
          <span className="status-dot" />
          Secure, role-based access
        </div>
      </section>

      <section className="login-panel">
        <div className="panel-heading">
          <p className="eyebrow">WELCOME BACK</p>
          <h2>Sign in to your workspace</h2>
          <p>Select your account type and enter your system credentials.</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <fieldset className="role-fieldset">
            <legend>Which workspace do you use?</legend>

            <div className="role-options">
              {roles.map(item => (
                <label
                  key={item.value}
                  className={`role-option ${role === item.value ? 'role-option-selected' : ''
                    }`}
                >
                  <input
                    type="radio"
                    name="accountRole"
                    value={item.value}
                    checked={role === item.value}
                    onChange={() => setRole(item.value)}
                    required
                  />

                  <span className="role-option-icon" aria-hidden="true">
                    {item.icon}
                  </span>

                  <span className="role-option-content">
                    <strong>{item.label}</strong>
                    <span>{item.description}</span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          <label htmlFor="username">Username</label>
          <input
            id="username"
            name="username"
            autoComplete="username"
            value={username}
            onChange={event => setUsername(event.target.value)}
            placeholder="Enter your username"
            required
          />

          <label htmlFor="password">Password</label>

          <div className="password-field">
            <input
              id="password"
              name="password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              value={password}
              onChange={event => setPassword(event.target.value)}
              placeholder="Enter your password"
              required
            />

            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowPassword(value => !value)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
            >
              {showPassword ? 'Hide' : 'Show'}
            </button>
          </div>

          {error && (
            <div className="alert alert-error" role="alert">
              {error}
            </div>
          )}

          <button
            type="submit"
            className="primary-button login-button"
            disabled={busy}
          >
            {busy ? 'Signing in…' : 'Sign in securely'}
            {!busy && <span aria-hidden="true"> →</span>}
          </button>
        </form>

        <p className="login-footnote">
          Your account permissions are verified securely by the system.
          Selecting a workspace does not change your assigned role.
        </p>
      </section>
    </main>
  );
}

function Dashboard({ token, user, onLogout }) {
  const [cases, setCases] = useState([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const [reviewers, setReviewers] = useState([]);
  const [selectedCase, setSelectedCase] = useState('');
  const [selectedReviewer, setSelectedReviewer] = useState('');
  const [activeAssignments, setActiveAssignments] = useState([]);
  const [reviewerLoading, setReviewerLoading] = useState(false);
  const [assignmentLoading, setAssignmentLoading] = useState(false);
  const [assigning, setAssigning] = useState(false);
  const [assignmentError, setAssignmentError] = useState('');
  const [assignmentNotice, setAssignmentNotice] = useState('');
  const [appeals, setAppeals] = useState([]);
  const [appealsLoading, setAppealsLoading] = useState(false);
  const [appealsError, setAppealsError] = useState('');
  const [selectedAppealId, setSelectedAppealId] = useState('');
  const loadAppeals = useCallback(async () => {
    setAppealsLoading(true);
    setAppealsError('');

    try {
      const result = await apiRequest('/appeals', {}, token);
      setAppeals(Array.isArray(result) ? result : []);
    } catch (err) {
      setAppealsError(err.message || 'Unable to load appeals.');
      setAppeals([]);
    } finally {
      setAppealsLoading(false);
    }
  }, [token]);

  const loadCases = useCallback(async () => {
    setLoading(true);
    setError('');
    setNotice('');

    try {
      const query = new URLSearchParams({ limit: '100', offset: '0' });
      if (status) query.set('status', status);

      const result = await apiRequest(`/cases?${query.toString()}`, {}, token);
      setCases(result.items || []);
      setTotal(result.total || 0);
    } catch (err) {
      setError(err.message || 'Unable to load cases.');
    } finally {
      setLoading(false);
    }
  }, [status, token]);

  const loadReviewers = useCallback(async () => {
    setReviewerLoading(true);
    setAssignmentError('');

    try {
      const result = await apiRequest('/admin/reviewers', {}, token);
      const items = result.items || [];
      setReviewers(items);

      setSelectedReviewer(current =>
        items.some(item => item.reviewer_id === current)
          ? current
          : ''
      );
    } catch (err) {
      setAssignmentError(err.message || 'Unable to load reviewers.');
    } finally {
      setReviewerLoading(false);
    }
  }, [token]);

  const loadAssignment = useCallback(async (caseId) => {
    if (!caseId) {
      setActiveAssignments([]);
      return;
    }

    setAssignmentLoading(true);
    setAssignmentError('');

    try {
      const result = await apiRequest(
        `/admin/cases/${encodeURIComponent(caseId)}/reviewer-assignment`,
        {},
        token
      );

      const assignments = result.active_assignments || [];
      setActiveAssignments(assignments);

      if (assignments.length > 0) {
        setSelectedReviewer(assignments[0].reviewer_id);
      }
    } catch (err) {
      setAssignmentError(err.message || 'Unable to load the current assignment.');
      setActiveAssignments([]);
    } finally {
      setAssignmentLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadReviewers();
  }, [loadReviewers]);
  useEffect(() => {
    loadAppeals();
  }, [loadAppeals]);

  useEffect(() => {
    if (cases.length === 0) {
      setSelectedCase('');
      setActiveAssignments([]);
      return;
    }

    const caseStillVisible = cases.some(
      item => item.case_id === selectedCase
    );

    if (!caseStillVisible) {
      setSelectedCase(cases[0].case_id);
    }
  }, [cases, selectedCase]);

  useEffect(() => {
    if (selectedCase) {
      loadAssignment(selectedCase);
    } else {
      setActiveAssignments([]);
    }
  }, [selectedCase, loadAssignment]);

  async function handleAssignReviewer() {
    if (!selectedCase || !selectedReviewer) {
      setAssignmentError('Select a case and a reviewer first.');
      return;
    }

    setAssigning(true);
    setAssignmentError('');
    setAssignmentNotice('');

    try {
      await apiRequest(
        `/admin/cases/${encodeURIComponent(selectedCase)}/reviewer-assignment`,
        {
          method: 'POST',
          body: JSON.stringify({ reviewer_id: selectedReviewer }),
        },
        token
      );

      await loadAssignment(selectedCase);
      setAssignmentNotice('Reviewer assignment saved successfully.');
      await loadCases();
    } catch (err) {
      setAssignmentError(err.message || 'Unable to save the reviewer assignment.');
    } finally {
      setAssigning(false);
    }
  }


  useEffect(() => {
    loadCases();
  }, [loadCases]);

  const investigationCount = cases.filter(
    item => item.case_status === 'UNDER_INVESTIGATION'
  ).length;
  const appealedCount = cases.filter(item => item.case_status === 'APPEALED').length;
  const decidedCount = cases.filter(item => item.case_status === 'DECIDED').length;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-mark small-mark">AI</div>
          <div>
            <strong>Integrity Office</strong>
            <span>Case management</span>
          </div>
        </div>

        <div className="nav-label">WORKSPACE</div>
        <div className="nav-item active">
          <span className="nav-icon">▦</span>
          Overview
        </div>
        <div className="nav-item">
          <span className="nav-icon">▤</span>
          Case register
        </div>
        <div className="nav-item">
          <span className="nav-icon">♧</span>
          Reviewer assignments
          <span className="nav-tag">Next</span>
        </div>

        <div className="sidebar-bottom">
          <div className="sidebar-user-icon">
            {(user.username || 'A').slice(0, 1).toUpperCase()}
          </div>
          <div className="sidebar-user">
            <strong>{user.username}</strong>
            <span>Administrator</span>
          </div>
          <button className="logout-button" onClick={onLogout} title="Sign out">
            ↗
          </button>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div className="breadcrumb">Workspace <span>/</span> Overview</div>
          <div className="topbar-right">
            <span className="environment-pill"><span /> Development</span>
            <button className="text-button" onClick={onLogout}>Sign out</button>
          </div>
        </header>

        <div className="dashboard-content">
          <section className="welcome-row">
            <div>
              <p className="eyebrow">ADMINISTRATOR WORKSPACE</p>
              <h1>Case overview</h1>
              <p className="muted">Monitor case activity and review current case statuses.</p>
            </div>
            <button className="secondary-button" onClick={loadCases} disabled={loading}>
              <span aria-hidden="true">↻</span> {loading ? 'Refreshing…' : 'Refresh data'}
            </button>
          </section>

          <section className="metric-grid" aria-label="Case statistics">
            <article className="metric-card">
              <div className="metric-top"><span>Total matching cases</span><span className="metric-icon indigo">▤</span></div>
              <div className="metric-number">{loading ? '—' : total}</div>
              <div className="metric-caption">Cases matching your filter</div>
            </article>
            <article className="metric-card">
              <div className="metric-top"><span>Under investigation</span><span className="metric-icon amber">◷</span></div>
              <div className="metric-number">{loading ? '—' : investigationCount}</div>
              <div className="metric-caption">In the currently loaded results</div>
            </article>
            <article className="metric-card">
              <div className="metric-top"><span>Decided</span><span className="metric-icon green">✓</span></div>
              <div className="metric-number">{loading ? '—' : decidedCount}</div>
              <div className="metric-caption">In the currently loaded results</div>
            </article>
            <article className="metric-card">
              <div className="metric-top"><span>Appealed</span><span className="metric-icon violet">↗</span></div>
              <div className="metric-number">{loading ? '—' : appealedCount}</div>
              <div className="metric-caption">In the currently loaded results</div>
            </article>
          </section>

          <section className="table-card">
            <div className="table-heading">
              <div>
                <h2>Case register</h2>
                <p>Cases returned by the case management API</p>
              </div>
              <label className="filter-control">
                <span>Status</span>
                <select value={status} onChange={event => setStatus(event.target.value)}>
                  {STATUSES.map(item => (
                    <option key={item.value} value={item.value}>{item.label}</option>
                  ))}
                </select>
              </label>
            </div>

            {error && (
              <div className="alert alert-error table-alert" role="alert">
                <strong>Could not load cases.</strong> {error}
                <button className="inline-action" onClick={loadCases}>Try again</button>
              </div>
            )}
            {notice && <div className="alert alert-success">{notice}</div>}

            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Case ID</th>
                    <th>Status</th>
                    <th>Submission ID</th>
                    <th>Created</th>
                    <th>Last updated</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr><td colSpan="5" className="empty-state">Loading case records…</td></tr>
                  ) : error ? (
                    <tr><td colSpan="5" className="empty-state">Check the error message above.</td></tr>
                  ) : cases.length === 0 ? (
                    <tr><td colSpan="5" className="empty-state">No cases found for this status.</td></tr>
                  ) : cases.map(item => (
                    <tr key={item.case_id}>
                      <td><span className="case-id">{item.case_id}</span></td>
                      <td><span className={`status-badge status-${item.case_status.toLowerCase()}`}>
                        <span />{readableStatus(item.case_status)}
                      </span></td>
                      <td className="submission-id">{item.submission_id}</td>
                      <td>{item.created_at ? new Date(item.created_at).toLocaleDateString() : '—'}</td>
                      <td>{item.updated_at ? new Date(item.updated_at).toLocaleDateString() : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="table-footer">
              <span>Showing {cases.length} of {total} matching cases</span>
              <span>Maximum 100 results per request</span>
            </div>
          </section>


          <section className="assignment-preview">
            <div className="assignment-symbol">♧</div>

            <div className="assignment-manager">
              <h2>Reviewer assignment management</h2>
              <p>
                Select a case to view its current reviewer, then assign or
                reassign an active reviewer.
              </p>

              {assignmentError && (
                <div className="alert alert-error" role="alert">
                  {assignmentError}
                </div>
              )}

              {assignmentNotice && (
                <div className="alert alert-success" role="status">
                  {assignmentNotice}
                </div>
              )}

              <div className="assignment-controls">
                <label className="filter-control">
                  <span>Case</span>
                  <select
                    value={selectedCase}
                    onChange={event => {
                      setSelectedCase(event.target.value);
                      setAssignmentNotice('');
                      setAssignmentError('');
                    }}
                    disabled={cases.length === 0 || loading}
                  >
                    {cases.length === 0 && (
                      <option value="">No cases available</option>
                    )}
                    {cases.map(item => (
                      <option key={item.case_id} value={item.case_id}>
                        {item.case_id} — {readableStatus(item.case_status)}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="filter-control">
                  <span>Active reviewer</span>
                  <select
                    value={selectedReviewer}
                    onChange={event => setSelectedReviewer(event.target.value)}
                    disabled={reviewerLoading || reviewers.length === 0}
                  >
                    <option value="">
                      {reviewerLoading
                        ? 'Loading reviewers…'
                        : reviewers.length === 0
                          ? 'No active reviewers available'
                          : 'Select a reviewer'}
                    </option>

                    {reviewers.map(reviewer => (
                      <option key={reviewer.reviewer_id} value={reviewer.reviewer_id}>
                        {reviewer.full_name} — {reviewer.department}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="current-assignment">
                <strong>Current assignment</strong>

                {assignmentLoading ? (
                  <p>Loading assignment details…</p>
                ) : activeAssignments.length > 0 ? (
                  activeAssignments.map(item => (
                    <p key={item.assignment_id}>
                      {item.reviewer_name}
                      {' · '}
                      {item.assignment_role.replaceAll('_', ' ')}
                    </p>
                  ))
                ) : (
                  <p>No active reviewer assignment for this case.</p>
                )}
              </div>

              <div className="assignment-actions">
                <button
                  className="primary-button"
                  onClick={handleAssignReviewer}
                  disabled={
                    assigning ||
                    assignmentLoading ||
                    reviewerLoading ||
                    !selectedCase ||
                    !selectedReviewer ||
                    reviewers.length === 0
                  }
                >
                  {assigning ? 'Saving assignment…' : 'Assign / Reassign Reviewer'}
                </button>

                <button
                  className="secondary-button"
                  onClick={() => {
                    loadReviewers();
                    if (selectedCase) loadAssignment(selectedCase);
                  }}
                  disabled={reviewerLoading || assignmentLoading || assigning}
                >
                  Refresh reviewers
                </button>
              </div>
            </div>
          </section>
          <section className="table-card">
            <div className="table-heading">
              <div>
                <h2>Appeal Management</h2>
                <p>
                  View submitted appeals and track independent review progress.
                </p>
              </div>

              <button
                className="secondary-button"
                onClick={loadAppeals}
                disabled={appealsLoading}
              >
                {appealsLoading ? 'Refreshing…' : 'Refresh appeals'}
              </button>
            </div>

            {appealsError && (
              <div className="alert alert-error" role="alert">
                <strong>Could not load appeals.</strong> {appealsError}
              </div>
            )}

            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Appeal ID</th>
                    <th>Case ID</th>
                    <th>Original decision</th>
                    <th>Independent reviewer</th>
                    <th>Status</th>
                    <th>Outcome</th>
                    <th>Submitted</th>
                  </tr>
                </thead>

                <tbody>
                  {appealsLoading ? (
                    <tr>
                      <td colSpan="7" className="empty-state">
                        Loading appeals…
                      </td>
                    </tr>
                  ) : appealsError ? (
                    <tr>
                      <td colSpan="7" className="empty-state">
                        Check the error message above.
                      </td>
                    </tr>
                  ) : appeals.length === 0 ? (
                    <tr>
                      <td colSpan="7" className="empty-state">
                        No appeals are currently available to your account.
                      </td>
                    </tr>
                  ) : (
                    appeals.map(appeal => (
                      <tr
                        key={appeal.appeal_id}
                        onClick={() => setSelectedAppealId(appeal.appeal_id)}
                        className={selectedAppealId === appeal.appeal_id ? 'selected-appeal-row' : ''}
                        style={{ cursor: 'pointer' }}
                      >
                        <td>
                          <span className="case-id">
                            {appeal.appeal_id}
                          </span>
                        </td>
                        <td>{appeal.case_id}</td>
                        <td>{appeal.decision_id}</td>
                        <td>{appeal.independent_reviewer_id}</td>
                        <td>
                          <span
                            className={`status-badge ${appeal.appeal_status === 'CLOSED'
                              ? 'status-closed'
                              : 'status-appealed'
                              }`}
                          >
                            <span />
                            {readableStatus(appeal.appeal_status)}
                          </span>
                        </td>
                        <td>
                          {appeal.review_outcome
                            ? readableStatus(appeal.review_outcome)
                            : 'Pending'}
                        </td>
                        <td>
                          {appeal.submitted_at
                            ? new Date(appeal.submitted_at).toLocaleDateString()
                            : '—'}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {!appealsLoading && !appealsError && appeals.length > 0 && (
              <div className="table-footer">
                <span>{appeals.length} appeal(s) available</span>
                <span>Review outcomes are recorded by independent reviewers</span>
              </div>
            )}

            {appeals.length > 0 && (
              <div className="appeal-details-panel">
                <h3>Appeal Details</h3>

                {(() => {
                  const selectedAppeal =
                    appeals.find(appeal => appeal.appeal_id === selectedAppealId) ||
                    appeals[0];

                  return (
                    <article className="appeal-detail-card">
                      <div className="detail-list">
                        <div>
                          <strong>Appeal ID</strong>
                          <p>{selectedAppeal.appeal_id}</p>
                        </div>

                        <div>
                          <strong>Case ID</strong>
                          <p>{selectedAppeal.case_id}</p>
                        </div>

                        <div>
                          <strong>Original decision</strong>
                          <p>{selectedAppeal.decision_id}</p>
                        </div>

                        <div>
                          <strong>Independent reviewer</strong>
                          <p>{selectedAppeal.independent_reviewer_id}</p>
                        </div>

                        <div>
                          <strong>Status</strong>
                          <p>{readableStatus(selectedAppeal.appeal_status)}</p>
                        </div>

                        <div>
                          <strong>Review outcome</strong>
                          <p>
                            {selectedAppeal.review_outcome
                              ? readableStatus(selectedAppeal.review_outcome)
                              : 'Pending'}
                          </p>
                        </div>

                        <div>
                          <strong>Submitted</strong>
                          <p>
                            {selectedAppeal.submitted_at
                              ? new Date(selectedAppeal.submitted_at).toLocaleString()
                              : '—'}
                          </p>
                        </div>

                        <div>
                          <strong>Review completed</strong>
                          <p>
                            {selectedAppeal.review_completed_at
                              ? new Date(selectedAppeal.review_completed_at).toLocaleString()
                              : 'Not completed'}
                          </p>
                        </div>
                      </div>

                      <div className="appeal-reason-detail">
                        <strong>Appeal reason</strong>
                        <p>{selectedAppeal.appeal_reason || 'No appeal reason provided.'}</p>
                      </div>
                    </article>
                  );
                })()}
              </div>
            )}
          </section>
          <EvidencePanel
            token={token}
            cases={cases}
            selectedCase={selectedCase}
          />


          <footer className="page-footer">
            <span>Academic Integrity Case Management System</span>
            <span>Signed in as {user.username}</span>
          </footer>
        </div>
      </main>
    </div>
  );
}

function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem('academic_integrity_token'));
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(Boolean(token));
  const [authError, setAuthError] = useState('');

  const logout = useCallback(() => {
    sessionStorage.removeItem('academic_integrity_token');
    sessionStorage.removeItem('academic_integrity_selected_role');
    setToken(null);
    setUser(null);
    setAuthError('');
  }, []);

  useEffect(() => {
    if (!token) {
      setChecking(false);
      return;
    }

    let cancelled = false;

    async function verifyUser() {
      setChecking(true);
      setAuthError('');

      try {
        const currentUser = await apiRequest('/auth/me', {}, token);
        const allowedRoles = [
          'Academic Administrator',
          'Case Reviewer',
          'Independent Appeal Reviewer',
        ];

        if (!allowedRoles.includes(currentUser.role)) {
          throw new Error('This workspace is not available for your account role.');
        }

        const selectedRole = sessionStorage.getItem(
          'academic_integrity_selected_role'
        );

        if (selectedRole && selectedRole !== currentUser.role) {
          throw new Error(
            `You selected ${selectedRole}, but this account is assigned to ${currentUser.role}. Please sign in again and select the correct workspace.`
          );
        }

        if (!cancelled) setUser(currentUser);
      } catch (err) {
        if (!cancelled) {
          sessionStorage.removeItem('academic_integrity_token');
          sessionStorage.removeItem('academic_integrity_selected_role');
          setToken(null);
          setUser(null);
          setAuthError(err.message || 'Your session has expired. Please sign in again.');
        }
      } finally {
        if (!cancelled) setChecking(false);
      }
    }

    verifyUser();
    return () => { cancelled = true; };
  }, [token]);

  function handleLogin(accessToken, selectedRole) {
    sessionStorage.setItem('academic_integrity_token', accessToken);
    sessionStorage.setItem('academic_integrity_selected_role', selectedRole);

    setAuthError('');
    setUser(null);
    setToken(accessToken);
  }
  if (checking) {
    return <main className="loading-screen"><div className="loading-mark">AI</div><p>Verifying administrator session…</p></main>;
  }

  if (!token || !user) {
    return (
      <>
        {authError && <div className="session-message" role="alert">{authError}</div>}
        <Login onLogin={handleLogin} />
      </>
    );
  }

  if (user.role === 'Case Reviewer') {
    return (
      <ReviewerWorkspace
        token={token}
        user={user}
        onLogout={logout}
      />
    );
  }
  if (user.role === 'Independent Appeal Reviewer') {
    return (
      <IndependentAppealWorkspace
        token={token}
        user={user}
        onLogout={logout}
      />
    );
  }

  return <Dashboard token={token} user={user} onLogout={logout} />;
}

export default App;
