/** app.js — Certificate Creator UI logic. */

// ── State ─────────────────────────────────────────────────────────────────
const state = {
  posGraduacoes:   [],
  grouped:         [],
  activeTemplate:  null,
  activeTab:       "text",
  currentJobId:    null,
  pollInterval:    null,
  spreadsheetFile: null,
  pendingSlot:     null,   // { category, variant, isVerso }
  queue:           [],     // pending tasks
};

// ── DOM refs ──────────────────────────────────────────────────────────────
const posList         = document.getElementById("posList");
const noTemplateMsg   = document.getElementById("noTemplateMsg");
const templateEditor  = document.getElementById("templateEditor");
const selectedBadge   = document.getElementById("selectedBadge");
const templateImg     = document.getElementById("templateImg");
const canvasWrap      = document.getElementById("canvasWrap");
const posMarker       = document.getElementById("posMarker");
const maxWidthBar     = document.getElementById("maxWidthBar");
const cfgFontSize     = document.getElementById("cfgFontSize");
const cfgMaxWidth     = document.getElementById("cfgMaxWidth");
const cfgColor        = document.getElementById("cfgColor");
const cfgAlignment    = document.getElementById("cfgAlignment");
const cfgFontName     = document.getElementById("cfgFontName");
const btnSaveConfig   = document.getElementById("btnSaveConfig");
const btnPreview      = document.getElementById("btnPreview");
const namesTextarea   = document.getElementById("namesTextarea");
const nameCount       = document.getElementById("nameCount");
const inputSpreadsheet    = document.getElementById("inputSpreadsheet");
const spreadsheetFilename = document.getElementById("spreadsheetFilename");
const spreadsheetOpts     = document.getElementById("spreadsheetOpts");
const spreadsheetPreview  = document.getElementById("spreadsheetPreview");
const colIndex            = document.getElementById("colIndex");
const hasHeader           = document.getElementById("hasHeader");
const btnPeek             = document.getElementById("btnPeek");
const peekList            = document.getElementById("peekList");
const peekTotal           = document.getElementById("peekTotal");
const btnGenerate    = document.getElementById("btnGenerate");
const progressArea   = document.getElementById("progressArea");
const progressBar    = document.getElementById("progressBar");
const progressLabel  = document.getElementById("progressLabel");
const summaryArea    = document.getElementById("summaryArea");
const summaryBox     = document.getElementById("summaryBox");
const btnDownload    = document.getElementById("btnDownload");
const versoHint      = document.getElementById("versoHint");
const previewModal   = document.getElementById("previewModal");
const previewModalImg = document.getElementById("previewModalImg");
const btnClosePreview = document.getElementById("btnClosePreview");
const btnAddToQueue    = document.getElementById("btnAddToQueue");
const queueEmpty       = document.getElementById("queueEmpty");
const queueList        = document.getElementById("queueList");
const queueFooter      = document.getElementById("queueFooter");
const queueResults     = document.getElementById("queueResults");
const btnRunAll        = document.getElementById("btnRunAll");
const btnClearQueue    = document.getElementById("btnClearQueue");
const globalSlotInput  = document.getElementById("globalSlotInput");
const versoPairItem    = document.getElementById("versoPairItem");
const versoPairSep     = document.getElementById("versoPairSep");
const versoPairImg     = document.getElementById("versoPairImg");
const toast            = document.getElementById("toast");

// ── Init ──────────────────────────────────────────────────────────────────
(async function init() {
  const meta = await apiGetMeta();
  state.posGraduacoes = meta.pos_graduacoes;
  await loadTemplates();
  bindEvents();
})();

// ── Load & render ─────────────────────────────────────────────────────────
async function loadTemplates() {
  try {
    const data = await apiListTemplates();
    state.grouped = data.grouped;
    renderPosList();
    updateVersoPreview();
  } catch (e) {
    showToast("Erro ao carregar modelos: " + e.message, "error");
  }
}

function updateVersoHint() {
  const fmt = document.querySelector('input[name="outputFormat"]:checked')?.value || "png";
  const isPdf = fmt === "pdf" || fmt === "pdf_combined";
  if (!state.activeTemplate || !isPdf) { versoHint.classList.add("hidden"); return; }
  const group = state.grouped.find(g => g.category === state.activeTemplate.category);
  const versoKey = `${state.activeTemplate.variant}_verso`;
  const hasVerso = !!(group?.slots[versoKey]);
  versoHint.textContent = hasVerso ? "✓ Verso encontrado — será incluído no PDF" : "";
  versoHint.classList.toggle("hidden", !hasVerso);
}

function updateVersoPreview() {
  if (!state.activeTemplate) { versoPairItem.classList.add("hidden"); versoPairSep.classList.add("hidden"); return; }
  const group = state.grouped.find(g => g.category === state.activeTemplate.category);
  const versoKey = `${state.activeTemplate.variant}_verso`;
  const verso = group?.slots[versoKey];
  if (verso) {
    versoPairImg.src = `/uploads/${verso.filename}`;
    versoPairItem.classList.remove("hidden");
    versoPairSep.classList.remove("hidden");
  } else {
    versoPairItem.classList.add("hidden");
    versoPairSep.classList.add("hidden");
  }
}

// ── Pós list ──────────────────────────────────────────────────────────────
function renderPosList() {
  posList.innerHTML = "";
  state.grouped.forEach(group => {
    const azulFilled  = !!group.slots["azul"];
    const verdeFilled = !!group.slots["verde"];

    const div = document.createElement("div");
    div.className = "cat-group";
    div.dataset.category = group.category;

    div.innerHTML = `
      <div class="cat-header">
        <span class="cat-chevron">▶</span>
        <span class="cat-name">${group.category}</span>
        <span class="cat-dots">
          <span class="cat-dot azul ${azulFilled ? "filled" : ""}"></span>
          <span class="cat-dot verde ${verdeFilled ? "filled" : ""}"></span>
        </span>
      </div>
      <div class="cat-slots">
        <div class="slot-row-label">Frente</div>
        <div class="slot-row">
          ${renderSlotHTML(group.slots["azul"],        group.category, "azul",  "Médicos",        false)}
          ${renderSlotHTML(group.slots["verde"],       group.category, "verde", "Profissionais",       false)}
        </div>
        <div class="slot-row-label verso-row-label">Verso</div>
        <div class="slot-row">
          ${renderSlotHTML(group.slots["azul_verso"],  group.category, "azul",  "Médicos Verso",  true)}
          ${renderSlotHTML(group.slots["verde_verso"], group.category, "verde", "Profissionais Verso", true)}
        </div>
      </div>`;

    div.querySelector(".cat-header").addEventListener("click", () => {
      div.classList.toggle("open");
    });

    div.querySelectorAll(".template-slot").forEach(slot => {
      const cat      = slot.dataset.category;
      const variant  = slot.dataset.variant;
      const isVerso  = slot.dataset.isVerso === "true";
      const templateId = slot.dataset.templateId;

      if (templateId) {
        const previewBtn = slot.querySelector(".slot-preview");
        if (previewBtn) {
          previewBtn.addEventListener("click", e => {
            e.stopPropagation();
            previewModalImg.src = previewBtn.dataset.src;
            previewModal.classList.remove("hidden");
          });
        }
        if (!isVerso) {
          slot.addEventListener("click", e => {
            if (e.target.closest(".slot-del") || e.target.closest(".slot-preview")) return;
            const t = findTemplate(parseInt(templateId));
            if (t) selectTemplate(t);
          });
        }
        const delBtn = slot.querySelector(".slot-del");
        if (delBtn) {
          delBtn.addEventListener("click", async e => {
            e.stopPropagation();
            if (!confirm("Remover este modelo?")) return;
            await apiDeleteTemplate(parseInt(templateId));
            if (state.activeTemplate?.id === parseInt(templateId)) {
              state.activeTemplate = null;
              noTemplateMsg.classList.remove("hidden");
              templateEditor.classList.add("hidden");
            }
            await loadTemplates();
            showToast("Modelo removido.", "success");
          });
        }
      } else {
        slot.addEventListener("click", () => triggerSlotUpload(cat, variant, isVerso));
      }
    });

    posList.appendChild(div);
  });

  if (state.activeTemplate) highlightActiveSlot(state.activeTemplate);
}

function renderSlotHTML(t, category, variant, label, isVerso) {
  const isActive   = !isVerso && state.activeTemplate?.id === t?.id;
  const activeClass = isActive ? ` active ${variant}` : "";
  const versoClass  = isVerso ? " verso" : "";
  const isVersoAttr = isVerso ? "true" : "false";
  if (t) {
    return `
      <div class="template-slot ${variant}${versoClass}${activeClass}" data-category="${category}" data-variant="${variant}" data-is-verso="${isVersoAttr}" data-template-id="${t.id}">
        <img src="/uploads/${t.filename}" alt="${label}" />
        <div class="slot-label">${label}</div>
        <button class="slot-preview" title="Visualizar" data-src="/uploads/${t.filename}">👁</button>
        <button class="slot-del" title="Remover">✕</button>
      </div>`;
  }
  return `
    <div class="template-slot ${variant}${versoClass}" data-category="${category}" data-variant="${variant}" data-is-verso="${isVersoAttr}">
      <div class="slot-add">+</div>
      <div class="slot-label">${label}</div>
    </div>`;
}

function findTemplate(id) {
  for (const g of state.grouped) {
    for (const t of Object.values(g.slots)) {
      if (t && t.id === id) return t;
    }
  }
  return null;
}

function highlightActiveSlot(t) {
  document.querySelectorAll(".template-slot").forEach(s => {
    s.classList.remove("active");
  });
  if (!t) return;
  const slot = document.querySelector(`.template-slot[data-template-id="${t.id}"]`);
  if (slot) {
    slot.classList.add("active");
    slot.closest(".cat-group")?.classList.add("open");
  }
}

// ── Slot upload ───────────────────────────────────────────────────────────
function triggerSlotUpload(category, variant, isVerso) {
  state.pendingSlot = { category, variant, isVerso };
  globalSlotInput.value = "";
  globalSlotInput.click();
}

globalSlotInput.addEventListener("change", async () => {
  const file = globalSlotInput.files[0];
  if (!file || !state.pendingSlot) return;
  const { category, variant, isVerso } = state.pendingSlot;
  state.pendingSlot = null;
  try {
    const data = await apiUploadTemplate(file, category, variant, isVerso);
    await loadTemplates();
    if (!isVerso) {
      const fresh = data.template ? (findTemplate(data.template.id) || data.template) : null;
      if (fresh) selectTemplate(fresh);
    }
    showToast("Modelo enviado!", "success");
  } catch (e) {
    showToast("Erro ao enviar: " + e.message, "error");
  }
});

// ── Select template ───────────────────────────────────────────────────────
function selectTemplate(t) {
  state.activeTemplate = t;
  highlightActiveSlot(t);

  noTemplateMsg.classList.add("hidden");
  templateEditor.classList.remove("hidden");

  const variantLabel  = t.variant === "verde" ? "Verde — Profissionais de Saúde" : "Azul — Médicos";
  selectedBadge.className = `selected-badge ${t.variant || "azul"}`;
  selectedBadge.innerHTML = `<span class="badge-dot"></span>${t.category || "Modelo"} &mdash; ${variantLabel}`;

  templateImg.src = `/uploads/${t.filename}`;
  populateConfig(t.config);
  updateVersoPreview();
  updateVersoHint();
}

function populateConfig(cfg) {
  cfgFontSize.value  = cfg.font_size  ?? 200;
  cfgMaxWidth.value  = Math.round((cfg.max_width ?? 0.7) * 100);
  cfgColor.value     = cfg.color      ?? "#ffffff";
  cfgAlignment.value = cfg.alignment  ?? "center";
  cfgFontName.value  = cfg.font_name  ?? "";
}

// ── Position marker ───────────────────────────────────────────────────────
templateImg.addEventListener("load", () => {
  if (state.activeTemplate?.config) updateMarkerFromConfig(state.activeTemplate.config);
});
window.addEventListener("resize", () => {
  if (state.activeTemplate?.config) updateMarkerFromConfig(state.activeTemplate.config);
});

function updateMarkerFromConfig(cfg) {
  setMarkerRelative(cfg.center_x ?? 0.5, cfg.center_y ?? 0.5, cfg.max_width ?? 0.8);
}

function setMarkerRelative(cx, cy, maxW) {
  const rect     = templateImg.getBoundingClientRect();
  const wrapRect = canvasWrap.getBoundingClientRect();
  const px = (rect.left - wrapRect.left) + cx * rect.width;
  const py = (rect.top  - wrapRect.top)  + cy * rect.height;

  posMarker.style.cssText = `left:${px}px;top:${py}px;display:block`;
  const barW = maxW * rect.width;
  maxWidthBar.style.cssText = `width:${barW}px;left:${px - barW/2}px;top:${py}px;display:block`;
}

canvasWrap.addEventListener("click", e => {
  if (!state.activeTemplate) return;
  const rect = templateImg.getBoundingClientRect();
  const relX = (e.clientX - rect.left) / rect.width;
  const relY = (e.clientY - rect.top)  / rect.height;
  if (relX < 0 || relX > 1 || relY < 0 || relY > 1) return;
  if (!state.activeTemplate.config) state.activeTemplate.config = {};
  state.activeTemplate.config.center_x = relX;
  state.activeTemplate.config.center_y = relY;
  setMarkerRelative(relX, relY, parseFloat(cfgMaxWidth.value) / 100 || 0.8);
});

cfgMaxWidth.addEventListener("input", () => {
  if (!state.activeTemplate) return;
  setMarkerRelative(
    state.activeTemplate.config?.center_x ?? 0.5,
    state.activeTemplate.config?.center_y ?? 0.5,
    parseFloat(cfgMaxWidth.value) / 100 || 0.8,
  );
});

// ── Save config ───────────────────────────────────────────────────────────
async function saveCurrentConfig(silent = false) {
  if (!state.activeTemplate) return false;
  try {
    const data = await apiSaveConfig(state.activeTemplate.id, buildConfigFromForm());
    state.activeTemplate = data.template;
    if (!silent) showToast("Configuração salva!", "success");
    return true;
  } catch (e) {
    showToast("Erro ao salvar: " + e.message, "error");
    return false;
  }
}

btnSaveConfig.addEventListener("click", () => saveCurrentConfig(false));

function buildConfigFromForm() {
  return {
    center_x:  state.activeTemplate.config?.center_x  ?? 0.5,
    center_y:  state.activeTemplate.config?.center_y  ?? 0.5,
    max_width: (parseFloat(cfgMaxWidth.value) || 80) / 100,
    font_size: parseInt(cfgFontSize.value) || 72,
    font_name: cfgFontName.value.trim(),
    color:     cfgColor.value,
    alignment: cfgAlignment.value,
  };
}

// ── Preview ───────────────────────────────────────────────────────────────
btnPreview.addEventListener("click", async () => {
  if (!state.activeTemplate) return;
  const name = prompt("Nome para pré-visualização:", "Maria da Silva Santos");
  if (!name) return;
  try {
    btnPreview.disabled = true;
    await saveCurrentConfig(true);
    const url = await apiPreview(state.activeTemplate.id, name);
    previewModalImg.src = url;
    previewModal.classList.remove("hidden");
  } catch (e) {
    showToast("Erro na pré-visualização: " + e.message, "error");
  } finally {
    btnPreview.disabled = false;
  }
});

btnClosePreview.addEventListener("click", () => previewModal.classList.add("hidden"));
previewModal.addEventListener("click", e => { if (e.target === previewModal) previewModal.classList.add("hidden"); });

// ── Tabs ──────────────────────────────────────────────────────────────────
document.querySelectorAll(".tab").forEach(btn => {
  btn.addEventListener("click", () => {
    state.activeTab = btn.dataset.tab;
    document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tabText").classList.toggle("hidden", state.activeTab !== "text");
    document.getElementById("tabSpreadsheet").classList.toggle("hidden", state.activeTab !== "spreadsheet");
  });
});

// ── Names textarea ────────────────────────────────────────────────────────
namesTextarea.addEventListener("input", () => {
  const count = namesTextarea.value.split("\n").filter(l => l.trim()).length;
  nameCount.textContent = `${count} nome${count !== 1 ? "s" : ""} detectado${count !== 1 ? "s" : ""}`;
});

// ── Spreadsheet ───────────────────────────────────────────────────────────
inputSpreadsheet.addEventListener("change", () => {
  const file = inputSpreadsheet.files[0];
  if (!file) return;
  state.spreadsheetFile = file;
  spreadsheetFilename.textContent = file.name;
  spreadsheetOpts.style.display = "flex";
  spreadsheetPreview.classList.add("hidden");
});

btnPeek.addEventListener("click", async () => {
  if (!state.spreadsheetFile) return;
  try {
    btnPeek.disabled = true;
    const data = await apiPeekSpreadsheet(state.spreadsheetFile, parseInt(colIndex.value) || 0, hasHeader.checked);
    peekList.innerHTML = data.preview.map(n => `<li>${n}</li>`).join("");
    peekTotal.textContent = `${data.total} nome${data.total !== 1 ? "s" : ""} no total`;
    spreadsheetPreview.classList.remove("hidden");
  } catch (e) {
    showToast("Erro ao ler planilha: " + e.message, "error");
  } finally {
    btnPeek.disabled = false;
  }
});

// ── Format change → verso hint ────────────────────────────────────────────
document.querySelectorAll('input[name="outputFormat"]').forEach(r => {
  r.addEventListener("change", updateVersoHint);
});

// ── Generate ──────────────────────────────────────────────────────────────
btnGenerate.addEventListener("click", async () => {
  if (!state.activeTemplate) { showToast("Selecione um modelo primeiro.", "error"); return; }

  const fmt = document.querySelector('input[name="outputFormat"]:checked')?.value || "png";
  let jobData;
  try {
    btnGenerate.disabled = true;
    summaryArea.classList.add("hidden");
    progressArea.classList.remove("hidden");
    progressBar.style.width = "0%";
    progressLabel.textContent = "Salvando configuração...";

    const saved = await saveCurrentConfig(true);
    if (!saved) { btnGenerate.disabled = false; progressArea.classList.add("hidden"); return; }
    progressLabel.textContent = "Iniciando...";

    if (state.activeTab === "text") {
      const text = namesTextarea.value;
      if (!text.trim()) { showToast("Insira ao menos um nome.", "error"); return; }
      jobData = await apiGenerateText(state.activeTemplate.id, text, fmt);
    } else {
      if (!state.spreadsheetFile) { showToast("Selecione uma planilha.", "error"); return; }
      jobData = await apiGenerateSpreadsheet(state.activeTemplate.id, state.spreadsheetFile, parseInt(colIndex.value) || 0, hasHeader.checked, fmt);
    }

    state.currentJobId = jobData.job_id;
    startPolling(jobData.job_id, jobData.total);
  } catch (e) {
    showToast("Erro ao iniciar geração: " + e.message, "error");
    progressArea.classList.add("hidden");
    btnGenerate.disabled = false;
  }
});

function startPolling(jobId, total) {
  clearInterval(state.pollInterval);
  state.pollInterval = setInterval(async () => {
    try {
      const job = await apiPollJob(jobId);
      const pct = total > 0 ? Math.round((job.progress / total) * 100) : 0;
      progressBar.style.width = pct + "%";
      progressLabel.textContent = `${job.progress} / ${total} certificados gerados...`;

      if (job.status === "done") {
        clearInterval(state.pollInterval);
        progressBar.style.width = "100%";
        progressLabel.textContent = "Concluído!";
        showSummary(job, total);
        btnGenerate.disabled = false;
      } else if (job.status === "error") {
        clearInterval(state.pollInterval);
        showToast("Erro: " + (job.alerts[0]?.reason || "desconhecido"), "error");
        progressArea.classList.add("hidden");
        btnGenerate.disabled = false;
      }
    } catch (e) {
      clearInterval(state.pollInterval);
      showToast("Erro ao verificar progresso.", "error");
      btnGenerate.disabled = false;
    }
  }, 1000);
}

function buildDownloadName(template, fmt) {
  const variant  = template?.variant === "verde" ? "Profissionais" : "Médicos";
  const category = (template?.category || "Certificados").replace(/[\\/:*?"<>|]/g, "");
  const ext      = fmt === "pdf_combined" ? ".pdf" : ".zip";
  return `${variant} - ${category}${ext}`;
}

function triggerDownload(url, filename) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function showSummary(job, total) {
  const alerts  = job.alerts || [];
  const reduced = alerts.filter(a => a.reason === "fonte reduzida para caber");
  const errors  = alerts.filter(a => a.reason !== "fonte reduzida para caber");
  const success = total - errors.length;

  let html = `<strong>✅ ${success} de ${total} certificados gerados com sucesso.</strong><br>`;
  if (reduced.length) html += `<span class="alert-row">⚠ ${reduced.length} com fonte reduzida.</span><br>`;
  if (errors.length) {
    html += `<span class="alert-row">❌ ${errors.length} com falha.</span>`;
    errors.forEach(e => { html += `<br><small style="color:var(--muted)">— ${e.name}: ${e.reason}</small>`; });
  }

  summaryBox.innerHTML = html;
  summaryArea.classList.remove("hidden");

  const fmt      = job.output_format || "png";
  const filename = buildDownloadName(state.activeTemplate, fmt);
  btnDownload.textContent = fmt === "pdf_combined" ? "⬇ Baixar PDF combinado" : "⬇ Baixar certificados (.zip)";
  btnDownload.onclick = () => triggerDownload(apiDownloadUrl(job.job_id || state.currentJobId), filename);

  if (typeof driveSetLastJob === "function") driveSetLastJob(job.job_id || state.currentJobId);
}

// ── Bind misc ─────────────────────────────────────────────────────────────
function bindEvents() {}

// ── Queue ─────────────────────────────────────────────────────────────────
const _FMT_LABEL = { png: "PNG", jpeg_cmyk: "JPEG CMYK", pdf: "PDF (ZIP)", pdf_combined: "PDF combinado" };

btnAddToQueue.addEventListener("click", () => {
  if (!state.activeTemplate) { showToast("Selecione um modelo primeiro.", "error"); return; }

  const fmt   = document.querySelector('input[name="outputFormat"]:checked')?.value || "png";
  const tab   = state.activeTab;
  const namesText = namesTextarea.value.trim();

  if (tab === "text") {
    if (!namesText) { showToast("Insira ao menos um nome.", "error"); return; }
  } else {
    if (!state.spreadsheetFile) { showToast("Selecione uma planilha.", "error"); return; }
  }

  const nameCount = tab === "text"
    ? namesText.split("\n").filter(l => l.trim()).length
    : "?";

  const variantLabel = state.activeTemplate.variant === "verde" ? "Profissionais" : "Médicos";
  const t = state.activeTemplate;

  state.queue.push({
    id:              crypto.randomUUID(),
    template:        { ...t },
    config:          buildConfigFromForm(),   // captura o config atual do formulário
    activeTab:       tab,
    namesText:       tab === "text" ? namesText : "",
    spreadsheetFile: tab === "spreadsheet" ? state.spreadsheetFile : null,
    colIndex:        parseInt(colIndex.value) || 0,
    hasHeader:       hasHeader.checked,
    outputFormat:    fmt,
    nameCount,
    label: `${t.category} — ${variantLabel} — ${nameCount} nomes — ${_FMT_LABEL[fmt] || fmt}`,
  });

  renderQueue();
  showToast("Tarefa adicionada à fila!", "success");
});

function renderQueue() {
  const empty = state.queue.length === 0;
  queueEmpty.classList.toggle("hidden", !empty);
  queueFooter.classList.toggle("hidden", empty);

  queueList.innerHTML = "";
  state.queue.forEach((task, idx) => {
    const li = document.createElement("li");
    li.className = "queue-item";
    li.innerHTML = `
      <span class="queue-dot ${task.template.variant || "azul"}"></span>
      <span class="queue-label">${task.label}</span>
      <button class="queue-remove" data-idx="${idx}" title="Remover">✕</button>`;
    li.querySelector(".queue-remove").addEventListener("click", () => {
      state.queue.splice(idx, 1);
      renderQueue();
    });
    queueList.appendChild(li);
  });
}

btnClearQueue.addEventListener("click", () => {
  if (!confirm("Limpar todas as tarefas da fila?")) return;
  state.queue = [];
  queueResults.innerHTML = "";
  renderQueue();
});

btnRunAll.addEventListener("click", async () => {
  if (state.queue.length === 0) return;
  btnRunAll.disabled = true;
  btnClearQueue.disabled = true;
  btnAddToQueue.disabled = true;
  btnGenerate.disabled = true;
  queueResults.innerHTML = "";

  const tasks = [...state.queue];

  for (let i = 0; i < tasks.length; i++) {
    const task = tasks[i];
    const itemEls = queueList.querySelectorAll(".queue-item");
    if (itemEls[i]) itemEls[i].classList.add("queue-item-running");

    try {
      // Salva o config capturado no momento em que a tarefa foi adicionada à fila
      await apiSaveConfig(task.template.id, task.config);
      let jobData;
      if (task.activeTab === "text") {
        jobData = await apiGenerateText(task.template.id, task.namesText, task.outputFormat);
      } else {
        jobData = await apiGenerateSpreadsheet(
          task.template.id, task.spreadsheetFile,
          task.colIndex, task.hasHeader, task.outputFormat
        );
      }

      const job = await _pollTask(jobData.job_id, jobData.total, task, i, tasks.length);
      if (itemEls[i]) { itemEls[i].classList.remove("queue-item-running"); itemEls[i].classList.add("queue-item-done"); }

      const div = document.createElement("div");
      div.className = "queue-result-row";
      const alerts = job.alerts || [];
      const errors = alerts.filter(a => a.reason !== "fonte reduzida para caber").length;
      const ok = jobData.total - errors;
      const dlName  = buildDownloadName(task.template, task.outputFormat);
      const drivBtn = typeof createDriveBtn === "function"
        ? createDriveBtn(jobData.job_id, task.template.category, task.template.variant) : "";
      div.innerHTML = `
        <span class="queue-dot ${task.template.variant || "azul"}"></span>
        <span class="queue-result-label">${task.label} — <strong>${ok}/${jobData.total}</strong> gerados</span>
        <a class="btn btn-secondary btn-sm" href="${apiDownloadUrl(jobData.job_id)}" download="${dlName}">⬇ Baixar</a>
        ${drivBtn}`;
      queueResults.appendChild(div);

    } catch (e) {
      if (itemEls[i]) { itemEls[i].classList.remove("queue-item-running"); itemEls[i].classList.add("queue-item-error"); }
      const div = document.createElement("div");
      div.className = "queue-result-row error";
      div.innerHTML = `<span class="queue-dot"></span><span class="queue-result-label">${task.label} — <strong>Erro:</strong> ${e.message}</span>`;
      queueResults.appendChild(div);
    }
  }

  state.queue = [];
  renderQueue();
  btnRunAll.disabled = false;
  btnClearQueue.disabled = false;
  btnAddToQueue.disabled = false;
  btnGenerate.disabled = false;
  showToast("Fila concluída!", "success");
});

function _pollTask(jobId, total, task, taskIdx, taskTotal) {
  return new Promise((resolve, reject) => {
    const interval = setInterval(async () => {
      try {
        const job = await apiPollJob(jobId);
        const pct = total > 0 ? Math.round((job.progress / total) * 100) : 0;
        progressBar.style.width = pct + "%";
        progressLabel.textContent =
          `Tarefa ${taskIdx + 1}/${taskTotal}: ${task.template.category} — ${job.progress}/${total}...`;
        progressArea.classList.remove("hidden");

        if (job.status === "done") {
          clearInterval(interval);
          progressBar.style.width = "100%";
          resolve({ ...job, job_id: jobId });
        } else if (job.status === "error") {
          clearInterval(interval);
          reject(new Error(job.alerts?.[0]?.reason || "Erro desconhecido"));
        }
      } catch (e) {
        clearInterval(interval);
        reject(e);
      }
    }, 1000);
  });
}

// ── Toast ─────────────────────────────────────────────────────────────────
let _toastTimer = null;
function showToast(msg, type = "") {
  toast.textContent = msg;
  toast.className = "toast" + (type ? " " + type : "");
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => toast.classList.add("hidden"), 3500);
}
