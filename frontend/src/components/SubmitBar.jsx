import React, { useState } from 'react';
import { createJob } from '../api';

export default function SubmitBar({
  title,
  organizationName,
  issuedDate,
  selectedTemplateId,
  recipients,
  onJobStarted,
}) {
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const isFormValid =
    title.trim().length > 0 &&
    Boolean(selectedTemplateId) &&
    recipients.length > 0 &&
    Boolean(issuedDate);

  const handleSubmit = async () => {
    if (!isFormValid || submitting) return;

    setSubmitting(true);
    setErrorMsg('');

    try {
      const payload = {
        title: title.trim(),
        organization_name: organizationName.trim() || null,
        issued_date: issuedDate,
        template_id: selectedTemplateId,
        recipients: recipients.map((r) => ({
          name: r.name,
          email: r.email,
        })),
      };

      const res = await createJob(payload);
      onJobStarted(res.id);
    } catch (err) {
      setErrorMsg(err.message || 'Failed to submit bulk certificate job.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      {errorMsg && (
        <div className="alert-box alert-danger" style={{ marginBottom: '1rem' }}>
          {errorMsg}
        </div>
      )}

      <div className="submit-bar">
        <div>
          <div style={{ fontWeight: 700, fontSize: '1.05rem', color: 'var(--text-main)' }}>
            Ready to Generate
          </div>
          <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
            {recipients.length} recipient{recipients.length === 1 ? '' : 's'} queued
            {!selectedTemplateId && ' • Select a template'}
            {!title && ' • Enter a course title'}
          </div>
        </div>

        <button
          type="button"
          className="submit-btn"
          disabled={!isFormValid || submitting}
          onClick={handleSubmit}
        >
          {submitting ? (
            <>⏳ Dispatching Job...</>
          ) : (
            <>🚀 Generate {recipients.length} Certificate{recipients.length === 1 ? '' : 's'}</>
          )}
        </button>
      </div>
    </div>
  );
}
