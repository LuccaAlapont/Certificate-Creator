/** convert.js — Imagem → PDF sidebar logic. */

const convDropZone  = document.getElementById("convDropZone");
const convFileInput = document.getElementById("convFileInput");
const convFileList  = document.getElementById("convFileList");
const btnConvert    = document.getElementById("btnConvert");
const convStatus    = document.getElementById("convStatus");

let convFiles = [];   // File objects in order

// ── Drop zone ─────────────────────────────────────────────────────────────
convDropZone.addEventListener("click", () => convFileInput.click());

convDropZone.addEventListener("dragover", e => {
  e.preventDefault();
  convDropZone.classList.add("drag-over");
});
convDropZone.addEventListener("dragleave", () => convDropZone.classList.remove("drag-over"));
convDropZone.addEventListener("drop", e => {
  e.preventDefault();
  convDropZone.classList.remove("drag-over");
  addFiles([...e.dataTransfer.files]);
});

convFileInput.addEventListener("change", () => {
  addFiles([...convFileInput.files]);
  convFileInput.value = "";
});

// ── File management ───────────────────────────────────────────────────────
function addFiles(files) {
  const allowed = new Set(["image/png", "image/jpeg", "image/webp", "image/bmp", "image/tiff"]);
  const valid = files.filter(f => allowed.has(f.type) || /\.(png|jpe?g|webp|bmp|tiff?)$/i.test(f.name));
  if (!valid.length) {
    showToast("Nenhuma imagem válida. Use PNG, JPG, WEBP, BMP ou TIFF.", "error");
    return;
  }
  convFiles.push(...valid);
  renderFileList();
}

function removeFile(index) {
  convFiles.splice(index, 1);
  renderFileList();
}

function renderFileList() {
  convFileList.innerHTML = "";
  convFiles.forEach((file, i) => {
    const li = document.createElement("li");
    li.className = "conv-file-item";

    const thumb = document.createElement("img");
    thumb.className = "conv-file-thumb";
    thumb.alt = file.name;
    const url = URL.createObjectURL(file);
    thumb.src = url;
    thumb.onload = () => URL.revokeObjectURL(url);

    const name = document.createElement("span");
    name.className = "conv-file-name";
    name.textContent = file.name;
    name.title = file.name;

    const rm = document.createElement("button");
    rm.className = "conv-file-remove";
    rm.textContent = "✕";
    rm.title = "Remover";
    rm.addEventListener("click", () => removeFile(i));

    li.append(thumb, name, rm);
    convFileList.appendChild(li);
  });

  btnConvert.disabled = convFiles.length === 0;
  setConvStatus(convFiles.length ? `${convFiles.length} imagem${convFiles.length > 1 ? "s" : ""} selecionada${convFiles.length > 1 ? "s" : ""}` : "");
}

function setConvStatus(msg, isError = false) {
  convStatus.textContent = msg;
  convStatus.className = "conv-status" + (isError ? " error" : "");
  convStatus.classList.toggle("hidden", !msg);
}

// ── Convert ───────────────────────────────────────────────────────────────
btnConvert.addEventListener("click", async () => {
  if (!convFiles.length) return;

  const combined = document.querySelector('input[name="convFormat"]:checked')?.value === "combined";

  btnConvert.disabled = true;
  setConvStatus("Convertendo...");

  try {
    const form = new FormData();
    convFiles.forEach(f => form.append("files", f));
    form.append("combined", combined);

    const res = await fetch("/api/convert/images-to-pdf", { method: "POST", body: form });

    if (!res.ok) {
      let detail = `Erro ${res.status}`;
      try { const b = await res.json(); detail = b.detail || detail; } catch (_) {}
      throw new Error(detail);
    }

    const blob = await res.blob();
    const filename = combined ? "imagens_combinadas.pdf" : "pdfs_individuais.zip";
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);

    setConvStatus(`Concluído! ${convFiles.length} imagem${convFiles.length > 1 ? "s" : ""} convertida${convFiles.length > 1 ? "s" : ""}.`);
    showToast("Conversão concluída!", "success");

  } catch (e) {
    setConvStatus(e.message, true);
    showToast("Erro na conversão: " + e.message, "error");
  } finally {
    btnConvert.disabled = convFiles.length === 0;
  }
});
