const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

async function handleResponse(res) {
  if (!res.ok) {
    let errorMsg = `HTTP Error ${res.status}`;
    try {
      const data = await res.json();
      if (data?.error?.message) {
        errorMsg = data.error.message;
      } else if (data?.detail) {
        errorMsg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      }
    } catch {
      // ignore json parse error
    }
    throw new Error(errorMsg);
  }
  return res.json();
}

export async function fetchTemplates() {
  const res = await fetch(`${API_BASE}/templates`);
  return handleResponse(res);
}

export function getTemplatePreviewUrl(templateId) {
  return `${API_BASE}/templates/${templateId}/preview`;
}

export async function uploadCustomTemplate(formData) {
  const res = await fetch(`${API_BASE}/templates/custom`, {
    method: 'POST',
    body: formData,
  });
  return handleResponse(res);
}

export async function fetchDraftPreview(formData) {
  const res = await fetch(`${API_BASE}/templates/preview/draft`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    let errorMsg = `HTTP Error ${res.status}`;
    try {
      const data = await res.json();
      if (data?.detail) errorMsg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
    } catch {
      // ignore
    }
    throw new Error(errorMsg);
  }
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}


export async function createJob(jobPayload) {
  const res = await fetch(`${API_BASE}/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(jobPayload),
  });
  return handleResponse(res);
}

export async function fetchJobProgress(jobId) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`);
  return handleResponse(res);
}

export async function fetchFailedCertificates(jobId) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/certificates?status=failed&page_size=200`);
  return handleResponse(res);
}

export function getJobZipDownloadUrl(jobId) {
  return `${API_BASE}/jobs/${jobId}/download`;
}

export function getCertificateDownloadUrl(certificateId) {
  return `${API_BASE}/certificates/${certificateId}/download`;
}
