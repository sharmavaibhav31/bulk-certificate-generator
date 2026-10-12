import React from 'react';

export default function DetailsForm({
  title,
  setTitle,
  organizationName,
  setOrganizationName,
  issuedDate,
  setIssuedDate,
  outputFormat = 'pdf',
  setOutputFormat,
  isCustom = false,
}) {
  const currentExt = (outputFormat || 'pdf').toLowerCase();

  return (
    <div className="card">
      <h2 className="card-title">📝 3. Certificate Details &amp; Output Format</h2>
      <p className="card-subtitle">
        {isCustom
          ? 'Configure the export format and download options for your custom template.'
          : 'Enter course details and select your desired certificate export format.'}
      </p>

      {isCustom ? (
        <div
          style={{
            background: '#eff6ff',
            border: '1px solid #bfdbfe',
            color: '#1e40af',
            padding: '0.85rem 1rem',
            borderRadius: 'var(--radius-md)',
            marginBottom: '1.5rem',
            fontSize: '0.9rem',
          }}
        >
          🎨 <strong>Custom Template Selected:</strong> Title, issue date, and organization branding are already flattened into your uploaded certificate image. Only the recipient's name is rendered dynamically.
        </div>
      ) : (
        <>
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

          <div style={{ maxWidth: '350px', marginBottom: '1.5rem' }}>
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
          </div>
        </>
      )}

      {/* Output Format Radio Group */}
      <div className="form-group" style={{ marginBottom: '1rem' }}>
        <label className="form-label">Export Output Format</label>
        <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', marginTop: '0.5rem' }}>
          {[
            { id: 'pdf', label: 'PDF Document', ext: '.pdf', desc: 'Standard 300 DPI Document' },
            { id: 'png', label: 'PNG Image', ext: '.png', desc: 'Lossless High-Resolution' },
            { id: 'jpg', label: 'JPG Image', ext: '.jpg', desc: 'Compressed High-Quality (92)' },
          ].map((fmt) => {
            const isChecked = outputFormat.toLowerCase() === fmt.id;
            return (
              <label
                key={fmt.id}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '0.65rem',
                  padding: '0.75rem 1rem',
                  borderRadius: 'var(--radius-md)',
                  border: isChecked ? '2px solid var(--primary)' : '1px solid var(--border-color)',
                  backgroundColor: isChecked ? 'var(--primary-light)' : '#ffffff',
                  cursor: 'pointer',
                  minWidth: '200px',
                }}
              >
                <input
                  type="radio"
                  name="outputFormatRadio"
                  value={fmt.id}
                  checked={isChecked}
                  onChange={() => setOutputFormat(fmt.id)}
                  style={{ marginTop: '0.2rem', cursor: 'pointer' }}
                />
                <div>
                  <div style={{ fontWeight: 700, fontSize: '0.925rem', color: 'var(--text-main)' }}>
                    {fmt.label} <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>({fmt.ext})</span>
                  </div>
                  <div style={{ fontSize: '0.775rem', color: 'var(--text-muted)' }}>{fmt.desc}</div>
                </div>
              </label>
            );
          })}
        </div>
      </div>

      {/* Filename Note */}
      <div
        style={{
          marginTop: '1.25rem',
          padding: '0.75rem 1rem',
          background: '#f8fafc',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-color)',
          fontSize: '0.875rem',
          color: '#334155',
        }}
      >
        📄 <strong>File Naming Rule:</strong> Files will be named after each recipient, for example{' '}
        <code style={{ background: '#e2e8f0', padding: '0.15rem 0.4rem', borderRadius: '4px', fontWeight: 600 }}>
          Tanisha C Kotian.{currentExt}
        </code>
        . Duplicate names are safely deduplicated (e.g.{' '}
        <code style={{ background: '#e2e8f0', padding: '0.15rem 0.4rem', borderRadius: '4px', fontWeight: 600 }}>
          Tanisha C Kotian (2).{currentExt}
        </code>
        ).
      </div>
    </div>
  );
}
