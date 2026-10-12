import React, { useState, useEffect } from 'react';
import { fetchTemplates, getTemplatePreviewUrl } from '../api';
import CustomTemplateModal from './CustomTemplateModal';

export default function TemplatePicker({
  selectedTemplateId,
  setSelectedTemplateId,
  selectedTemplate,
  setSelectedTemplate,
}) {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);

  const loadTemplates = async () => {
    setLoading(true);
    try {
      const data = await fetchTemplates();
      setTemplates(data);
      if (data.length > 0) {
        if (!selectedTemplateId) {
          setSelectedTemplateId(data[0].id);
          if (setSelectedTemplate) setSelectedTemplate(data[0]);
        } else {
          const current = data.find((t) => t.id === selectedTemplateId);
          if (current && setSelectedTemplate) setSelectedTemplate(current);
        }
      }
    } catch (err) {
      setErrorMsg(`Failed to load templates: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTemplates();
  }, []);

  const handleSelect = (tpl) => {
    setSelectedTemplateId(tpl.id);
    if (setSelectedTemplate) setSelectedTemplate(tpl);
  };

  const handleCustomCreated = (newTemplate) => {
    setTemplates((prev) => [newTemplate, ...prev]);
    setSelectedTemplateId(newTemplate.id);
    if (setSelectedTemplate) setSelectedTemplate(newTemplate);
  };

  return (
    <div className="card">
      <h2 className="card-title">🎨 2. Choose Certificate Template</h2>
      <p className="card-subtitle">
        Select one of 5 built-in professional styles or upload your own finished certificate design.
      </p>

      {errorMsg && <div className="alert-box alert-danger">{errorMsg}</div>}

      {loading ? (
        <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          Loading available templates...
        </div>
      ) : (
        <div className="templates-grid">
          {templates.map((tpl) => {
            const isSelected = selectedTemplateId === tpl.id;
            return (
              <div
                key={tpl.id}
                className={`template-card ${isSelected ? 'selected' : ''}`}
                onClick={() => handleSelect(tpl)}
              >
                <div className="template-preview-box">
                  <img
                    src={`${getTemplatePreviewUrl(tpl.id)}?name=Sample+Recipient`}
                    alt={`Preview ${tpl.name}`}
                    className="template-preview-frame"
                    style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                    loading="lazy"
                  />
                </div>
                <div className="template-info">
                  <div>
                    <div className="template-title">{tpl.name}</div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {tpl.kind === 'builtin' ? 'Built-in style' : 'Custom upload'}
                    </span>
                  </div>
                  <input
                    type="radio"
                    name="templateSelection"
                    checked={isSelected}
                    onChange={() => handleSelect(tpl)}
                    style={{ cursor: 'pointer' }}
                  />
                </div>
              </div>
            );
          })}

          {/* Upload Custom Card */}
          <div className="upload-card" onClick={() => setIsModalOpen(true)}>
            <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>➕</div>
            <div style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--primary)' }}>
              Upload your own template
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
              Add a finished certificate image &amp; position the name
            </div>
          </div>
        </div>
      )}

      <CustomTemplateModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onCreated={handleCustomCreated}
      />
    </div>
  );
}
