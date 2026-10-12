import React, { useState, useRef, useEffect } from 'react';
import { uploadCustomTemplate, fetchDraftPreview } from '../api';

const FONT_OPTIONS = [
  { key: 'dejavu_sans', label: 'DejaVu Sans (Modern / Clean)' },
  { key: 'dejavu_serif', label: 'DejaVu Serif (Traditional / Formal)' },
  { key: 'liberation_sans', label: 'Liberation Sans (Neutral / Crisp)' },
  { key: 'liberation_serif', label: 'Liberation Serif (Classic / Elegant)' },
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

  const [sampleName, setSampleName] = useState('Tanisha C Kotian');
  const [sampleRenderUrl, setSampleRenderUrl] = useState('');
  const [renderingSample, setRenderingSample] = useState(false);

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const imageContainerRef = useRef(null);
  const isDraggingRef = useRef(false);

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isDraggingRef.current || !imageContainerRef.current) return;
      const rect = imageContainerRef.current.getBoundingClientRect();
      const xPct = Math.max(0, Math.min(100, ((e.clientX - rect.left) / rect.width) * 100));
      const yPct = Math.max(0, Math.min(100, ((e.clientY - rect.top) / rect.height) * 100));
      setNameX(parseFloat(xPct.toFixed(1)));
      setNameY(parseFloat(yPct.toFixed(1)));
    };

    const handleMouseUp = () => {
      isDraggingRef.current = false;
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

  if (!isOpen) return null;

  const handleFileChange = (e) => {
    const selected = e.target.files?.[0];
    if (!selected) return;

    if (!['image/png', 'image/jpeg'].includes(selected.type)) {
      setErrorMsg('Only PNG and JPEG image formats are supported.');
      return;
    }

    if (selected.size > 10 * 1024 * 1024) {
      setErrorMsg('Image size cannot exceed 10 MB.');
      return;
    }

    setFile(selected);
    setErrorMsg('');
    setSampleRenderUrl('');
    const objUrl = URL.createObjectURL(selected);
    setPreviewUrl(objUrl);
  };

  const handleMouseDownOnCanvas = (e) => {
    if (!imageContainerRef.current) return;
    isDraggingRef.current = true;
    const rect = imageContainerRef.current.getBoundingClientRect();
    const xPct = Math.max(0, Math.min(100, ((e.clientX - rect.left) / rect.width) * 100));
    const yPct = Math.max(0, Math.min(100, ((e.clientY - rect.top) / rect.height) * 100));
    setNameX(parseFloat(xPct.toFixed(1)));
    setNameY(parseFloat(yPct.toFixed(1)));
  };

  const handleTestSample = async () => {
    if (!file) {
      setErrorMsg('Please upload a certificate background image first.');
      return;
    }

    setRenderingSample(true);
    setErrorMsg('');

    try {
      const formData = new FormData();
      formData.append('image', file);
      formData.append('name_x', nameX);
      formData.append('name_y', nameY);
      formData.append('font', font);
      formData.append('font_size_pct', fontSizePct);
      formData.append('color', color);
      formData.append('max_width_pct', maxWidthPct);
      formData.append('sample_name', sampleName || 'Tanisha C Kotian');

      const renderedBlobUrl = await fetchDraftPreview(formData);
      setSampleRenderUrl(renderedBlobUrl);
    } catch (err) {
      setErrorMsg(`Preview rendering failed: ${err.message}`);
    } finally {
      setRenderingSample(false);
    }
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
      <div className="modal-content" style={{ maxWidth: '820px', maxHeight: '90vh', overflowY: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
          <div>
            <h2 style={{ fontSize: '1.35rem', fontWeight: 800 }}>🎨 Custom Template Studio</h2>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Upload your finished certificate artwork and drag the name marker into position.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{ background: 'none', border: 'none', fontSize: '1.5rem', cursor: 'pointer', color: 'var(--text-muted)' }}
          >
            ✕
          </button>
        </div>

        {errorMsg && <div className="alert-box alert-danger">{errorMsg}</div>}

        <form onSubmit={handleSubmit}>
          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">Template Display Name <span style={{ color: 'var(--danger)' }}>*</span></label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Annual Summit Award"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Certificate Background Image <span style={{ color: 'var(--danger)' }}>*</span></label>
              <input
                type="file"
                accept="image/png, image/jpeg"
                onChange={handleFileChange}
                className="form-input"
                required={!file}
              />
              <small style={{ color: 'var(--text-muted)' }}>PNG or JPEG up to 10 MB. Native resolution preserved.</small>
            </div>
          </div>

          {/* Interactive Full-Width Canvas Preview with Draggable Marker */}
          {previewUrl && (
            <div style={{ marginBottom: '1.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <label className="form-label" style={{ margin: 0 }}>
                  📍 Click or drag on the certificate to position the Recipient Name:
                </label>
                <span style={{ fontSize: '0.8rem', color: 'var(--primary)', fontWeight: 600 }}>
                  X: {nameX}% • Y: {nameY}%
                </span>
              </div>

              <div
                ref={imageContainerRef}
                style={{
                  position: 'relative',
                  width: '100%',
                  cursor: 'crosshair',
                  userSelect: 'none',
                  borderRadius: 'var(--radius-md)',
                  overflow: 'hidden',
                  border: '2px solid var(--border-color)',
                  boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.05)',
                  backgroundColor: '#f1f5f9',
                }}
                onMouseDown={handleMouseDownOnCanvas}
              >
                <img
                  src={previewUrl}
                  alt="Template background"
                  style={{ width: '100%', height: 'auto', display: 'block' }}
                  draggable={false}
                />

                {/* Draggable Marker */}
                <div
                  style={{
                    position: 'absolute',
                    left: `${nameX}%`,
                    top: `${nameY}%`,
                    transform: 'translate(-50%, -50%)',
                    backgroundColor: color || '#1A202C',
                    color: '#ffffff',
                    padding: '6px 14px',
                    borderRadius: '6px',
                    fontSize: '0.85rem',
                    fontWeight: 700,
                    cursor: 'grab',
                    boxShadow: '0 4px 14px rgba(0,0,0,0.4)',
                    border: '2px solid #ffffff',
                    whiteSpace: 'nowrap',
                    userSelect: 'none',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                  onMouseDown={(e) => {
                    e.stopPropagation();
                    isDraggingRef.current = true;
                  }}
                >
                  <span>🎯</span>
                  <span>Recipient Name</span>
                </div>
              </div>
            </div>
          )}

          {/* Typography & Layout Tuning Controls */}
          <div className="grid-2" style={{ marginBottom: '1rem' }}>
            <div className="form-group">
              <label className="form-label">Font Family</label>
              <select className="form-input" value={font} onChange={(e) => setFont(e.target.value)}>
                {FONT_OPTIONS.map((f) => (
                  <option key={f.key} value={f.key}>
                    {f.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Font Color</label>
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <input
                  type="color"
                  value={color}
                  onChange={(e) => setColor(e.target.value)}
                  style={{ width: '42px', height: '42px', padding: 0, border: 'none', borderRadius: '6px', cursor: 'pointer' }}
                />
                <input
                  type="text"
                  className="form-input"
                  value={color}
                  onChange={(e) => setColor(e.target.value)}
                  placeholder="#1A202C"
                />
              </div>
            </div>
          </div>

          <div className="grid-2" style={{ marginBottom: '1rem' }}>
            <div className="form-group">
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <label className="form-label">Font Size</label>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>{fontSizePct}% of height</span>
              </div>
              <input
                type="range"
                min="1.0"
                max="15.0"
                step="0.1"
                value={fontSizePct}
                onChange={(e) => setFontSizePct(parseFloat(e.target.value))}
                style={{ width: '100%' }}
              />
            </div>

            <div className="form-group">
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <label className="form-label">Max Width Limit</label>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>{maxWidthPct}% of width</span>
              </div>
              <input
                type="range"
                min="20.0"
                max="95.0"
                step="1.0"
                value={maxWidthPct}
                onChange={(e) => setMaxWidthPct(parseFloat(e.target.value))}
                style={{ width: '100%' }}
              />
            </div>
          </div>

          {/* Test With Sample Name Section */}
          {file && (
            <div style={{ background: '#f8fafc', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)', marginBottom: '1.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <span style={{ fontWeight: 700, fontSize: '0.9rem' }}>🧪 Live Server Render Test</span>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <input
                  type="text"
                  className="form-input"
                  style={{ flex: 1 }}
                  placeholder="Sample Recipient Name"
                  value={sampleName}
                  onChange={(e) => setSampleName(e.target.value)}
                />
                <button
                  type="button"
                  className="action-btn"
                  onClick={handleTestSample}
                  disabled={renderingSample}
                >
                  {renderingSample ? '⏳ Rendering...' : 'Test with sample name'}
                </button>
              </div>

              {sampleRenderUrl && (
                <div style={{ marginTop: '0.75rem', textAlign: 'center' }}>
                  <p style={{ fontSize: '0.8rem', color: 'var(--success)', fontWeight: 600, marginBottom: '0.25rem' }}>
                    ✓ Pixel-exact server render:
                  </p>
                  <img
                    src={sampleRenderUrl}
                    alt="Sample Preview"
                    style={{ maxWidth: '100%', maxHeight: '280px', borderRadius: '6px', border: '1px solid var(--border-color)' }}
                  />
                </div>
              )}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <button type="button" className="action-btn" style={{ background: '#f1f5f9', color: '#475569' }} onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="submit-btn" style={{ padding: '0.65rem 1.5rem' }} disabled={loading || !file}>
              {loading ? 'Saving Template...' : 'Save & Select Template'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
