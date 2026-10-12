import React, { useState } from 'react';
import Papa from 'papaparse';
import readXlsxFile from 'read-excel-file';

const EMAIL_REGEX = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;
const NAME_HEADER_REGEX = /^(name|student|student[\s_-]?name|full[\s_-]?name|recipient|recipient[\s_-]?name)$/i;
const EMAIL_HEADER_REGEX = /^(email|mail|e-mail|recipient[\s_-]?email)$/i;

export default function ImportPanel({ recipients, setRecipients }) {
  const [activeTab, setActiveTab] = useState('upload'); // 'upload' | 'paste'
  const [pasteText, setPasteText] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  // Tabular column mapping state (for CSV / XLSX)
  const [tabularData, setTabularData] = useState(null); // { headers: string[], rows: string[][] }
  const [nameColIdx, setNameColIdx] = useState(0);
  const [emailColIdx, setEmailColIdx] = useState(-1);

  // Apply column selection to tabular data and update parent recipients
  const applyColumnMapping = (rows, nIdx, eIdx) => {
    const parsed = [];
    rows.forEach((row) => {
      const name = String(row[nIdx] ?? '').trim();
      const email = eIdx >= 0 ? String(row[eIdx] ?? '').trim() : '';
      if (!name && !email) return; // skip completely empty rows
      parsed.push({ name, email });
    });
    setRecipients(parsed);
  };

  const handleTabularLoaded = (allRows) => {
    if (!allRows || allRows.length === 0) {
      setErrorMsg('Uploaded file contains no data.');
      return;
    }

    // Filter out completely empty rows
    const cleanedRows = allRows.filter((r) =>
      Array.isArray(r) && r.some((c) => c !== null && c !== undefined && String(c).trim() !== '')
    );

    if (cleanedRows.length === 0) {
      setErrorMsg('Uploaded file contains only empty rows.');
      return;
    }

    const firstRow = cleanedRows[0];
    let detectedName = -1;
    let detectedEmail = -1;

    firstRow.forEach((col, idx) => {
      const text = String(col ?? '').trim();
      if (NAME_HEADER_REGEX.test(text)) detectedName = idx;
      if (EMAIL_HEADER_REGEX.test(text)) detectedEmail = idx;
    });

    let headers = [];
    let dataRows = [];
    let initialNameIdx = 0;
    let initialEmailIdx = -1;

    if (detectedName !== -1) {
      // First row is a header
      headers = firstRow.map((c, i) => String(c ?? '').trim() || `Column ${i + 1}`);
      dataRows = cleanedRows.slice(1);
      initialNameIdx = detectedName;
      initialEmailIdx = detectedEmail;
    } else {
      // No recognized header: treat first row as data, name is column 0
      headers = firstRow.map((_, i) => `Column ${i + 1}`);
      dataRows = cleanedRows;
      initialNameIdx = 0;
      initialEmailIdx = -1;
    }

    setTabularData({ headers, rows: dataRows });
    setNameColIdx(initialNameIdx);
    setEmailColIdx(initialEmailIdx);
    applyColumnMapping(dataRows, initialNameIdx, initialEmailIdx);
    setErrorMsg('');
  };

  // TXT line-by-line parsing: supports "Name <email>", "Name, email", or bare name
  const parseTxtLines = (text) => {
    const lines = text.split(/\r?\n/);
    const parsed = [];

    lines.forEach((line) => {
      const trimmed = line.trim();
      if (!trimmed) return;

      // 1. "Name <email@example.com>"
      const angleBracketMatch = trimmed.match(/^([^<]+)<([^>]+)>$/);
      if (angleBracketMatch) {
        parsed.push({
          name: angleBracketMatch[1].trim(),
          email: angleBracketMatch[2].trim(),
        });
        return;
      }

      // 2. "Name, email@example.com"
      const commaParts = trimmed.split(',');
      if (commaParts.length >= 2) {
        const name = commaParts[0].trim();
        const email = commaParts.slice(1).join(',').trim();
        parsed.push({ name, email });
        return;
      }

      // 3. Single name per line
      parsed.push({ name: trimmed, email: '' });
    });

    setTabularData(null);
    setRecipients(parsed);
    setErrorMsg('');
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const lowerName = file.name.toLowerCase();

    if (lowerName.endsWith('.csv')) {
      Papa.parse(file, {
        skipEmptyLines: true,
        complete: (results) => {
          handleTabularLoaded(results.data);
        },
        error: (err) => setErrorMsg(`Failed to parse CSV: ${err.message}`),
      });
    } else if (lowerName.endsWith('.xlsx')) {
      try {
        const rows = await readXlsxFile(file);
        handleTabularLoaded(rows);
      } catch (err) {
        setErrorMsg(`Failed to parse Excel (.xlsx) file: ${err.message}`);
      }
    } else if (lowerName.endsWith('.txt')) {
      const reader = new FileReader();
      reader.onload = (event) => {
        const content = event.target?.result || '';
        parseTxtLines(content);
      };
      reader.readAsText(file);
    } else {
      setErrorMsg('Unsupported file format. Please upload a .csv, .xlsx, or .txt file.');
    }
  };

  const handlePasteSubmit = () => {
    if (!pasteText.trim()) return;
    parseTxtLines(pasteText);
  };

  const handleNameColChange = (e) => {
    const newIdx = parseInt(e.target.value, 10);
    setNameColIdx(newIdx);
    if (tabularData) {
      applyColumnMapping(tabularData.rows, newIdx, emailColIdx);
    }
  };

  const handleEmailColChange = (e) => {
    const newIdx = parseInt(e.target.value, 10);
    setEmailColIdx(newIdx);
    if (tabularData) {
      applyColumnMapping(tabularData.rows, nameColIdx, newIdx);
    }
  };

  const removeRow = (index) => {
    setRecipients(recipients.filter((_, i) => i !== index));
  };

  // Duplicate name count calculation
  const nameCounts = {};
  recipients.forEach((r) => {
    const key = (r.name || '').trim().toLowerCase();
    if (key) {
      nameCounts[key] = (nameCounts[key] || 0) + 1;
    }
  });

  // Calculate statistics: Ready vs Attention
  let readyCount = 0;
  let attentionCount = 0;

  recipients.forEach((r) => {
    const cleanName = (r.name || '').trim();
    const cleanEmail = (r.email || '').trim();
    const nameValid = cleanName.length > 0 && cleanName.length <= 200;
    const emailValid = !cleanEmail || EMAIL_REGEX.test(cleanEmail);

    if (nameValid && emailValid) {
      readyCount += 1;
    } else {
      attentionCount += 1;
    }
  });

  return (
    <div className="card">
      <h2 className="card-title">👥 1. Import Recipients</h2>
      <p className="card-subtitle">
        Upload a CSV, Excel (.xlsx), or plain text file. Invalid or empty names are accepted and flagged
        so they do not fail the rest of your batch.
      </p>

      <div className="tabs-header">
        <button
          type="button"
          className={`tab-btn ${activeTab === 'upload' ? 'active' : ''}`}
          onClick={() => setActiveTab('upload')}
        >
          📁 Upload File (.csv, .xlsx, .txt)
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'paste' ? 'active' : ''}`}
          onClick={() => setActiveTab('paste')}
        >
          📋 Paste Text
        </button>
      </div>

      {errorMsg && <div className="alert-box alert-danger">{errorMsg}</div>}

      {activeTab === 'upload' ? (
        <div className="form-group">
          <input
            type="file"
            accept=".csv, .xlsx, .txt"
            onChange={handleFileUpload}
            className="form-input"
          />
          <small style={{ color: 'var(--text-muted)', display: 'block', marginTop: '0.35rem' }}>
            Supported formats: <strong>.csv</strong>, <strong>.xlsx</strong> (Excel), or <strong>.txt</strong> (one name per line or name &lt;email&gt;).
          </small>
        </div>
      ) : (
        <div className="form-group">
          <textarea
            className="form-input"
            rows="5"
            placeholder="Alice Johnson&#10;Bob Dylan <bob@example.com>&#10;Charlie Brown, charlie@example.com"
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
          />
          <div style={{ marginTop: '0.5rem', display: 'flex', gap: '0.5rem' }}>
            <button type="button" className="action-btn" onClick={handlePasteSubmit}>
              Parse Text Entries
            </button>
            {pasteText && (
              <button
                type="button"
                className="action-btn"
                style={{ background: '#f1f5f9', color: '#475569' }}
                onClick={() => setPasteText('')}
              >
                Clear
              </button>
            )}
          </div>
        </div>
      )}

      {/* Tabular Column Mapping Controls */}
      {tabularData && tabularData.headers && tabularData.headers.length > 0 && (
        <div style={{ background: '#f8fafc', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)', marginBottom: '1.25rem' }}>
          <div style={{ fontWeight: 600, fontSize: '0.875rem', marginBottom: '0.5rem', color: 'var(--text-main)' }}>
            ⚙️ Column Mapping
          </div>
          <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 600 }}>Recipient Name Column:</label>
              <select
                className="form-input"
                style={{ width: 'auto', padding: '0.35rem 0.75rem' }}
                value={nameColIdx}
                onChange={handleNameColChange}
              >
                {tabularData.headers.map((h, i) => (
                  <option key={i} value={i}>
                    {h}
                  </option>
                ))}
              </select>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 600 }}>Email Column (Optional):</label>
              <select
                className="form-input"
                style={{ width: 'auto', padding: '0.35rem 0.75rem' }}
                value={emailColIdx}
                onChange={handleEmailColChange}
              >
                <option value="-1">None (Omit Email)</option>
                {tabularData.headers.map((h, i) => (
                  <option key={i} value={i}>
                    {h}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Recipients Preview Table & Stats */}
      {recipients.length > 0 && (
        <div style={{ marginTop: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
              <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>
                Total: {recipients.length}
              </span>
              <span
                style={{
                  background: '#dcfce7',
                  color: '#166534',
                  padding: '0.2rem 0.6rem',
                  borderRadius: '9999px',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                }}
              >
                ✓ {readyCount} ready
              </span>
              {attentionCount > 0 && (
                <span
                  style={{
                    background: '#fee2e2',
                    color: '#991b1b',
                    padding: '0.2rem 0.6rem',
                    borderRadius: '9999px',
                    fontSize: '0.8rem',
                    fontWeight: 600,
                  }}
                >
                  ⚠️ {attentionCount} need attention
                </span>
              )}
            </div>

            <button
              type="button"
              onClick={() => {
                setRecipients([]);
                setTabularData(null);
              }}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--danger)',
                cursor: 'pointer',
                fontSize: '0.825rem',
                fontWeight: 600,
              }}
            >
              Clear All Rows
            </button>
          </div>

          <div className="table-container" style={{ maxHeight: '320px', overflowY: 'auto' }}>
            <table className="preview-table">
              <thead>
                <tr>
                  <th style={{ width: '50px' }}>#</th>
                  <th>Recipient Name</th>
                  <th>Email (Optional)</th>
                  <th style={{ width: '80px', textAlign: 'center' }}>Remove</th>
                </tr>
              </thead>
              <tbody>
                {recipients.map((r, idx) => {
                  const cleanName = (r.name || '').trim();
                  const cleanEmail = (r.email || '').trim();
                  const isNameEmpty = cleanName.length === 0;
                  const isEmailInvalid = cleanEmail && !EMAIL_REGEX.test(cleanEmail);
                  const isDuplicate = cleanName && (nameCounts[cleanName.toLowerCase()] || 0) > 1;

                  return (
                    <tr
                      key={idx}
                      style={{
                        backgroundColor: isNameEmpty ? '#fff5f5' : isEmailInvalid ? '#fffbeb' : 'inherit',
                      }}
                    >
                      <td style={{ color: 'var(--text-muted)', fontSize: '0.825rem' }}>{idx + 1}</td>
                      <td>
                        {isNameEmpty ? (
                          <span style={{ color: 'var(--danger)', fontWeight: 700, fontSize: '0.85rem' }}>
                            ⚠️ Missing Name
                          </span>
                        ) : (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                            <span>{cleanName}</span>
                            {isDuplicate && (
                              <span
                                style={{
                                  fontSize: '0.725rem',
                                  background: '#fef3c7',
                                  color: '#92400e',
                                  padding: '0.1rem 0.4rem',
                                  borderRadius: '4px',
                                  fontWeight: 600,
                                }}
                              >
                                Duplicate (saved as "{cleanName} (2)")
                              </span>
                            )}
                          </div>
                        )}
                      </td>
                      <td>
                        {cleanEmail ? (
                          <span style={{ color: isEmailInvalid ? 'var(--danger)' : 'inherit' }}>
                            {cleanEmail} {isEmailInvalid && '⚠️ (Invalid syntax)'}
                          </span>
                        ) : (
                          <span style={{ color: 'var(--text-muted)', fontStyle: 'italic', fontSize: '0.8rem' }}>
                            (None)
                          </span>
                        )}
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <button
                          type="button"
                          className="row-delete-btn"
                          title="Remove row"
                          onClick={() => removeRow(idx)}
                        >
                          ✕
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
