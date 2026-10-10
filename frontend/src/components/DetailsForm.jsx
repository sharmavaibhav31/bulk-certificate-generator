import React from 'react';

export default function DetailsForm({
  title,
  setTitle,
  organizationName,
  setOrganizationName,
  issuedDate,
  setIssuedDate,
}) {
  return (
    <div className="card">
      <h2 className="card-title">📝 3. Certificate Details</h2>
      <p className="card-subtitle">
        Enter the course or event details that will be rendered across all recipient certificates.
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

      <div className="form-group" style={{ maxWidth: '300px' }}>
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
    </div>
  );
}
