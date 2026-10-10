import React, { useState, useEffect, useRef } from 'react';
import { fetchJobProgress, fetchFailedCertificates, getJobZipDownloadUrl } from '../api';

const FINAL_STATUSES = ['completed', 'completed_with_errors', 'failed'];

export default function StatusPanel({ jobId, onReset }) {
  const [progress, setProgress] = useState(null);
  const [failedCerts, setFailedCerts] = useState([]);
  const [loadingFailed, setLoadingFailed] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const pollTimerRef = useRef(null);

  useEffect(() => {
    if (!jobId) return;

    const poll = async () => {
      try {
        const data = await fetchJobProgress(jobId);
        setProgress(data);

        // Check if finished
        if (FINAL_STATUSES.includes(data.status)) {
          clearInterval(pollTimerRef.current);

          // If there were failed certificates, fetch their details and reasons
          if (data.failed > 0) {
            setLoadingFailed(true);
            try {
              const failedData = await fetchFailedCertificates(jobId);
              setFailedCerts(failedData.items || []);
            } catch (err) {
              console.error('Error fetching failed certificates:', err);
            } finally {
              setLoadingFailed(false);
            }
          }
        }
      } catch (err) {
        setErrorMsg(`Failed to poll job status: ${err.message}`);
      }
    };

    // Initial poll
    poll();
    // Poll every 2 seconds
    pollTimerRef.current = setInterval(poll, 2000);

    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
      }
    };
  }, [jobId]);

  if (!progress) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
        <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>Connecting to generation worker...</div>
        <div style={{ color: 'var(--text-muted)', marginTop: '0.5rem' }}>Job ID: {jobId}</div>
      </div>
    );
  }

  const isCompleted = FINAL_STATUSES.includes(progress.status);
  const finishedCount = progress.succeeded + progress.failed;

  return (
    <div className="card" style={{ border: '2px solid var(--primary)', backgroundColor: '#ffffff' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 className="card-title">
          {isCompleted ? '🎉 Generation Complete' : '⚙️ Generating Certificates...'}
        </h2>
        <span
          className={`badge ${
            progress.status === 'completed'
              ? 'badge-success'
              : progress.status === 'completed_with_errors'
              ? 'badge-warning'
              : progress.status === 'failed'
              ? 'badge-danger'
              : 'badge-warning'
          }`}
          style={{ textTransform: 'uppercase', padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}
        >
          {progress.status.replace(/_/g, ' ')}
        </span>
      </div>

      <p className="card-subtitle">
        Job ID: <code style={{ color: '#0f172a', fontWeight: 600 }}>{jobId}</code>
      </p>

      {errorMsg && <div className="alert-box alert-danger">{errorMsg}</div>}

      {/* Progress Bar */}
      <div className="progress-bar-bg">
        <div
          className="progress-bar-fill"
          style={{ width: `${Math.min(100, Math.max(0, progress.percent))}%` }}
        />
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem', color: 'var(--text-muted)' }}>
        <span>
          <strong>{finishedCount}</strong> of <strong>{progress.total}</strong> processed ({progress.percent}%)
        </span>
        <span>
          {progress.pending > 0 ? `⏳ ${progress.pending} in queue` : '✓ All rows processed'}
        </span>
      </div>

      {/* Stats Counter */}
      <div className="status-stats">
        <div className="stat-item">
          <span className="stat-value" style={{ color: 'var(--success)' }}>{progress.succeeded}</span>
          <span className="stat-label">Succeeded</span>
        </div>
        <div className="stat-item">
          <span className="stat-value" style={{ color: progress.failed > 0 ? 'var(--danger)' : 'var(--text-muted)' }}>
            {progress.failed}
          </span>
          <span className="stat-label">Failed</span>
        </div>
        <div className="stat-item">
          <span className="stat-value">{progress.total}</span>
          <span className="stat-label">Total</span>
        </div>
      </div>

      {/* Action when complete */}
      {isCompleted && (
        <div style={{ marginTop: '1.5rem', display: 'flex', gap: '1rem', alignItems: 'center' }}>
          {progress.succeeded > 0 && (
            <a
              href={getJobZipDownloadUrl(jobId)}
              className="btn-download-zip"
              download
            >
              📦 Download All Certificates (ZIP)
            </a>
          )}
          <button
            type="button"
            className="tab-btn"
            style={{ border: '1px solid var(--border-color)', marginTop: '1.25rem' }}
            onClick={onReset}
          >
            Create New Batch
          </button>
        </div>
      )}

      {/* Failed Recipients Breakdown Table */}
      {progress.failed > 0 && (
        <div style={{ marginTop: '2rem' }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--danger)', marginBottom: '0.5rem' }}>
            ⚠ Failed Recipients ({progress.failed})
          </h3>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
            These recipients failed validation or rendering. Valid certificates were still successfully generated.
          </p>

          {loadingFailed ? (
            <div>Loading failure details...</div>
          ) : (
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th style={{ width: '40px' }}>#</th>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Reason / Error Message</th>
                  </tr>
                </thead>
                <tbody>
                  {failedCerts.map((cert, idx) => (
                    <tr key={cert.id} className="row-invalid">
                      <td>{idx + 1}</td>
                      <td>{cert.recipient_name || <em>(empty)</em>}</td>
                      <td>{cert.recipient_email || <em>(empty)</em>}</td>
                      <td style={{ color: 'var(--danger)', fontWeight: 600 }}>
                        {cert.error_message || 'Rendering error'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
