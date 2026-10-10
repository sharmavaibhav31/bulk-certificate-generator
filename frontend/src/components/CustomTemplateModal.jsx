import React, { useState } from 'react';
import { uploadCustomTemplate } from '../api';

export default function CustomTemplateModal({ isOpen, onClose, onCreated }) {
  const [name, setName] = useState('');
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [nameY, setNameY] = useState(45.0);
  const [courseY, setCourseY] = useState(60.0);
  const [dateY, setDateY] = useState(75.0);
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

    if (selected.size > 5 * 1024 * 1024) {
      setErrorMsg('Image size cannot exceed 5 MB.');
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
      formData.append('name_y', nameY);
      formData.append('course_y', courseY);
      formData.append('date_y', dateY);

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
      <div className="modal-content">
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
              placeholder="e.g. Annual Summit Certificate"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Background Image (PNG / JPEG, &le; 5 MB, Landscape A4)</label>
            <input
              type="file"
              accept="image/png, image/jpeg"
              onChange={handleFileChange}
              className="form-input"
              required
            />
          </div>

          {previewUrl && (
            <div>
              <label className="form-label">Live Text Positioning Preview</label>
              <div className="custom-canvas-container">
                <img src={previewUrl} alt="Background preview" className="custom-canvas-bg" />
                <div className="overlay-text" style={{ top: `${nameY}%`, fontSize: '1.25rem', color: '#1e293b' }}>
                  Jane Doe (Recipient Name)
                </div>
                <div className="overlay-text" style={{ top: `${courseY}%`, fontSize: '0.95rem', color: '#334155' }}>
                  Full-Stack Architecture Masterclass
                </div>
                <div className="overlay-text" style={{ top: `${dateY}%`, fontSize: '0.8rem', color: '#64748b' }}>
                  Issued Date: 2026-10-10
                </div>
              </div>

              <div className="slider-group">
                <label>
                  <span>Recipient Name Vertical Position (Y)</span>
                  <span>{nameY}%</span>
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

              <div className="slider-group">
                <label>
                  <span>Course Title Vertical Position (Y)</span>
                  <span>{courseY}%</span>
                </label>
                <input
                  type="range"
                  min="15"
                  max="95"
                  step="0.5"
                  value={courseY}
                  onChange={(e) => setCourseY(parseFloat(e.target.value))}
                  style={{ width: '100%' }}
                />
              </div>

              <div className="slider-group">
                <label>
                  <span>Issue Date Vertical Position (Y)</span>
                  <span>{dateY}%</span>
                </label>
                <input
                  type="range"
                  min="20"
                  max="98"
                  step="0.5"
                  value={dateY}
                  onChange={(e) => setDateY(parseFloat(e.target.value))}
                  style={{ width: '100%' }}
                />
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
