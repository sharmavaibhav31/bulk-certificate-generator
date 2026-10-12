import React, { useState } from 'react';
import { createJob } from '../api';

export default function SubmitBar({
  title,
  organizationName,
  issuedDate,
  selectedTemplateId,
  outputFormat = 'pdf',
  recipients,
  onJobStarted,
}) {
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const isFormValid =
    Boolean(selectedTemplateId) &&
    recipients.length > 0;

  const handleSubmit = async () => {
    if (!isFormValid || submitting) return;

    setSubmitting(true);
    setErrorMsg('');

    try {
      const payload = {
        title: title ? title.trim() : null,
        organization_name: organizationName ? organizationName.trim() : null,
        issued_date: issuedDate || null,
        output_format: outputFormat || 'pdf',
        template_id: selectedTemplateId,
        recipients: recipients.map((r) => ({
          name: r.name,
          email: r.email || null,
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
            {recipients.length} recipient{recipients.length === 1 ? '' : 's'} queued • Format: {outputFormat.toUpperCase()}
            {!selectedTemplateId && ' • Select a template'}
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
            <>🚀 Generate {recipients.length} Certificate{recipients.length === 1 ? '' : 's'} ({outputFormat.toUpperCase()})</>
          )}
        </button>
      </div>
    </div>
  );
}
