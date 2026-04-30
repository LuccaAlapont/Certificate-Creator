/** drive.js — Google Drive OAuth2 integration */

const drivePanelToggle = document.getElementById("drivePanelToggle");
const drivePanelBody   = document.getElementById("drivePanelBody");
const driveStatusDot   = document.getElementById("driveStatusDot");
const driveStatusMsg   = document.getElementById("driveStatusMsg");
const driveCredInput   = document.getElementById("driveCredInput");
const driveCredName    = document.getElementById("driveCredName");
const btnDriveAuth     = document.getElementById("btnDriveAuth");
const btnDriveRevoke   = document.getElementById("btnDriveRevoke");
const driveFolderId    = document.getElementById("driveFolderId");
const driveYear        = document.getElementById("driveYear");
const btnDriveSave     = document.getElementById("btnDriveSave");
const btnDriveUpload   = document.getElementById("btnDriveUpload");

let _driveConfigured = false;
let _lastGenJobId    = null;

// ── Panel toggle ──────────────────────────────────────────────────────────────
drivePanelToggle.addEventListener("click", () => {
  drivePanelBody.classList.toggle("hidden");
  drivePanelToggle.querySelector(".drive-icon").textContent =
    drivePanelBody.classList.contains("hidden") ? "▶" : "▼";
});

// ── Status ────────────────────────────────────────────────────────────────────
async function driveLoadStatus() {
  try {
    const s = await apiDriveStatus();
    _driveConfigured = s.configured;
    driveStatusDot.className = "drive-status-dot " + (s.configured ? "ok" : s.authorized ? "warn" : "");

    if (!s.available) {
      driveStatusMsg.textContent = "⚠ Pacotes não instalados. Reinicie o servidor.";
    } else if (s.configured) {
      driveStatusMsg.textContent = "✓ Autorizado e configurado.";
    } else if (s.authorized) {
      driveStatusMsg.textContent = "✓ Conta autorizada. Configure a pasta e o ano.";
    } else if (s.has_credentials) {
      driveStatusMsg.textContent = "Clique em \"Autorizar com Google\" para continuar.";
    } else {
      driveStatusMsg.textContent = "Passo 1: faça upload do JSON OAuth2.";
    }

    btnDriveAuth.style.display   = s.authorized ? "none" : "";
    btnDriveRevoke.style.display = s.authorized ? "" : "none";

    if (s.root_folder_id) driveFolderId.value = s.root_folder_id;
    if (s.year)           driveYear.value      = s.year;

    _refreshDriveBtn();
  } catch (_) {
    driveStatusMsg.textContent = "Erro ao verificar status.";
  }
}

driveLoadStatus();

// Se voltou do callback OAuth2
if (location.search.includes("drive=ok")) {
  history.replaceState({}, "", "/");
  driveLoadStatus();
  showToast("Google Drive autorizado com sucesso!", "success");
  drivePanelBody.classList.remove("hidden");
  drivePanelToggle.querySelector(".drive-icon").textContent = "▼";
}

// ── Upload JSON de credenciais ────────────────────────────────────────────────
driveCredInput.addEventListener("change", async () => {
  const file = driveCredInput.files[0];
  if (!file) return;
  try {
    await apiDriveSaveCredentials(file);
    driveCredName.textContent = "✓ " + file.name;
    driveCredName.style.color = "#22c55e";
    driveLoadStatus();
  } catch (e) {
    driveCredName.textContent = "Erro: " + e.message;
    driveCredName.style.color = "var(--danger)";
  }
});

// ── Desconectar ───────────────────────────────────────────────────────────────
btnDriveRevoke.addEventListener("click", async () => {
  if (!confirm("Desconectar a conta Google do Drive?")) return;
  await apiFetch("/api/drive/revoke", { method: "POST" });
  driveLoadStatus();
  showToast("Conta desconectada.", "success");
});

// ── Salvar pasta e ano ────────────────────────────────────────────────────────
btnDriveSave.addEventListener("click", async () => {
  const id = driveFolderId.value.trim();
  if (!id) { showToast("Informe o ID da pasta.", "error"); return; }
  try {
    btnDriveSave.disabled = true;
    await apiDriveSaveConfig(id, driveYear.value.trim());
    await driveLoadStatus();
    showToast("Configuração salva!", "success");
  } catch (e) {
    showToast("Erro: " + e.message, "error");
  } finally {
    btnDriveSave.disabled = false;
  }
});

// ── Botão Drive (geração simples) ─────────────────────────────────────────────
function _refreshDriveBtn() {
  btnDriveUpload.classList.toggle("hidden", !_driveConfigured || !_lastGenJobId);
}

function driveSetLastJob(jobId) {
  _lastGenJobId = jobId;
  btnDriveUpload.textContent = "📤 Enviar para Drive";
  btnDriveUpload.disabled = false;
  btnDriveUpload.className = "btn btn-secondary btn-lg";
  btnDriveUpload.nextElementSibling?.tagName === "A" && btnDriveUpload.nextElementSibling.remove();
  _refreshDriveBtn();
}

btnDriveUpload.addEventListener("click", () => {
  if (!_lastGenJobId || !state.activeTemplate) return;
  _driveUpload(_lastGenJobId, state.activeTemplate.category, state.activeTemplate.variant, btnDriveUpload);
});

// ── Upload + progresso ────────────────────────────────────────────────────────
async function _driveUpload(genJobId, category, variant, btn) {
  btn.disabled = true;
  btn.textContent = "Iniciando...";
  try {
    const { drive_job_id } = await apiDriveUpload(genJobId, category, variant);
    await _pollDriveJob(drive_job_id, btn);
  } catch (e) {
    btn.disabled = false;
    btn.textContent = "📤 Enviar para Drive";
    showToast("Erro Drive: " + e.message, "error");
  }
}

function _pollDriveJob(driveJobId, btn) {
  return new Promise((resolve, reject) => {
    const iv = setInterval(async () => {
      try {
        const job = await apiDrivePollJob(driveJobId);
        const pct = job.total > 0 ? Math.round((job.progress / job.total) * 100) : 0;
        btn.textContent = job.total > 0
          ? `Enviando... ${job.progress}/${job.total} (${pct}%)`
          : "Enviando...";

        if (job.status === "done") {
          clearInterval(iv);
          btn.textContent = `✓ ${job.uploaded}/${job.total} enviados`;
          btn.classList.add("drive-sent");
          if (job.folder_link) {
            const a = document.createElement("a");
            a.href = job.folder_link;
            a.target = "_blank";
            a.className = "btn btn-ghost btn-sm";
            a.textContent = "Abrir pasta no Drive";
            btn.insertAdjacentElement("afterend", a);
          }
          if (job.errors?.length)
            showToast(`Drive: ${job.errors.length} erro(s).`, "error");
          else
            showToast("Certificados enviados para o Drive!", "success");
          resolve(job);
        } else if (job.status === "error") {
          clearInterval(iv);
          btn.disabled = false;
          btn.textContent = "📤 Enviar para Drive";
          reject(new Error(job.errors?.[0]?.reason || "Erro desconhecido"));
        }
      } catch (e) {
        clearInterval(iv);
        reject(e);
      }
    }, 1500);
  });
}

// ── Botão Drive nas linhas da fila ────────────────────────────────────────────
function createDriveBtn(genJobId, category, variant) {
  if (!_driveConfigured) return "";
  return `<button class="btn btn-secondary btn-sm drive-queue-btn"
    data-job="${genJobId}" data-cat="${encodeURIComponent(category)}" data-var="${variant}">📤 Drive</button>`;
}

document.addEventListener("click", e => {
  const btn = e.target.closest(".drive-queue-btn");
  if (!btn) return;
  _driveUpload(btn.dataset.job, decodeURIComponent(btn.dataset.cat), btn.dataset.var, btn);
});
