import React, { useState } from 'react';
import Papa from 'papaparse';

const EMAIL_REGEX = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;

function validateRecipient(name, email) {
  const isNameValid = Boolean(name && name.trim().length > 0 && name.trim().length <= 200);
  const isEmailValid = Boolean(email && EMAIL_REGEX.test(email.trim()));
  return {
    isNameValid,
    isEmailValid,
    isValid: isNameValid && isEmailValid,
  };
}

export default function ImportPanel({ recipients, setRecipients }) {
  const [activeTab, setActiveTab] = useState('upload'); // 'upload' | 'paste'
  const [pasteText, setPasteText] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  // Parse CSV content using PapaParse
  const handleCsvParsed = (results) => {
    const data = results.data;
    if (!data || data.length === 0) {
      setErrorMsg('CSV file is empty.');
      return;
    }

    const newRecipients = [];
    const firstRow = data[0];

    // Detect if first row is header
    let nameIdx = -1;
    let emailIdx = -1;
    let startIndex = 0;

    if (Array.isArray(firstRow)) {
      firstRow.forEach((col, idx) => {
        const val = String(col).trim().toLowerCase();
        if (val === 'name' || val === 'recipient_name' || val === 'full_name') nameIdx = idx;
        if (val === 'email' || val === 'recipient_email') emailIdx = idx;
      });

      if (nameIdx !== -1 && emailIdx !== -1) {
        startIndex = 1; // Header found
      } else {
        // Fallback: 2 columns without header (col 0 = name, col 1 = email)
        nameIdx = 0;
        emailIdx = 1;
        startIndex = 0;
      }

      for (let i = startIndex; i < data.length; i++) {
        const row = data[i];
        if (!row || row.length < 2) continue;
        const name = String(row[nameIdx] || '').trim();
        const email = String(row[emailIdx] || '').trim();
        if (!name && !email) continue; // Skip completely empty line
        newRecipients.push({ name, email });
      }
    } else if (typeof firstRow === 'object') {
      // Objects mode if PapaParse header: true
      const keys = Object.keys(firstRow);
      const nameKey = keys.find((k) => /name/i.test(k));
      const emailKey = keys.find((k) => /email/i.test(k));

      data.forEach((row) => {
        const name = String(row[nameKey] || '').trim();
        const email = String(row[emailKey] || '').trim();
        if (name || email) {
          newRecipients.push({ name, email });
        }
      });
    }

    setRecipients(newRecipients);
    setErrorMsg('');
  };

  // Parse TXT line-by-line: supports "Name, email" and "Name <email>"
  const handleTxtParse = (text) => {
    const lines = text.split(/\r?\n/);
    const parsed = [];

    lines.forEach((line) => {
      const trimmed = line.trim();
      if (!trimmed) return;

      // Check format: "Name <email@example.com>"
      const angleBracketMatch = trimmed.match(/^([^<]+)<([^>]+)>$/);
      if (angleBracketMatch) {
        parsed.push({
          name: angleBracketMatch[1].trim(),
          email: angleBracketMatch[2].trim(),
        });
        return;
      }

      // Check format: "Name, email@example.com"
      const commaParts = trimmed.split(',');
      if (commaParts.length >= 2) {
        const name = commaParts[0].trim();
        const email = commaParts.slice(1).join(',').trim();
        parsed.push({ name, email });
        return;
      }

      // Fallback
      parsed.push({ name: trimmed, email: '' });
    });

    return parsed;
  };

  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const fileName = file.name.toLowerCase();
    if (fileName.endsWith('.csv')) {
      Papa.parse(file, {
        complete: handleCsvParsed,
        error: (err) => setErrorMsg(`Failed to parse CSV: ${err.message}`),
      });
    } else if (fileName.endsWith('.txt')) {
      const reader = new FileReader();
      reader.onload = (event) => {
        const content = event.target?.result || '';
        const parsed = handleTxtParse(content);
        setRecipients(parsed);
        setErrorMsg('');
      };
      reader.readAsText(file);
    } else {
      setErrorMsg('Please upload a .csv or .txt file.');
    }
  };

  const handlePasteSubmit = () => {
    if (!pasteText.trim()) return;
    const parsed = handleTxtParse(pasteText);
    setRecipients(parsed);
    setErrorMsg('');
  };

  const removeRow = (index) => {
    setRecipients(recipients.filter((_, i) => i !== index));
  };

  // Calculate statistics
  const stats = recipients.reduce(
    (acc, r) => {
      const { isValid } = validateRecipient(r.name, r.email);
      if (isValid) acc.ready += 1;
      else acc.problem += 1;
      return acc;
    },
    { ready: 0, problem: 0 }
  );

  return (
    <div className="card">
      <h2 className="card-title">👥 1. Import Recipients</h2>
      <p className="card-subtitle">
        Upload a CSV/TXT file or paste recipient details. Invalid entries are accepted and will be
        flagged in the status report rather than failing the whole job.
      </p>

      <div className="tabs-header">
        <button
          className={`tab-btn ${activeTab === 'upload' ? 'active' : ''}`}
          onClick={() => setActiveTab('upload')}
        >
          📁 Upload File (.csv, .txt)
        </button>
        <button
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
            accept=".csv, .txt"
            onChange={handleFileUpload}
            className="form-input"
          />
          <small style={{ color: 'var(--text-muted)', display: 'block', marginTop: '0.25rem' }}>
            Supported formats: CSV with "name, email" columns, or TXT lines formatted as "Name, email" or "Name &lt;email&gt;".
          </small>
        </div>
      ) : (
        <div className="form-group">
          <textarea
            className="form-textarea"
            placeholder="Jane Doe, jane@example.com&#10;John Smith <john@example.com>"
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
          />
          <button
            type="button"
            className="tab-btn active"
            style={{ marginTop: '0.5rem' }}
            onClick={handlePasteSubmit}
          >
            Apply Pasted Recipients
          </button>
        </div>
      )}

      {recipients.length > 0 && (
        <div>
          <div className="badge-group">
            <span className="badge badge-success">✓ {stats.ready} ready</span>
            {stats.problem > 0 && (
              <span className="badge badge-danger">⚠ {stats.problem} with problems</span>
            )}
            <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              ({recipients.length} total)
            </span>
          </div>

          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th style={{ width: '50px' }}>#</th>
                  <th>Recipient Name</th>
                  <th>Email Address</th>
                  <th style={{ width: '80px' }}>Status</th>
                  <th style={{ width: '60px' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {recipients.map((rec, idx) => {
                  const { isNameValid, isEmailValid, isValid } = validateRecipient(
                    rec.name,
                    rec.email
                  );
                  return (
                    <tr key={idx} className={!isValid ? 'row-invalid' : ''}>
                      <td>{idx + 1}</td>
                      <td style={{ color: !isNameValid ? 'var(--danger)' : 'inherit' }}>
                        {rec.name || <em>(empty name)</em>}
                      </td>
                      <td style={{ color: !isEmailValid ? 'var(--danger)' : 'inherit' }}>
                        {rec.email || <em>(empty email)</em>}
                      </td>
                      <td>
                        {isValid ? (
                          <span className="badge badge-success">Valid</span>
                        ) : (
                          <span className="badge badge-danger">Problem</span>
                        )}
                      </td>
                      <td>
                        <button
                          type="button"
                          className="btn-remove"
                          onClick={() => removeRow(idx)}
                          title="Remove row"
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
