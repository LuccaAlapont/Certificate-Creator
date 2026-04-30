/** api.js — fetch wrappers for Certificate Creator backend. */

async function apiFetch(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let detail = `Erro ${res.status}`;
    try { const b = await res.json(); detail = b.detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
}

async function apiGetMeta() {
  return apiFetch("/api/templates/meta");
}

async function apiUploadTemplate(file, category = "", variant = "", isVerso = false) {
  const form = new FormData();
  form.append("file", file);
  form.append("category", category);
  form.append("variant", variant);
  form.append("is_verso", isVerso);
  return apiFetch("/api/templates/upload", { method: "POST", body: form });
}

async function apiListTemplates() {
  return apiFetch("/api/templates");
}

async function apiDeleteTemplate(id) {
  return apiFetch(`/api/templates/${id}`, { method: "DELETE" });
}

async function apiSaveConfig(id, config) {
  return apiFetch(`/api/templates/${id}/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
}

async function apiPreview(templateId, name) {
  const res = await fetch("/api/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ template_id: templateId, name }),
  });
  if (!res.ok) {
    let detail = `Erro ${res.status}`;
    try { const b = await res.json(); detail = b.detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

async function apiGenerateText(templateId, namesText, outputFormat = "png") {
  return apiFetch("/api/generate/text", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ template_id: templateId, names_text: namesText, output_format: outputFormat }),
  });
}

async function apiGenerateSpreadsheet(templateId, file, columnIndex, hasHeader, outputFormat = "png") {
  const form = new FormData();
  form.append("template_id", templateId);
  form.append("column_index", columnIndex);
  form.append("has_header", hasHeader);
  form.append("output_format", outputFormat);
  form.append("file", file);
  return apiFetch("/api/generate/spreadsheet", { method: "POST", body: form });
}

async function apiPeekSpreadsheet(file, columnIndex, hasHeader) {
  const form = new FormData();
  form.append("column_index", columnIndex);
  form.append("has_header", hasHeader);
  form.append("file", file);
  return apiFetch("/api/spreadsheet/peek", { method: "POST", body: form });
}

async function apiPollJob(jobId) {
  return apiFetch(`/api/jobs/${jobId}`);
}

function apiDownloadUrl(jobId) {
  return `/api/jobs/${jobId}/download`;
}

// ── Google Drive ──────────────────────────────────────────────────────────────
async function apiDriveStatus() {
  return apiFetch("/api/drive/status");
}

async function apiDriveSaveCredentials(file) {
  const form = new FormData();
  form.append("file", file);
  return apiFetch("/api/drive/credentials", { method: "POST", body: form });
}

async function apiDriveSaveConfig(rootFolderId, year = "") {
  return apiFetch("/api/drive/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ root_folder_id: rootFolderId, year }),
  });
}

async function apiDriveUpload(jobId, category, variant) {
  return apiFetch("/api/drive/upload", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id: jobId, category, variant }),
  });
}

async function apiDrivePollJob(driveJobId) {
  return apiFetch(`/api/drive/jobs/${driveJobId}`);
}
