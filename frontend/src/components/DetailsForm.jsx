import React from 'react';

export default function DetailsForm({
  title,
  setTitle,
  organizationName,
  setOrganizationName,
  issuedDate,
  setIssuedDate,
  outputFormat,
  setOutputFormat,
}) {
  return (
    <div className="card">
      <h2 className="card-title">📝 3. Certificate Details &amp; Output Format</h2>
      <p className="card-subtitle">
        Enter the event details and select the certificate export format.
      </p>

      <div className="grid-2">
        <div className="form-group">
          <label className="form-label">
            Course / Certificate Title <span style={{ color: 'var(--danger)' }}>*</span>
          </label>
          <input
            type="text"
            className="form-input"
            placeholder="e.g. Full-Stack Web Development Bootcamp"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
          />
        </div>

        <div className="form-group">
          <label className="form-label">Issuing Organization / Institution (Optional)</label>
          <input
            type="text"
            className="form-input"
            placeholder="e.g. Acme Tech Institute"
            value={organizationName}
            onChange={(e) => setOrganizationName(e.target.value)}
          />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', maxWidth: '600px' }}>
        <div className="form-group">
          <label className="form-label">
            Issue Date <span style={{ color: 'var(--danger)' }}>*</span>
          </label>
          <input
            type="date"
            className="form-input"
            value={issuedDate}
            onChange={(e) => setIssuedDate(e.target.value)}
            required
          />
        </div>

        <div className="form-group">
          <label className="form-label">Output Format</label>
          <select
            className="form-input"
            value={outputFormat}
            onChange={(e) => setOutputFormat(e.target.value)}
          >
            <option value="pdf">PDF Document (.pdf)</option>
            <option value="png">Lossless Image (.png)</option>
            <option value="jpg">High Quality Image (.jpg)</option>
          </select>
        </div>
      </div>
    </div>
  );
}
