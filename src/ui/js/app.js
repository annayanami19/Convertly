"use strict";

const $ = (id) => document.getElementById(id);
const api = () => window.pywebview.api;

const state = {
  files: [],      // {path, name, ext, category, targets:[{target,missing}], target}
  tasks: {},      // id → {name, target, status, progress, dst, error}
  deps: null,
  settings: null,
  taskOrder: [],
  presetMode: {},   // kategori -> auto | manual
};

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g,
    (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

let toastTimer = null;
function toast(msg, isErr) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.toggle("err", !!isErr);
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 3200);
}

/* ---------- event bridge dari Python ---------- */
function jlog(msg) {
  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.log("[js] " + msg);
  }
}

window.__onEvent = function (payload) {
  jlog("__onEvent: " + payload.event);
  if (payload.event === "task") onTaskEvent(payload);
  else if (payload.event === "dep_log") appendDepLog(payload.line);
  else if (payload.event === "dep_done") onDepDone(payload);
  else if (payload.event === "files_dropped") {
    jlog("files_dropped diterima: " + (payload.paths || []).length + " path");
    addFiles(payload.paths || []);
  }
};

function onTaskEvent(p) {
  if (!state.tasks[p.id]) state.taskOrder.push(p.id);
  const t = state.tasks[p.id] || (state.tasks[p.id] = {});
  Object.assign(t, p);
  if (p.status === "done") toast("Selesai: " + p.name);
  if (p.status === "error") toast("Gagal: " + p.name + " — " + (p.error || ""), true);
  renderQueue();
}

/* ---------- init ---------- */
window.addEventListener("pywebviewready", init);

async function init() {
  jlog("init: pywebviewready, mulai");
  state.settings = await api().get_settings();
  applyTheme(state.settings.theme || "dark");
  bindUI();
  await refreshDeps(false);
  await restoreSnapshot();
  jlog("init: selesai");
}

async function restoreSnapshot() {
  const snap = await api().snapshot();
  for (const t of snap) {
    if (!state.tasks[t.id]) state.taskOrder.push(t.id);
    state.tasks[t.id] = Object.assign(state.tasks[t.id] || {}, t);
  }
  renderQueue();
}

/* ---------- tema ---------- */
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  $("themeIcon").innerHTML = theme === "dark" ? "&#9789;" : "&#9788;";
  $("themeLabel").textContent = theme === "dark" ? "Dark" : "Light";
  const sel = $("setTheme");
  if (sel) sel.value = theme;
}

async function toggleTheme() {
  const cur = document.documentElement.getAttribute("data-theme");
  const next = cur === "dark" ? "light" : "dark";
  applyTheme(next);
  await api().set_settings({ theme: next });
}

/* ---------- navigasi ---------- */
function bindUI() {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
      btn.classList.add("active");
      $("view-" + btn.dataset.view).classList.add("active");
      if (btn.dataset.view === "history") renderHistory();
      if (btn.dataset.view === "deps") refreshDeps(false);
      if (btn.dataset.view === "settings") fillSettings();
    });
  });
  $("themeToggle").addEventListener("click", toggleTheme);

  // dropzone
  // CATATAN: path file drop tidak pernah ada di JavaScript (WebView2
  // menyembunyikannya) — pywebview menyalurkannya dari sisi Python via
  // event "files_dropped" (lihat main.py _bind_drop + api.on_drop_event).
  const dz = $("dropZone");
  dz.addEventListener("click", () => pickFiles());
  $("btnBrowse").addEventListener("click", (e) => { e.stopPropagation(); pickFiles(); });
  ["dragover", "dragenter"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((ev) =>
    dz.addEventListener(ev, () => {
      dz.classList.remove("drag");
      jlog(ev + " di dropzone fired");
    }));
  // drop di window: hanya logging — Python-side handler yang menangkap path.
  // TETAP preventDefault agar WebView2 tidak membuka file / navigasi.
  ["dragenter", "dragover", "drop"].forEach((ev) =>
    window.addEventListener(ev, (e) => {
      e.preventDefault();
      if (ev === "drop") jlog("drop di WINDOW fired (fileCount=" +
        ((e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) || 0) + ")");
    }));

  $("btnConvert").addEventListener("click", startConvert);
  $("btnClearFiles").addEventListener("click", () => { state.files = []; renderFiles(); });
  $("btnCancelAll").addEventListener("click", async () => { await api().cancel_all(); });
  $("btnClearDone").addEventListener("click", async () => {
    await api().clear_finished();
    // buang task selesai dari state lokal — restoreSnapshot hanya MENAMBAH,
    // tanpa purge ini barisan selesai tetap tampil (tombol terlihat mati)
    state.taskOrder = state.taskOrder.filter((id) => {
      const t = state.tasks[id];
      const keep = t && (t.status === "queued" || t.status === "running");
      if (!keep) delete state.tasks[id];
      return keep;
    });
    renderQueue();
  });
  $("btnDepRefresh").addEventListener("click", () => refreshDeps(true));
  $("btnSaveSettings").addEventListener("click", saveSettings);
  $("btnClearLog").addEventListener("click", async () => {
    await api().clear_logs();
    toast("Log dibersihkan");
  });
  const resetBtn = $("btnResetSettings");
  resetBtn.addEventListener("click", async () => {
    if (resetBtn.dataset.arm !== "1") {
      resetBtn.dataset.arm = "1";
      resetBtn.textContent = "Klik LAGI untuk konfirmasi reset";
      setTimeout(() => {
        resetBtn.dataset.arm = "";
        resetBtn.textContent = "Reset ke Pengaturan Default";
      }, 4000);
      return;
    }
    resetBtn.dataset.arm = "";
    resetBtn.textContent = "Reset ke Pengaturan Default";
    state.settings = await api().reset_settings();
    fillSettings();
    applyTheme(state.settings.theme);
    toast("Pengaturan dikembalikan ke default");
  });
  $("btnPickOut").addEventListener("click", pickOutputDir);
  $("btnOpenOut").addEventListener("click", openOutputFolder);
  const chBtn = $("btnClearHistory");
  chBtn.addEventListener("click", async () => {
    if (chBtn.dataset.arm !== "1") {
      chBtn.dataset.arm = "1";
      chBtn.textContent = "Klik LAGI untuk konfirmasi";
      setTimeout(() => {
        chBtn.dataset.arm = "";
        chBtn.textContent = "Bersihkan Riwayat";
      }, 4000);
      return;
    }
    chBtn.dataset.arm = "";
    chBtn.textContent = "Bersihkan Riwayat";
    await api().clear_history();
    await renderHistory();
    toast("Riwayat dibersihkan");
  });
}

/* ---------- file list ---------- */
async function pickFiles() {
  try {
    const paths = await api().select_files();
    if (paths && paths.length) addFiles(paths);
  } catch (e) {
    toast("Dialog file gagal: " + e, true);
    jlog("select_files error: " + e);
  }
}

async function addFiles(paths) {
  jlog("addFiles: " + paths.length + " path");
  for (const p of paths) {
    if (state.files.some((f) => f.path === p)) continue;
    const ext = (p.match(/\.[^.\\/]+$/) || [""])[0].toLowerCase();
    if (!ext) { toast("Format tidak dikenal: " + p, true); continue; }
    const info = await api().targets_for(ext);
    if (!info.category) { toast("Format tidak didukung: " + ext, true); continue; }
    const f = {
      path: p, name: p.split(/[\\/]/).pop(), ext, category: info.category,
      targets: info.targets, target: "",
    };
    const usable = info.targets.filter((t) => !t.missing.length);
    if (usable.length) f.target = usable[0].target;
    state.files.push(f);
  }
  renderFiles();
}

function renderFiles() {
  const list = $("fileList");
  list.innerHTML = "";
  state.files.forEach((f, i) => {
    const card = document.createElement("div");
    card.className = "file-card";
    const missing = f.targets.filter((t) => t.missing.length);
    const allMissing = usableTargets(f).length === 0;
    card.innerHTML =
      '<span class="chip ' + (allMissing ? "danger" : "") + '">' + esc(f.category) + "</span>" +
      '<span class="file-name">' + esc(f.name) +
        "<small>" + esc(f.path) + "</small></span>" +
      '<select data-i="' + i + '">' + f.targets.map((t) =>
        '<option value="' + esc(t.target) + '"' +
        (t.target === f.target ? " selected" : "") +
        (t.missing.length ? ' disabled title="' + esc("Perlu: " + t.missing.join(", ")) + '"' : "") +
        ">." + esc(t.target) + (t.missing.length ? " (belum terpasang)" : "") +
        "</option>").join("") + "</select>" +
      '<button class="file-remove" data-i="' + i + '" title="Hapus">&#10005;</button>';
    card.querySelector("select").addEventListener("change", (e) => {
      state.files[i].target = e.target.value;
      renderOptions();
    });
    card.querySelector(".file-remove").addEventListener("click", () => {
      state.files.splice(i, 1); renderFiles();
    });
    list.appendChild(card);
  });
  renderOptions();
}

function usableTargets(f) {
  return f.targets.filter((t) => !t.missing.length);
}

function categoriesPresent() {
  return [...new Set(state.files.map((f) => f.category))];
}

/* ---------- panel opsi (preset rekomendasi per target) ---------- */
const PRESETS = {
  images: {
    webp: { quality: 82 },
    jpg:  { quality: 85 },
    jpeg: { quality: 85 },
    avif: { quality: 68 },
    png:  {}, gif: {}, bmp: {}, tiff: {}, ico: {},
  },
  documents: {},  // pdf ops — tidak ada parameter kualitas
  media: {
    mp3:  { audio_bitrate: "192k" },
    aac:  { audio_bitrate: "192k" },
    m4a:  { audio_bitrate: "192k" },
    ogg:  { audio_bitrate: "160k" },
    opus: { audio_bitrate: "128k" },
    flac: {}, wav: {},
    mp4:  { crf: 23, audio_bitrate: "128k" },
    mkv:  { crf: 22, audio_bitrate: "128k" },
    mov:  { crf: 23, audio_bitrate: "128k" },
    webm: { crf: 33, audio_bitrate: "128k" },
    avi:  { audio_bitrate: "128k" },
    gif:  {},
  },
};

const PRESET_NOTE = {
  webp: "kualitas 82 — kompresi terbaik, kualitas nyaris setara asli",
  jpg:  "kualitas 85 — seimbang ukuran/kualitas",
  avif: "kualitas 68 — AVIF paling efisien, kualitas tetap tinggi",
  png:  "lossless — ukuran dioptimalkan tanpa penurunan kualitas",
  mp3:  "192 kbps — umumnya tak terbedakan dari asli",
  m4a:  "192 kbps AAC — seimbang, ramah perangkat Apple/umum",
  ogg:  "160 kbps Vorbis", opus: "128 kbps — efisien untuk musik/suara",
  mp4:  "CRF 23 + audio 128k — standar kualitas baik (x264)",
  mkv:  "CRF 22 + audio 128k — sedikit di atas standar",
  webm: "CRF 33 (VP9) + audio 128k — setara CRF 23 x264",
  mov:  "CRF 23 + audio 128k",
  gif:  "12 fps, lebar 480px — GIF ringan standar",
};

function presetMode(cat) {
  return state.presetMode[cat] || "auto";
}

function presetTargetFor(cat) {
  const f = state.files.find((x) => x.category === cat && x.target);
  return f ? f.target : "";
}

function captureOptValues(cat) {
  const out = {};
  document.querySelectorAll('#optionsBody [data-cat="' + cat + '"] [data-opt]')
    .forEach((el) => {
      out[el.dataset.opt] = el.type === "checkbox" ? el.checked : el.value;
    });
  return out;
}

function restoreOptValues(cat, vals) {
  document.querySelectorAll('#optionsBody [data-cat="' + cat + '"] [data-opt]')
    .forEach((el) => {
      if (!(el.dataset.opt in vals)) return;
      if (el.type === "checkbox") el.checked = !!vals[el.dataset.opt];
      else el.value = vals[el.dataset.opt];
    });
}

function setOptDisabled(cat, disabled) {
  document.querySelectorAll('#optionsBody [data-cat="' + cat + '"] [data-opt]')
    .forEach((el) => { el.disabled = disabled; });
}

function applyPresetValues(cat) {
  const target = presetTargetFor(cat);
  const preset = (PRESETS[cat] && PRESETS[cat][target]) || {};
  document.querySelectorAll('#optionsBody [data-cat="' + cat + '"] [data-opt]')
    .forEach((el) => {
      const k = el.dataset.opt;
      if (!(k in preset)) {
        // kolom di luar rekomendasi dikosongkan — hanya nilai preset yang masuk
        if (el.type === "checkbox") el.checked = false;
        else el.value = "";
        return;
      }
      if (el.type === "checkbox") el.checked = !!preset[k];
      else el.value = preset[k];
    });
  setOptDisabled(cat, true);  // mode rekomendasi = semua input terkunci
  const noteEl = document.querySelector(
    '#optionsBody [data-cat="' + cat + '"] .preset-note');
  if (noteEl) {
    noteEl.textContent = target
      ? ("." + target + " -> " + (PRESET_NOTE[target] ||
         "nilai default yang disarankan") + " (input terkunci)")
      : "pilih format target dulu";
  }
}

// checkbox jenis toggle tampil sebagai chip di baris terpisah,
// bukan di grid kolom — supaya kolom utama selalu lurus
const OPT_TOGGLES = {
  images: [
    optCheck("flip_h", "Flip horizontal"),
    optCheck("flip_v", "Flip vertikal"),
  ],
  documents: [],
  media: [
    optCheck("extract_audio", "Extract audio saja"),
  ],
};

function _optFieldsFor(cat) {
  if (cat === "images") {
    return [
      optNum("quality", "Kualitas (10-95)", 85, 10, 95),
      optNum("resize_pct", "Resize % (kosong = asli)", "", 1, 400),
      optSelect("rotate", "Rotate", [["0","-"],["90","90 deg"],["180","180 deg"],["270","270 deg"]]),
      optText("watermark_text", "Watermark teks"),
    ];
  }
  if (cat === "documents") {
    return [
      optSelect("pdf_op", "Aksi PDF", [
        ["convert", "Konversi format"],
        ["merge", "Merge (semua PDF jadi satu)"],
        ["split", "Split per halaman"],
        ["rotate", "Rotate 90 deg"],
        ["compress", "Kompres"],
        ["extract_text", "Extract teks"],
      ]),
    ];
  }
  if (cat === "media") {
    return [
      optText("trim_start", "Trim mulai (detik, kosong = awal)"),
      optText("trim_end", "Trim akhir (detik, kosong = sampai habis)"),
      optNum("crf", "CRF video (18-32, makin kecil makin bagus)", "", 10, 40),
      optNum("scale_w", "Lebar video px (kosong = asli)", "", 128, 7680),
      optSelect("audio_bitrate", "Bitrate audio", [
        ["", "-"], ["128k", "128k"], ["160k", "160k"], ["192k", "192k"],
        ["256k", "256k"], ["320k", "320k"],
      ]),
    ];
  }
  return [];
}

const CAT_LABEL = { images: "Gambar", documents: "Dokumen", media: "Audio / Video" };

function _sectionHtml(cat) {
  const hasPreset = PRESETS[cat] && Object.keys(PRESETS[cat]).length > 0;
  const toggles = (OPT_TOGGLES[cat] || []).join("");
  return '<div data-cat="' + cat + '">' +
    '<div class="preset-head">' +
      '<span class="preset-title">' + (CAT_LABEL[cat] || cat) + '</span>' +
      (hasPreset
        ? '<label class="opt-check"><input type="checkbox" data-preset-auto checked> ' +
          'Rekomendasi otomatis</label>' +
          '<button type="button" class="btn-ghost small" data-preset-apply>' +
          'Pakai Rekomendasi</button>'
        : "") +
    "</div>" +
    (hasPreset ? '<small class="hint preset-note"></small>' : "") +
    '<div class="opt-group">' + _optFieldsFor(cat).join("") + "</div>" +
    (toggles ? '<div class="opt-toggles">' + toggles + "</div>" : "") +
    "</div>";
}

function renderOptions() {
  const panel = $("optionsPanel");
  const body = $("optionsBody");
  if (!state.files.length) { panel.hidden = true; body.innerHTML = ""; return; }
  panel.hidden = false;
  const cats = categoriesPresent();
  $("optionsCat").textContent = cats.join(" + ");
  $("btnConvert").disabled = state.files.every((f) => !f.target);

  // nilai mode manual dipertahankan lintas re-render
  const saved = {};
  cats.forEach((c) => {
    if (presetMode(c) === "manual") saved[c] = captureOptValues(c);
  });

  body.innerHTML = cats.map((c) => _sectionHtml(c)).join("");

  cats.forEach((c) => {
    const sec = body.querySelector('[data-cat="' + c + '"]');
    if (presetMode(c) === "manual" && saved[c]) {
      restoreOptValues(c, saved[c]);
      setOptDisabled(c, false);
      const cb = sec.querySelector("[data-preset-auto]");
      if (cb) cb.checked = false;
      const noteEl = sec.querySelector(".preset-note");
      if (noteEl) noteEl.textContent = "mode manual — nilai kamu dipertahankan";
    } else if (PRESETS[c] && Object.keys(PRESETS[c]).length > 0) {
      applyPresetValues(c);
    }
    // kategori tanpa preset (documents): input tetap AKTIF — tidak boleh
    // terkunci karena tidak ada checkbox untuk keluar dari mode auto
    const applyBtn = sec.querySelector("[data-preset-apply]");
    if (applyBtn) applyBtn.addEventListener("click", () => {
      state.presetMode[c] = "auto";
      const cb = sec.querySelector("[data-preset-auto]");
      if (cb) cb.checked = true;
      applyPresetValues(c);
    });
    const autoCb = sec.querySelector("[data-preset-auto]");
    if (autoCb) autoCb.addEventListener("change", () => {
      state.presetMode[c] = autoCb.checked ? "auto" : "manual";
      if (autoCb.checked) {
        applyPresetValues(c);
      } else {
        setOptDisabled(c, false);
        const noteEl = sec.querySelector(".preset-note");
        if (noteEl) noteEl.textContent = "mode manual — nilai kamu dipertahankan";
      }
    });
  });
}

function optNum(key, label, val, min, max) {
  return '<label class="opt">' + label +
    '<input type="number" data-opt="' + key + '" value="' + val + '"' +
    (min !== "" ? ' min="' + min + '" max="' + max + '"' : "") + "></label>";
}
function optText(key, label) {
  return '<label class="opt">' + label +
    '<input type="text" data-opt="' + key + '"></label>';
}
function optSelect(key, label, pairs) {
  return '<label class="opt">' + label + '<select data-opt="' + key + '">' +
    pairs.map((p) => "<option value=\"" + p[0] + "\">" + p[1] + "</option>").join("") +
    "</select></label>";
}
function optCheck(key, label) {
  return '<label class="opt opt-check">' +
    '<input type="checkbox" data-opt="' + key + '"> ' + label + "</label>";
}
/* ---------- konversi ---------- */
function readOptions() {
  const o = {};
  document.querySelectorAll("[data-opt]").forEach((el) => {
    const k = el.dataset.opt;
    if (el.type === "checkbox") o[k] = el.checked;
    else o[k] = el.value.trim();
  });
  return o;
}

async function startConvert() {
  const opts = readOptions();
  const items = [];
  const files = state.files.filter((f) => f.target);

  // PDF ops non-convert diterapkan ke PDF pertama (merge = semua PDF)
  const pdfOp = opts.pdf_op && opts.pdf_op !== "convert" ? opts.pdf_op : null;
  if (pdfOp) {
    const pdfs = files.filter((f) => f.ext === ".pdf");
    if (pdfs.length) {
      const base = {};
      if (pdfOp === "rotate") base.degrees = 90;
      items.push({
        src: pdfs[0].path,
        // extract_text menghasilkan TEKS -> target .txt (output name ikut benar);
        // op pdf lain ber-target .pdf (di-whitelist validasi engine)
        target: pdfOp === "extract_text" ? "txt" : "pdf",
        options: Object.assign({ op: pdfOp }, base,
          pdfOp === "merge"
            ? { extra_files: pdfs.slice(1).map((f) => f.path) } : {}),
      });
      for (const f of pdfs) {
        const idx = state.files.indexOf(f);
        if (idx >= 0) state.files.splice(idx, 1);
      }
    }
  }

  for (const f of files) {
    const o = {};
    if (f.category === "images") {
      if (opts.quality) o.quality = opts.quality;
      if (opts.resize_pct) o.resize_pct = opts.resize_pct;
      if (opts.rotate && opts.rotate !== "0") o.rotate = opts.rotate;
      if (opts.flip_h) o.flip_h = true;
      if (opts.flip_v) o.flip_v = true;
      if (opts.watermark_text) o.watermark_text = opts.watermark_text;
    } else if (f.category === "media") {
      if (opts.trim_start) o.trim_start = opts.trim_start;
      if (opts.trim_end) o.trim_end = opts.trim_end;
      if (opts.crf) o.crf = opts.crf;
      if (opts.scale_w) o.scale_w = opts.scale_w;
      if (opts.audio_bitrate) o.audio_bitrate = opts.audio_bitrate;
      if (opts.extract_audio) o.extract_audio = true;
    }
    items.push({ src: f.path, target: f.target, options: o });
  }

  if (!items.length) { toast("Tidak ada task valid", true); return; }
  const res = await api().add_tasks(items);
  // hanya file yang task-nya DITERIMA yang dikeluarkan dari daftar —
  // file yang ditolak (paket belum terpasang dll) tetap tampil
  const addedSrc = new Set((res.added || []).map((t) => t.src));
  state.files = state.files.filter((f) => !addedSrc.has(f.path));
  renderFiles();

  if (res.rejected && res.rejected.length) {
    toast(res.rejected.length + " file ditolak: " +
      res.rejected[0].reason, true);
  }
  renderQueue();
}

/* ---------- antrian ---------- */
function renderQueue() {
  const panel = $("queuePanel");
  const list = $("queueList");
  const ids = state.taskOrder.filter((id) => state.tasks[id]);
  if (!ids.length) { panel.hidden = true; list.innerHTML = ""; return; }
  panel.hidden = false;
  list.innerHTML = ids.map((id) => {
    const t = state.tasks[id];
    const pct = t.status === "done" ? 100 : (t.progress || 0);
    return '<div class="q-item">' +
      '<span class="q-name">' + esc(t.name) + ' &rarr; .' + esc(t.target) + "</span>" +
      (t.status === "running"
        ? '<span class="q-bar"><div style="width:' + pct + '%"></div></span>'
        : "") +
      '<span class="q-status ' + esc(t.status) + '">' + esc(t.status) + "</span>" +
      (t.status === "queued" || t.status === "running"
        ? '<button class="q-cancel" data-id="' + esc(id) + '">&#10005;</button>'
        : "") +
      (t.status === "done"
        ? '<button class="q-cancel" data-open="' + esc(t.dst || "") + '" title="Buka">&#8674;</button>'
        : "") +
      (t.status === "error"
        ? '<span class="h-err" title="' + esc(t.error || "") + '">!</span>'
        : "") +
      "</div>";
  }).join("");
  list.querySelectorAll("[data-id]").forEach((b) =>
    b.addEventListener("click", async () => { await api().cancel(b.dataset.id); }));
  list.querySelectorAll("[data-open]").forEach((b) =>
    b.addEventListener("click", async () => {
      const p = b.dataset.open;
      if (p) await api().open_path(p);
    }));
}

/* ---------- dependencies ---------- */
const FEATURE_LABEL = { images: "Gambar", documents: "Dokumen", media: "Audio / Video" };

async function refreshDeps(showToast) {
  state.deps = await api().get_deps();
  renderDeps();
  const notReady = Object.entries(state.deps)
    .filter(([, v]) => !v.ready).map(([k]) => k);
  const badge = $("navDepBadge");
  badge.hidden = !notReady.length;
  badge.textContent = String(notReady.length);
  if (showToast) {
    toast(notReady.length
      ? "Belum siap: " + notReady.map((k) => FEATURE_LABEL[k]).join(", ")
      : "Semua dependencies siap");
  }
}

function renderDeps() {
  const wrap = $("depsList");
  if (!state.deps) { wrap.innerHTML = '<div class="dep-empty">Memuat...</div>'; return; }
  wrap.innerHTML = Object.entries(state.deps).map(([feature, d]) => {
    const pkgs = d.packages.map((p) => {
      const name = p.label || p.pip;
      const status = p.installed
        ? '<span class="badge ok">terpasang' +
          (p.version ? " " + esc(p.version) : "") + "</span>"
        : (p.required
          ? '<span class="badge no">belum terpasang</span>'
          : '<span class="badge opt">opsional</span>');
      const btn = !p.installed && p.pip
        ? '<button class="btn-install" data-pip="' + esc(p.pip) + '">Install</button>'
        : "";
      return '<div class="dep-pkg"><span class="name">' + esc(name) +
        (p.required ? "" : ' <small style="color:var(--text-dim)">(' +
          esc(p.label || "") + ')</small>') + "</span>" +
        '<span class="ver">' + esc(p.version || p.path || "") + "</span>" +
        status + btn + "</div>";
    }).join("");
    const head =
      '<span class="chip ' + (d.ready ? "" : "danger") + '">' +
        esc(FEATURE_LABEL[feature] || feature) + "</span>" +
      (d.ready ? '<span class="badge ok">siap</span>'
               : '<span class="badge no">fitur disabled — install dulu</span>');
    const note = feature === "media" && !d.ready
      ? '<div class="dep-note">ffmpeg bukan paket pip — jalankan di PowerShell: ' +
        '<span class="dep-cmd" data-cmd="winget install --id Gyan.FFmpeg -e">' +
        "winget install --id Gyan.FFmpeg -e</span> (klik untuk copy), " +
        "lalu restart aplikasi / klik Refresh.</div>"
      : "";
    return '<div class="dep-feature glass"><div class="dep-feature-head">' +
      head + "</div>" + pkgs + note + "</div>";
  }).join("");

  wrap.querySelectorAll("[data-pip]").forEach((b) =>
    b.addEventListener("click", async () => {
      $("depLogPanel").hidden = false;
      $("depLog").textContent = "> pip install " + b.dataset.pip + "\n";
      const res = await api().install_deps([b.dataset.pip]);
      if (!res.started) toast(res.reason || "Install gagal dimulai", true);
      b.disabled = true;
    }));
  wrap.querySelectorAll("[data-cmd]").forEach((el) =>
    el.addEventListener("click", () => {
      navigator.clipboard.writeText(el.dataset.cmd).then(
        () => toast("Command di-copy"),
        () => toast("Gagal copy", true));
    }));
}

function appendDepLog(line) {
  const pre = $("depLog");
  pre.textContent += line + "\n";
  pre.scrollTop = pre.scrollHeight;
}

async function onDepDone(payload) {
  appendDepLog(payload.code === 0
    ? "--- selesai, sukses ---" : "--- selesai dengan error ---");
  state.deps = payload.status;
  renderDeps();
  const notReady = Object.entries(state.deps)
    .filter(([, v]) => !v.ready).length;
  const badge = $("navDepBadge");
  badge.hidden = !notReady;
  badge.textContent = String(notReady);
  toast(payload.code === 0 ? "Install sukses — fitur aktif kembali"
    : "Install gagal — lihat log", payload.code !== 0);
  // refresh daftar file supaya format yang tadinya disabled aktif
  for (const f of state.files) {
    const info = await api().targets_for(f.ext);
    f.targets = info.targets;
    if (!f.target || f.targets.some((t) => t.target === f.target && t.missing.length)) {
      const usable = f.targets.filter((t) => !t.missing.length);
      f.target = usable.length ? usable[0].target : "";
    }
  }
  renderFiles();
}

/* ---------- riwayat & settings ---------- */
async function renderHistory() {
  const cfg = await api().get_settings();
  const wrap = $("historyList");
  const hist = cfg.history || [];
  if (!hist.length) {
    wrap.innerHTML = '<div class="h-empty">Belum ada riwayat konversi.</div>';
    return;
  }
  wrap.innerHTML = hist.map((h) =>
    '<div class="h-item"><span class="h-time">' + esc(h.time || "") + "</span>" +
    '<span class="h-src">' + esc(h.src) + ' &rarr; .' + esc(h.target) +
      ' <small style="color:var(--text-dim)">' + esc(h.dst || "") + "</small></span>" +
    (h.status === "done"
      ? '<span class="h-ok">sukses</span>'
      : '<span class="h-err" title="' + esc(h.error || "") + '">gagal</span>') +
    "</div>").join("");
}

async function openOutputFolder() {
  const cfg = await api().get_settings();
  let dir = cfg.output_dir;
  if (!dir && cfg.history && cfg.history.length && cfg.history[0].dst) {
    dir = cfg.history[0].dst.replace(/[\\/][^\\/]+$/, "");
  }
  if (!dir) { toast("Belum ada folder output — konversi dulu atau set di Settings", true); return; }
  await api().open_path(dir);
}

async function pickOutputDir() {
  try {
    const dir = await api().select_folder();
    if (dir) $("setOutDir").value = dir;
  } catch (e) {
    toast("Dialog folder gagal: " + e, true);
  }
}

function fillSettings() {
  const s = state.settings || {};
  api().get_log_path().then((p) => { $("setLogPath").value = p || ""; });
  $("setTheme").value = s.theme || "dark";
  $("setWorkers").value = s.workers || 2;
  $("setOutDir").value = s.output_dir || "";
  $("setPattern").value = s.naming_pattern || "{name}";
  $("setOverwrite").checked = !!s.overwrite;
  $("setQuality").value = s.default_quality || 85;
}

async function saveSettings() {
  const patch = {
    theme: $("setTheme").value,
    workers: Math.max(1, Math.min(8, parseInt($("setWorkers").value, 10) || 2)),
    output_dir: $("setOutDir").value.trim(),
    naming_pattern: $("setPattern").value.trim() || "{name}",
    overwrite: $("setOverwrite").checked,
    default_quality: Math.max(10, Math.min(95, parseInt($("setQuality").value, 10) || 85)),
  };
  state.settings = await api().set_settings(patch);
  applyTheme(state.settings.theme);
  toast("Settings tersimpan");
}
