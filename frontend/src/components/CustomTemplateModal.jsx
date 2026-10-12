import React, { useState } from 'react';
import { uploadCustomTemplate } from '../api';

const FONT_OPTIONS = [
  { key: 'dejavu_sans', label: 'DejaVu Sans (Modern / Clean)' },
  { key: 'dejavu_serif', label: 'DejaVu Serif (Traditional / Elegant)' },
  { key: 'liberation_sans', label: 'Liberation Sans (Neutral / Crisp)' },
  { key: 'liberation_serif', label: 'Liberation Serif (Classic / Formal)' },
];

export default function CustomTemplateModal({ isOpen, onClose, onCreated }) {
  const [name, setName] = useState('');
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [nameX, setNameX] = useState(50.0);
  const [nameY, setNameY] = useState(57.0);
  const [font, setFont] = useState('dejavu_sans');
  const [fontSizePct, setFontSizePct] = useState(5.0);
  const [color, setColor] = useState('#1A202C');
  const [maxWidthPct, setMaxWidthPct] = useState(70.0);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  if (!isOpen) return null;

  const handleFileChange = (e) => {
    const selected = e.target.files?.[0];
    if (!selected) return;

    if (!['image/png', 'image/jpeg'].includes(selected.type)) {
      setErrorMsg('Only PNG and JPEG formats are supported.');
      return;
    }

    if (selected.size > 10 * 1024 * 1024) {
      setErrorMsg('Image size cannot exceed 10 MB.');
      return;
    }

    setFile(selected);
    setErrorMsg('');
    const objUrl = URL.createObjectURL(selected);
    setPreviewUrl(objUrl);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) {
      setErrorMsg('Please enter a template name.');
      return;
    }
    if (!file) {
      setErrorMsg('Please select a certificate background image.');
      return;
    }

    setLoading(true);
    setErrorMsg('');

    try {
      const formData = new FormData();
      formData.append('name', name.trim());
      formData.append('image', file);
      formData.append('name_x', nameX);
      formData.append('name_y', nameY);
      formData.append('font', font);
      formData.append('font_size_pct', fontSizePct);
      formData.append('color', color);
      formData.append('max_width_pct', maxWidthPct);

      const createdTemplate = await uploadCustomTemplate(formData);
      onCreated(createdTemplate);
      onClose();
    } catch (err) {
      setErrorMsg(err.message || 'Failed to upload template.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: '680px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <h2 style={{ fontSize: '1.35rem', fontWeight: 800 }}>🎨 Custom Template Studio</h2>
          <button
            type="button"
            onClick={onClose}
            style={{ background: 'none', border: 'none', fontSize: '1.5rem', cursor: 'pointer' }}
          >
            ✕
          </button>
        </div>

        {errorMsg && <div className="alert-box alert-danger">{errorMsg}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Template Display Name</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g. Annual Summit Branded Certificate"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Background Image (PNG / JPEG, &le; 10 MB, any dimensions)</label>
            <input
              type="file"
              accept="image/png, image/jpeg"
              onChange={handleFileChange}
              className="form-input"
              required
            />
            <small style={{ color: 'var(--text-muted)', display: 'block', marginTop: '0.25rem' }}>
              Upload your complete certificate artwork with an open area for the recipient name.
            </small>
          </div>

          {previewUrl && (
            <div>
              <label className="form-label">Visual Name Overlay Preview</label>
              <div
                className="custom-canvas-container"
                style={{
                  position: 'relative',
                  overflow: 'hidden',
                  borderRadius: '8px',
                  border: '1px solid var(--border-color, #e2e8f0)',
                  background: '#f8fafc',
                }}
              >
                <img
                  src={previewUrl}
                  alt="Background preview"
                  style={{ width: '100%', display: 'block', maxHeight: '340px', objectFit: 'contain' }}
                />
                <div
                  style={{
                    position: 'absolute',
                    left: `${nameX}%`,
                    top: `${nameY}%`,
                    transform: 'translate(-50%, -50%)',
                    color: color,
                    fontFamily: font.includes('serif') ? 'serif' : 'sans-serif',
                    fontSize: `${Math.max(12, fontSizePct * 3.5)}px`,
                    fontWeight: 700,
                    maxWidth: `${maxWidthPct}%`,
                    textAlign: 'center',
                    whiteSpace: 'nowrap',
                    textOverflow: 'ellipsis',
                    overflow: 'hidden',
                    pointerEvents: 'none',
                    userSelect: 'none',
                    textShadow: '0 0 2px rgba(255,255,255,0.8)',
                  }}
                >
                  Jane Doe
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginTop: '1rem' }}>
                <div className="slider-group">
                  <label style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Horizontal Center (X)</span>
                    <strong>{nameX}%</strong>
                  </label>
                  <input
                    type="range"
                    min="10"
                    max="90"
                    step="0.5"
                    value={nameX}
                    onChange={(e) => setNameX(parseFloat(e.target.value))}
                    style={{ width: '100%' }}
                  />
                </div>

                <div className="slider-group">
                  <label style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Vertical Position (Y)</span>
                    <strong>{nameY}%</strong>
                  </label>
                  <input
                    type="range"
                    min="10"
                    max="90"
                    step="0.5"
                    value={nameY}
                    onChange={(e) => setNameY(parseFloat(e.target.value))}
                    style={{ width: '100%' }}
                  />
                </div>

                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label" style={{ fontSize: '0.85rem' }}>Font Family</label>
                  <select
                    className="form-input"
                    value={font}
                    onChange={(e) => setFont(e.target.value)}
                  >
                    {FONT_OPTIONS.map((opt) => (
                      <option key={opt.key} value={opt.key}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label" style={{ fontSize: '0.85rem' }}>Name Color</label>
                  <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    <input
                      type="color"
                      value={color}
                      onChange={(e) => setColor(e.target.value)}
                      style={{ width: '40px', height: '38px', padding: 0, border: 'none', cursor: 'pointer' }}
                    />
                    <input
                      type="text"
                      className="form-input"
                      value={color}
                      onChange={(e) => setColor(e.target.value)}
                      style={{ fontFamily: 'monospace' }}
                    />
                  </div>
                </div>

                <div className="slider-group">
                  <label style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Font Size (% of height)</span>
                    <strong>{fontSizePct}%</strong>
                  </label>
                  <input
                    type="range"
                    min="1.0"
                    max="15.0"
                    step="0.2"
                    value={fontSizePct}
                    onChange={(e) => setFontSizePct(parseFloat(e.target.value))}
                    style={{ width: '100%' }}
                  />
                </div>

                <div className="slider-group">
                  <label style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Max Width (% of width)</span>
                    <strong>{maxWidthPct}%</strong>
                  </label>
                  <input
                    type="range"
                    min="30"
                    max="95"
                    step="1"
                    value={maxWidthPct}
                    onChange={(e) => setMaxWidthPct(parseFloat(e.target.value))}
                    style={{ width: '100%' }}
                  />
                </div>
              </div>
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1.5rem' }}>
            <button
              type="button"
              className="tab-btn"
              onClick={onClose}
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="submit-btn"
              disabled={loading || !file}
            >
              {loading ? 'Uploading & Processing...' : 'Save & Select Template'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
