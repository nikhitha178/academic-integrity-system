
import { useCallback, useEffect, useState } from 'react';
import { apiRequest } from './api/client';

export default function EvidencePanel({ token, cases, selectedCase }) {
    const [evidence, setEvidence] = useState([]);
    const [evidenceType, setEvidenceType] = useState('Document');
    const [contentSummary, setContentSummary] = useState('');
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');

    const currentCase = cases.find(item => item.case_id === selectedCase);
    const canAddEvidence =
        currentCase?.case_status === 'UNDER_INVESTIGATION';

    const loadEvidence = useCallback(async () => {
        if (!selectedCase) {
            setEvidence([]);
            return;
        }

        setLoading(true);
        setError('');

        try {
            const result = await apiRequest(
                `/cases/${encodeURIComponent(selectedCase)}/evidence`,
                {},
                token
            );

            setEvidence(Array.isArray(result) ? result : []);
        } catch (err) {
            setEvidence([]);
            setError(err.message || 'Unable to load evidence.');
        } finally {
            setLoading(false);
        }
    }, [selectedCase, token]);

    useEffect(() => {
        setNotice('');
        setContentSummary('');
        loadEvidence();
    }, [loadEvidence]);

    async function handleSubmit(event) {
        event.preventDefault();
        setError('');
        setNotice('');

        if (!selectedCase) {
            setError('Select a case first.');
            return;
        }

        if (!canAddEvidence) {
            setError('Evidence can only be added while a case is under investigation.');
            return;
        }

        if (!evidenceType.trim() || !contentSummary.trim()) {
            setError('Enter both an evidence type and a summary.');
            return;
        }

        setSaving(true);

        try {
            await apiRequest(
                `/cases/${encodeURIComponent(selectedCase)}/evidence`,
                {
                    method: 'POST',
                    body: JSON.stringify({
                        evidence_type: evidenceType.trim(),
                        content_summary: contentSummary.trim(),
                    }),
                },
                token
            );

            setContentSummary('');
            setNotice('Evidence added successfully.');
            await loadEvidence();
        } catch (err) {
            setError(err.message || 'Unable to add evidence.');
        } finally {
            setSaving(false);
        }
    }

    return (
        <section className="table-card evidence-panel">
            <div className="table-heading">
                <div>
                    <h2>Evidence management</h2>
                    <p>
                        {selectedCase
                            ? `Evidence records for ${selectedCase}`
                            : 'Select a case to view its evidence.'}
                    </p>
                </div>

                <button
                    type="button"
                    className="secondary-button"
                    onClick={loadEvidence}
                    disabled={!selectedCase || loading || saving}
                >
                    {loading ? 'Refreshing…' : 'Refresh evidence'}
                </button>
            </div>

            {error && (
                <div className="alert alert-error" role="alert">
                    {error}
                </div>
            )}

            {notice && (
                <div className="alert alert-success" role="status">
                    {notice}
                </div>
            )}

            {!selectedCase ? (
                <p className="empty-state">Choose a case in Reviewer assignment management first.</p>
            ) : (
                <>
                    <div className="evidence-list">
                        {loading ? (
                            <p className="empty-state">Loading evidence records…</p>
                        ) : evidence.length === 0 ? (
                            <p className="empty-state">No evidence records found for this case.</p>
                        ) : (
                            evidence.map(item => (
                                <article className="evidence-item" key={item.evidence_id}>
                                    <div className="evidence-item-heading">
                                        <strong>{item.evidence_type}</strong>
                                        <span>Version {item.version}</span>
                                    </div>

                                    <p className="evidence-summary">{item.content_summary}</p>

                                    <dl className="evidence-details">
                                        <div>
                                            <dt>Evidence ID</dt>
                                            <dd>{item.evidence_id}</dd>
                                        </div>
                                        <div>
                                            <dt>Added by</dt>
                                            <dd>{item.added_by_user_id}</dd>
                                        </div>
                                        <div>
                                            <dt>Added on</dt>
                                            <dd>
                                                {item.added_at
                                                    ? new Date(item.added_at).toLocaleString()
                                                    : '—'}
                                            </dd>
                                        </div>
                                        <div>
                                            <dt>SHA-256 checksum</dt>
                                            <dd className="evidence-checksum">
                                                {item.metadata_checksum}
                                            </dd>
                                        </div>
                                    </dl>
                                </article>
                            ))
                        )}
                    </div>

                    <div className="evidence-form-section">
                        <h3>Add evidence</h3>

                        {!canAddEvidence && (
                            <p className="muted">
                                Evidence can only be added while this case is under investigation.
                            </p>
                        )}

                        <form className="evidence-form" onSubmit={handleSubmit}>
                            <label htmlFor="evidence-type">Evidence type</label>
                            <input
                                id="evidence-type"
                                value={evidenceType}
                                onChange={event => setEvidenceType(event.target.value)}
                                maxLength={80}
                                required
                                disabled={!canAddEvidence || saving}
                                placeholder="e.g. Document, Similarity Report"
                            />

                            <label htmlFor="evidence-summary">Content summary</label>
                            <textarea
                                id="evidence-summary"
                                value={contentSummary}
                                onChange={event => setContentSummary(event.target.value)}
                                maxLength={10000}
                                rows={4}
                                required
                                disabled={!canAddEvidence || saving}
                                placeholder="Describe the evidence and its relevance to the case."
                            />

                            <button
                                type="submit"
                                className="primary-button"
                                disabled={!canAddEvidence || saving || loading}
                            >
                                {saving ? 'Saving evidence…' : 'Add evidence'}
                            </button>
                        </form>
                    </div>
                </>
            )}
        </section>
    );
}
