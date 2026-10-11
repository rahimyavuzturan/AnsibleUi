/* AnsibleUI — teknik onizleme istemcisi.
 *
 * Guvenlik notu: depo icerigi guvenilmez metin kabul edilir. DOM her zaman
 * createElement + textContent ile kurulur; innerHTML kullanilmaz (XSS).
 */

const $ = (id) => document.getElementById(id);

const state = {
  summary: null,
  documents: [],
  activePath: null,
  activeNodeId: null,
};

/* ---------------------------------------------------------------- yardim */

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function tr(count) {
  return new Intl.NumberFormat("tr-TR").format(count);
}

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body && body.error && body.error.message) message = body.error.message;
    } catch (_) { /* yanit JSON degil */ }
    throw new Error(message);
  }
  return response.json();
}

function showNotice(message) {
  const box = $("notice");
  box.textContent = message;
  box.hidden = false;
}

/* --------------------------------------------------------- gostergeler */

const KIND_LABEL = {
  playbook: "Playbook",
  task_list: "Görev listesi",
  pipeline: "Pipeline",
  vars: "Değişken",
  config: "Yapılandırma",
  empty: "Boş",
  unparsed: "Bozuk",
};

function renderKpis(summary) {
  const kinds = summary.kind_counts || {};
  const lockedPct = summary.param_count
    ? Math.round((summary.locked_param_count / summary.param_count) * 100)
    : 0;

  const cards = [
    { value: tr(summary.file_count), label: "YAML dosyası tarandı", cls: "" },
    { value: tr(kinds.playbook || 0), label: "Playbook", cls: "" },
    { value: tr(summary.node_count), label: "Görsel düğüm çıkarıldı", cls: "kpi--accent" },
    { value: tr(summary.role_call_count), label: "Rol çağrısı", cls: "" },
    { value: tr(summary.distinct_role_count), label: "Farklı rol", cls: "" },
    { value: tr(summary.param_count), label: "Düzenlenebilir parametre", cls: "kpi--accent" },
    { value: `%${100 - lockedPct}`, label: "Parametre forma uygun", cls: "" },
    { value: tr(summary.broken_files.length), label: "Bozuk dosya tespit edildi", cls: "kpi--muted" },
  ];

  const host = $("kpis");
  host.replaceChildren();
  for (const card of cards) {
    const box = el("div", `kpi ${card.cls}`.trim());
    box.append(el("div", "kpi__value", card.value), el("div", "kpi__label", card.label));
    host.append(box);
  }
}

/* -------------------------------------------------------- dosya listesi */

function visibleDocuments() {
  const term = $("search").value.trim().toLowerCase();
  const onlyEditable = $("onlyEditable").checked;
  return state.documents.filter((doc) => {
    if (onlyEditable && !doc.editable) return false;
    return !term || doc.path.toLowerCase().includes(term);
  });
}

function renderFileList() {
  const docs = visibleDocuments();
  const list = $("filelist");
  list.replaceChildren();

  $("fileCount").textContent = `${tr(docs.length)} dosya`;

  for (const doc of docs.slice(0, 400)) {
    const button = el("button", null);
    button.type = "button";
    button.setAttribute("aria-current", String(doc.path === state.activePath));
    button.append(
      el("span", "filelist__name", doc.name),
      el("span", "filelist__dir", doc.directory),
      el("span", "filelist__meta",
        `${KIND_LABEL[doc.kind] || doc.kind} · ${tr(doc.node_count)} düğüm`)
    );
    button.addEventListener("click", () => selectDocument(doc.path));
    const item = el("li");
    item.append(button);
    list.append(item);
  }

  if (docs.length > 400) {
    const more = el("li");
    more.append(el("div", "filelist__meta", `…ve ${tr(docs.length - 400)} dosya daha. Aramayı daraltın.`));
    list.append(more);
  }
}

/* --------------------------------------------------------------- canvas */

function paramRow(param) {
  const row = el("div", `param${param.locked ? " param--locked" : ""}`);
  const name = el("div", "param__name", param.name);
  if (param.locked) {
    const tag = el("span", "tag tag--lock", "kilitli");
    tag.title = param.lock_reason;
    name.append(tag);
  } else if (param.templated) {
    const tag = el("span", "tag tag--tpl", "{{ }}");
    tag.title = "Jinja değişkeni içerir; düzenlenebilir";
    name.append(tag);
  }
  row.append(name, el("div", "param__value", param.value));
  return row;
}

function keywordRow(keyword) {
  const row = el("div", "param");
  const name = el("div", "param__name", keyword.name);
  name.append(el("span", "tag tag--kw", "koşul"));
  row.append(name, el("div", "param__value", keyword.value));
  return row;
}

function subtitleFor(node) {
  if (node.type === "role" && node.role_name) {
    return node.tasks_from
      ? [`rol: `, node.role_name, ` · görev dosyası: ${node.tasks_from}`]
      : [`rol: `, node.role_name];
  }
  if (node.type === "task_include" && node.include_target) return ["hedef: ", node.include_target];
  if (node.type === "module" && node.module) return ["modül: ", node.module];
  if (node.type === "play") return ["oynatma", ""];
  return null;
}

function renderNode(node) {
  const card = el("article", `node node--${node.type}`);
  card.tabIndex = 0;
  card.dataset.nodeId = node.id;
  card.dataset.start = node.line_start;
  card.dataset.end = node.line_end;

  const head = el("div", "node__head");
  head.append(el("span", `chip chip--${node.type}`, node.type));
  head.append(el("span", "node__title", node.name));
  if (node.register_var) {
    const reg = el("span", "tag tag--tpl", `register: ${node.register_var}`);
    reg.title = "Sonraki görevler bu değişkene bağımlı olabilir";
    head.append(reg);
  }
  head.append(el("span", "node__lines",
    node.line_start === node.line_end ? `satır ${node.line_start}` : `satır ${node.line_start}–${node.line_end}`));
  card.append(head);

  const sub = subtitleFor(node);
  if (sub) {
    const line = el("div", "node__sub", sub[0]);
    if (sub[1]) line.append(el("code", null, sub[1]));
    if (sub[2]) line.append(document.createTextNode(sub[2]));
    card.append(line);
  }

  if (node.locked && node.lock_reason) {
    card.append(el("div", "node__lock", `Kilitli — ${node.lock_reason}`));
  }

  if (node.params.length || node.keywords.length) {
    const params = el("div", "params");
    node.params.forEach((p) => params.append(paramRow(p)));
    node.keywords.forEach((k) => params.append(keywordRow(k)));
    card.append(params);
  }

  if (node.children.length) {
    const kids = el("div", "children");
    node.children.forEach((child) => kids.append(renderNode(child)));
    card.append(kids);
  }

  const activate = (event) => {
    event.stopPropagation();
    highlightNode(card, node);
  };
  card.addEventListener("click", activate);
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); activate(event); }
  });

  return card;
}

function highlightNode(card, node) {
  document.querySelectorAll(".node[aria-current='true']")
    .forEach((n) => n.setAttribute("aria-current", "false"));
  card.setAttribute("aria-current", "true");
  state.activeNodeId = node.id;
  highlightLines(node.line_start, node.line_end);
}

/* --------------------------------------------------------------- kaynak */

function renderSource(text) {
  const host = $("source");
  host.replaceChildren();
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  lines.forEach((content, index) => {
    const row = el("div", "srcline");
    row.dataset.line = index + 1;
    row.append(el("span", "srcline__no", index + 1), el("span", "srcline__text", content));
    host.append(row);
  });
}

function highlightLines(start, end) {
  const host = $("source");
  host.querySelectorAll(".srcline--hit").forEach((row) => {
    row.classList.remove("srcline--hit", "srcline--first", "srcline--last");
  });
  let first = null;
  for (let line = start; line <= end; line += 1) {
    const row = host.querySelector(`.srcline[data-line="${line}"]`);
    if (!row) continue;
    row.classList.add("srcline--hit");
    if (line === start) { row.classList.add("srcline--first"); first = row; }
    if (line === end) row.classList.add("srcline--last");
  }
  if (first) first.scrollIntoView({ block: "center", behavior: "smooth" });
}

/* ------------------------------------------------------------- yukleme */

async function selectDocument(path) {
  state.activePath = path;
  renderFileList();

  const canvas = $("canvas");
  canvas.replaceChildren(el("p", "empty", "Ayrıştırılıyor…"));

  let view;
  try {
    view = await getJson(`/api/preview/document?path=${encodeURIComponent(path)}`);
  } catch (error) {
    canvas.replaceChildren(el("p", "empty", `Dosya açılamadı: ${error.message}`));
    return;
  }

  $("docTitle").textContent = view.path;
  $("docMeta").textContent =
    `${KIND_LABEL[view.kind] || view.kind} · ${tr(view.node_count)} düğüm`;
  $("srcMeta").textContent = `${tr(view.line_count)} satır`;

  renderSource(view.text);

  canvas.replaceChildren();
  if (view.parse_error) {
    canvas.append(el("div", "node node--raw",
      `Bu dosya ayrıştırılamıyor: ${view.parse_error}`));
  }
  if (!view.nodes.length && !view.parse_error) {
    canvas.append(el("p", "empty",
      "Bu dosya Ansible playbook'u veya görev listesi değil; salt okunur gösterilir."));
  }
  view.nodes.forEach((node) => canvas.append(renderNode(node)));
}

function pickInitialDocument() {
  const preferred = state.documents.find((doc) => doc.editable && doc.node_count >= 8
    && doc.path.startsWith("playbooks/"));
  const fallback = state.documents.find((doc) => doc.editable);
  const chosen = preferred || fallback;
  if (chosen) selectDocument(chosen.path);
}

async function boot() {
  try {
    const summary = await getJson("/api/preview/summary");
    state.summary = summary;
    state.documents = summary.documents;

    $("repoPill").textContent = `depo: ${summary.repo_name}`;
    $("buildInfo").textContent =
      `${tr(summary.file_count)} dosya · ${tr(summary.node_count)} düğüm · ` +
      `${tr(summary.raw_node_count)} tanınmayan düğüm`;

    renderKpis(summary);
    renderFileList();
    pickInitialDocument();
  } catch (error) {
    showNotice(`Depo okunamadı: ${error.message}`);
    $("repoPill").textContent = "depo yok";
  }

  $("search").addEventListener("input", renderFileList);
  $("onlyEditable").addEventListener("change", renderFileList);
}

boot();
