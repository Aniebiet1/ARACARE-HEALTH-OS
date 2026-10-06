const pptxgen = require("pptxgenjs");
const { applyTheme } = require("/root/.claude/skills/synced/1642de46-a867-43b4-80f0-0e5c269bfea9_3aa5b93c-fa03-437c-9717-889c44d6003a/pptx/scripts/apply_theme.js");

const THEME = {
  name: "AraCare",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "0B2E24", lt1: "FFFFFF", dk2: "14513E", lt2: "EEF3F0",
    accent1: "14513E", accent2: "D4A93C", accent3: "3E8E6E", accent4: "9CC5B2",
    accent5: "B5533C", accent6: "6B7F77", hlink: "14513E", folHlink: "6B7F77",
  },
};

const DARK = "0B2E24", MID = "14513E", GREEN = "3E8E6E", MINT = "9CC5B2";
const GOLD = "D4A93C", RUST = "B5533C", INK = "16241F", MUTED = "5B6B64";
const PALE = "EEF3F0", WHITE = "FFFFFF", ONDARK = "E3EEE8";
const HF = "Cambria", BF = "Calibri";

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.theme = { headFontFace: HF, bodyFontFace: BF };
pres.title = "AraCare Health OS: Project Defense";
pres.author = "AraCare";

const W = 10, H = 5.625, MX = 0.6;
let n = 0;

function base(dark, kicker, notes) {
  const s = pres.addSlide();
  n += 1;
  s.background = { color: dark ? DARK : WHITE };
  if (kicker) {
    s.addText(kicker.toUpperCase(), {
      x: MX, y: 0.38, w: 6, h: 0.3, fontFace: BF, fontSize: 11, bold: true,
      color: dark ? GOLD : GREEN, charSpacing: 3, margin: 0, isTextBox: true,
      objectName: "Kicker",
    });
  }
  s.addText("AraCare Health OS", {
    x: MX, y: 5.2, w: 3, h: 0.25, fontFace: BF, fontSize: 10,
    color: dark ? MINT : MUTED, margin: 0, isTextBox: true, objectName: "Footer",
  });
  s.addText(String(n).padStart(2, "0") + " / 10", {
    x: W - MX - 1.2, y: 5.2, w: 1.2, h: 0.25, fontFace: BF, fontSize: 10,
    align: "right", color: dark ? MINT : MUTED, margin: 0, isTextBox: true,
    objectName: "Slide number",
  });
  s.addNotes(notes);
  return s;
}

function title(s, text, dark, o = {}) {
  s.addText(text, {
    x: MX, y: o.y ?? 0.75, w: o.w ?? W - 2 * MX, h: o.h ?? 0.9,
    fontFace: HF, fontSize: o.size ?? 34, bold: true, margin: 0, valign: "top",
    color: dark ? WHITE : DARK, isTextBox: true, objectName: "Title",
  });
}

function body(s, text, dark, o) {
  s.addText(text, {
    x: o.x, y: o.y, w: o.w, h: o.h, fontFace: BF, fontSize: o.size ?? 16,
    color: dark ? ONDARK : INK, margin: 0, valign: "top", italic: !!o.italic,
    paraSpaceAfter: o.gap ?? 0, isTextBox: true, objectName: o.name ?? "Body",
  });
}

function card(s, x, y, w, h, fill, o = {}) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: 0.08, fill: { color: fill },
    line: { color: o.line ?? fill, width: o.line ? 1 : 0 },
    shadow: o.shadow ? { type: "outer", color: "000000", blur: 8, offset: 2, angle: 90, opacity: 0.12 } : undefined,
    objectName: o.name ?? "Card",
  });
}

// ---------------------------------------------------------------- 1 Title
{
  const s = base(true, null,
    "Opening. Frame the question for the panel: anyone who has attended a public hospital in Nigeria knows this experience. The project is AraCare Health OS, a hospital operating system built for Nigerian facilities. State your name, matric number and supervisor.");
  // decorative node network (right)
  const nodes = [[6.3, 1.1], [7.6, 0.8], [8.9, 1.5], [7.0, 2.2], [8.3, 2.7], [9.3, 3.5], [7.4, 3.6], [6.2, 3.1], [8.6, 4.4]];
  const links = [[0, 1], [1, 2], [0, 3], [1, 3], [3, 4], [2, 4], [4, 5], [3, 7], [4, 6], [6, 7], [5, 8], [6, 8]];
  links.forEach(([a, b]) => {
    s.addShape(pres.shapes.LINE, {
      x: Math.min(nodes[a][0], nodes[b][0]), y: Math.min(nodes[a][1], nodes[b][1]),
      w: Math.abs(nodes[a][0] - nodes[b][0]) || 0.001, h: Math.abs(nodes[a][1] - nodes[b][1]) || 0.001,
      line: { color: MID, width: 1.25 },
      flipV: (nodes[a][0] - nodes[b][0]) * (nodes[a][1] - nodes[b][1]) < 0,
      objectName: "Network link",
    });
  });
  nodes.forEach(([x, y], i) => {
    const r = i % 3 === 0 ? 0.17 : 0.11;
    s.addShape(pres.shapes.OVAL, {
      x: x - r, y: y - r, w: 2 * r, h: 2 * r,
      fill: { color: i === 4 ? GOLD : GREEN }, line: { color: DARK, width: 0 }, objectName: "Network node",
    });
  });
  s.addText("PROJECT DEFENSE", {
    x: MX, y: 0.9, w: 5, h: 0.3, fontFace: BF, fontSize: 12, bold: true, color: GOLD,
    charSpacing: 4, margin: 0, isTextBox: true, objectName: "Kicker",
  });
  s.addText("AraCare\nHealth OS", {
    x: MX, y: 1.35, w: 5.6, h: 1.8, fontFace: HF, fontSize: 52, bold: true,
    color: WHITE, margin: 0, valign: "top", isTextBox: true, objectName: "Title",
  });
  s.addText("A hospital operating system built for how Nigerian facilities actually run.", {
    x: MX, y: 3.3, w: 5.2, h: 0.8, fontFace: BF, fontSize: 18, italic: true,
    color: MINT, margin: 0, valign: "top", isTextBox: true, objectName: "Subtitle",
  });
  s.addText("[Your name]  ·  [Matric no.]  ·  Supervisor: [Name]  ·  [Department]", {
    x: MX, y: 4.55, w: 6.2, h: 0.3, fontFace: BF, fontSize: 12, color: ONDARK,
    margin: 0, isTextBox: true, objectName: "Presenter details",
  });
  s.addText("01 / 10", {
    x: W - MX - 1.2, y: 5.2, w: 1.2, h: 0.25, fontFace: BF, fontSize: 10,
    align: "right", color: MINT, margin: 0, isTextBox: true, objectName: "Slide number",
  });
}

// ---------------------------------------------------------------- 2 Queue
{
  const s = base(true, "Part 1  ·  The patient's day",
    "Introduce the composite patient: Mrs. Ngozi, with a feverish child. She arrives before sunrise because she knows what the queue is like. There is no ticket and no order; the queue is whoever pushed in first. Ask the panel to recall their own experience. Note this is a composite scenario used to illustrate the observed problem.");
  title(s, "Before sunrise, the line has formed", true, { w: 4.7, h: 1.1, size: 30 });
  body(s, [
    { text: "Her child has a fever. She joins the line early, because she knows what the day will look like.", options: { breakLine: true } },
    { text: " ", options: { breakLine: true, fontSize: 8 } },
    { text: "There is no ticket, no order and no estimate. Place in line is decided by who pushes in first, and every patient waits without knowing for how long.", options: {} },
  ], true, { x: MX, y: 1.9, w: 4.3, h: 2.4, size: 16 });
  // crowd
  const cols = 8, rows = 4, x0 = 5.55, y0 = 1.0, dx = 0.46, dy = 0.78;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const x = x0 + c * dx + (r % 2) * 0.12, y = y0 + r * dy;
      const tone = (r + c) % 3 === 0 ? GREEN : (r + c) % 3 === 1 ? MID : "1D6B52";
      s.addShape(pres.shapes.OVAL, { x: x + 0.07, y, w: 0.2, h: 0.2, fill: { color: MINT }, line: { color: DARK, width: 0 }, objectName: "Person head" });
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: y + 0.24, w: 0.34, h: 0.36, rectRadius: 0.1, fill: { color: tone }, line: { color: DARK, width: 0 }, objectName: "Person body" });
    }
  }
  card(s, 5.7, 4.2, 3.7, 0.7, "14513E", { name: "Ticket card" });
  s.addText([
    { text: "Queue position:  ", options: { color: ONDARK } },
    { text: "unknown", options: { color: GOLD, bold: true } },
  ], { x: 5.7, y: 4.2, w: 3.7, h: 0.7, fontFace: BF, fontSize: 16, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: "Ticket label" });
}

// ---------------------------------------------------------------- 3 Records
{
  const s = base(true, "Part 1  ·  The patient's day",
    "At the desk, her file cannot be found. With paper records, the file is in a shelf, in another department, or misplaced. The consequence is a new file and a lost history: previous diagnoses, allergies and prescriptions disappear. Point out that this is a patient-safety issue, not only an inconvenience.");
  title(s, "The file cannot be found", true, { w: 4.6, h: 1.1, size: 30 });
  body(s, [
    { text: "A new folder is opened and her history starts again from zero.", options: { breakLine: true } },
    { text: " ", options: { breakLine: true, fontSize: 8 } },
    { text: "Earlier diagnoses, allergies and prescriptions are not available to the clinician at the moment they matter most.", options: {} },
  ], true, { x: MX, y: 1.9, w: 4.2, h: 2.6, size: 16 });
  // folder stack
  const fx = 5.4, fy = 1.1;
  const cols = [MID, GREEN, "1D6B52", MID, GREEN, "1D6B52", MID];
  cols.forEach((c, i) => {
    const y = fy + i * 0.42;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: fx + (i === 3 ? 0.5 : 0), y, w: 3.5, h: 0.52, rectRadius: 0.05, fill: { color: c }, line: { color: DARK, width: 1 }, objectName: "Folder" });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: fx + (i === 3 ? 0.5 : 0) + 0.15, y: y - 0.1, w: 1.0, h: 0.14, rectRadius: 0.04, fill: { color: c }, line: { color: DARK, width: 1 }, objectName: "Folder tab" });
  });
  s.addText("?", { x: fx + 0.5, y: fy + 3 * 0.42, w: 3.5, h: 0.52, fontFace: HF, fontSize: 24, bold: true, color: GOLD, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: "Missing file" });
  card(s, 5.4, 4.2, 3.5, 0.62, "14513E", { name: "Note card" });
  s.addText("Patient history: not available", { x: 5.4, y: 4.2, w: 3.5, h: 0.62, fontFace: BF, fontSize: 15, color: ONDARK, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: "Note label" });
}

// ---------------------------------------------------------------- 4 Power
{
  const s = base(true, "Part 1  ·  The facility's reality",
    "Facilities run on inverters and generators. Power and connectivity fail mid-consultation. This photo is from a real working environment. The design implication: a cloud-only system is not viable here. Whatever we build must keep working on the facility's local network when the internet or power is interrupted.");
  title(s, "Power and network are not guaranteed", true, { w: 5 , h: 1.3, size: 30 });
  body(s, [
    { text: "Facilities depend on inverters and generators.", options: { breakLine: true, bullet: true } },
    { text: "Internet access drops without warning.", options: { breakLine: true, bullet: true } },
    { text: "A system that needs the cloud stops when the connection does.", options: { bullet: true } },
  ], true, { x: MX, y: 2.2, w: 4.2, h: 1.7, size: 16, gap: 8 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: MX, y: 4.1, w: 4.2, h: 0.7, rectRadius: 0.08, fill: { color: MID }, line: { color: GOLD, width: 1 }, objectName: "Requirement card" });
  s.addText([{ text: "Design requirement:  ", options: { color: GOLD, bold: true } }, { text: "keep working offline, on the facility LAN", options: { color: WHITE } }],
    { x: MX + 0.15, y: 4.1, w: 3.9, h: 0.7, fontFace: BF, fontSize: 14, valign: "middle", margin: 0, isTextBox: true, objectName: "Requirement text" });
  s.addImage({ path: "power.png", x: 5.25, y: 0.95, w: 4.15, h: 4.15 * 455 / 715, sizing: { type: "cover", w: 4.15, h: 4.15 * 455 / 715 }, altText: "Inverter and battery unit in a facility room, and a wall-mounted unit with a power plug", objectName: "Power infrastructure photo" });
  s.addText("Power infrastructure at a working site", { x: 5.25, y: 3.7, w: 4.15, h: 0.3, fontFace: BF, fontSize: 11, italic: true, color: MINT, margin: 0, isTextBox: true, objectName: "Photo caption" });
}

// ---------------------------------------------------------------- 5 Doctor
{
  const s = base(true, "Part 1  ·  The consultation",
    "She finally reaches the doctor. The doctor's time is split between the patient and the paperwork. Notes are written by hand, in addition to examining, diagnosing and prescribing. Every minute spent writing is a minute not spent listening. This is the gap the AI scribe addresses later in the deck.");
  title(s, "Writing instead of listening", true, { size: 30 });
  body(s, "Consultation time is limited, and a large share of it goes to documentation.", true, { x: MX, y: 1.7, w: 8.8, h: 0.5, size: 16 });
  const cw = 4.1, ch = 2.2, cy = 2.5;
  card(s, MX, cy, cw, ch, "14513E", { name: "Should card" });
  s.addText("What the visit is for", { x: MX + 0.3, y: cy + 0.2, w: cw - 0.6, h: 0.4, fontFace: HF, fontSize: 18, bold: true, color: GOLD, margin: 0, isTextBox: true, objectName: "Card heading" });
  body(s, [
    { text: "Listen to the history", options: { breakLine: true, bullet: true } },
    { text: "Examine and reason", options: { breakLine: true, bullet: true } },
    { text: "Explain the plan to the patient", options: { bullet: true } },
  ], true, { x: MX + 0.3, y: cy + 0.7, w: cw - 0.6, h: 1.3, size: 15, gap: 6 });
  card(s, MX + cw + 0.6, cy, cw, ch, "1B1F1D", { line: RUST, name: "Reality card" });
  s.addText("What the visit becomes", { x: MX + cw + 0.9, y: cy + 0.2, w: cw - 0.6, h: 0.4, fontFace: HF, fontSize: 18, bold: true, color: "E8A08C", margin: 0, isTextBox: true, objectName: "Card heading" });
  body(s, [
    { text: "Handwrite every note", options: { breakLine: true, bullet: true } },
    { text: "Re-copy details into records", options: { breakLine: true, bullet: true } },
    { text: "Eyes on paper, not on the patient", options: { bullet: true } },
  ], true, { x: MX + cw + 0.9, y: cy + 0.7, w: cw - 0.6, h: 1.3, size: 15, gap: 6 });
}

// ---------------------------------------------------------------- 6 Turning point
{
  const s = base(false, "Part 2  ·  The response",
    "The turning point. Four problems: no queue order, lost records, unreliable infrastructure, documentation burden. AraCare answers each with a module. Walk the flow left to right: Registration and check-in, the queue engine, the electronic health record with triage and SOAP notes, and the AI voice scribe. Billing and pharmacy are designed and have event hooks, but are not built yet; say so honestly.");
  title(s, "One connected system", false, { size: 32 });
  body(s, "Each problem from the patient's day has a matching module.", false, { x: MX, y: 1.5, w: 8.5, h: 0.4, size: 16, name: "Subtitle" });
  const steps = [
    ["1", "Registration", "Check-in and patient identity", "no lost files"],
    ["2", "Queue engine", "Ordered tickets, live status", "no pushing in"],
    ["3", "EHR", "Triage and SOAP notes", "history is kept"],
    ["4", "AI scribe", "Voice to draft note", "less writing"],
  ];
  const bw = 1.95, gap = 0.33, by = 2.3;
  steps.forEach((st, i) => {
    const x = MX + i * (bw + gap);
    card(s, x, by, bw, 2.1, PALE, { name: "Module card" });
    s.addShape(pres.shapes.OVAL, { x: x + 0.2, y: by + 0.2, w: 0.5, h: 0.5, fill: { color: MID }, line: { color: MID, width: 0 }, objectName: "Step badge" });
    s.addText(st[0], { x: x + 0.2, y: by + 0.2, w: 0.5, h: 0.5, fontFace: HF, fontSize: 16, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: "Step number" });
    s.addText(st[1], { x: x + 0.2, y: by + 0.85, w: bw - 0.4, h: 0.35, fontFace: HF, fontSize: 14, bold: true, color: DARK, margin: 0, isTextBox: true, objectName: "Module name" });
    s.addText(st[2], { x: x + 0.2, y: by + 1.2, w: bw - 0.4, h: 0.45, fontFace: BF, fontSize: 12, color: INK, margin: 0, valign: "top", isTextBox: true, objectName: "Module description" });
    s.addText(st[3], { x: x + 0.2, y: by + 1.7, w: bw - 0.4, h: 0.3, fontFace: BF, fontSize: 12, bold: true, italic: true, color: GREEN, margin: 0, isTextBox: true, objectName: "Module outcome" });
    if (i < 3) s.addText("›", { x: x + bw, y: by + 0.7, w: gap, h: 0.5, fontFace: HF, fontSize: 28, bold: true, color: GOLD, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: "Flow arrow" });
  });
  s.addText("Designed, with event hooks in place, not yet built:  Billing  ·  Pharmacy and inventory  ·  Cloud sync", { x: MX, y: 4.65, w: 8.8, h: 0.3, fontFace: BF, fontSize: 12, italic: true, color: MUTED, margin: 0, isTextBox: true, objectName: "Roadmap note" });
}

// ---------------------------------------------------------------- 7 Architecture
{
  const s = base(false, "Part 2  ·  Technical design",
    "Architecture. Clients (reception, nurse, doctor, admin) talk to one FastAPI server per facility. The API is organised into modules: core, registration, queues, EHR and scribe, joined by an internal event system. PostgreSQL in production, SQLite in development, schema managed by Alembic. A WebSocket hub pushes live queue updates. Important caveat: run exactly one API process, because the queue sweeper and WebSocket hub are in-process; scaling out would require Redis pub/sub first.");
  title(s, "One server per facility", false, { size: 32 });
  const lx = MX, lw = 5.6;
  const layers = [
    ["Clients", "Reception  ·  Nurse  ·  Doctor  ·  Admin", PALE, DARK],
    ["FastAPI", "Core · Registration · Queues · EHR · Scribe", MID, WHITE],
    ["Real-time", "Event bus  ·  WebSocket queue updates", GREEN, WHITE],
    ["Data", "PostgreSQL 16 (SQLite in dev) · Alembic", PALE, DARK],
  ];
  layers.forEach((l, i) => {
    const y = 1.55 + i * 0.85;
    card(s, lx, y, lw, 0.7, l[2], { name: "Layer" });
    s.addText(l[0], { x: lx + 0.2, y, w: 1.3, h: 0.7, fontFace: HF, fontSize: 14, bold: true, color: l[3] === WHITE ? GOLD : MID, valign: "middle", margin: 0, isTextBox: true, objectName: "Layer name" });
    s.addText(l[1], { x: lx + 1.5, y, w: lw - 1.65, h: 0.7, fontFace: BF, fontSize: 13, color: l[3], valign: "middle", margin: 0, isTextBox: true, objectName: "Layer detail" });
  });
  const rx = 6.6;
  card(s, rx, 1.55, 2.8, 3.25, PALE, { name: "Decisions card" });
  s.addText("Key decisions", { x: rx + 0.25, y: 1.7, w: 2.3, h: 0.35, fontFace: HF, fontSize: 16, bold: true, color: DARK, margin: 0, isTextBox: true, objectName: "Card heading" });
  body(s, [
    { text: "Runs on the facility LAN, offline-capable", options: { breakLine: true, bullet: true } },
    { text: "Modular, so billing and pharmacy plug in", options: { breakLine: true, bullet: true } },
    { text: "Docker Compose deploy on one server", options: { bullet: true } },
  ], false, { x: rx + 0.25, y: 2.15, w: 2.35, h: 2.5, size: 13, gap: 8 });
}

// ---------------------------------------------------------------- 8 Scribe
{
  const s = base(true, "Part 2  ·  Technical design",
    "The AI voice scribe addresses slide 5. Audio from the consultation is transcribed locally by Whisper through faster-whisper, then a local LLM, Qwen 2.5 7B through Ollama, structures the text into a SOAP note draft. The clinician always reviews and approves the draft. Everything runs on the facility's own machine: no cloud API, no per-call cost, and patient data never leaves the building. Likely examiner question: accuracy with Nigerian accents and clinical terms; answer: the model size is configurable and the clinician review step is the safeguard.");
  title(s, "The AI scribe runs on-site", true, { size: 32 });
  const st = [
    ["Consultation", "Doctor and patient speak"],
    ["Whisper", "Local speech-to-text"],
    ["Local LLM", "Qwen via Ollama drafts a SOAP note"],
    ["Clinician review", "Edit, approve, save to EHR"],
  ];
  const bw = 1.95, gap = 0.33, by = 1.9;
  st.forEach((x, i) => {
    const px = MX + i * (bw + gap);
    const last = i === 3;
    card(s, px, by, bw, 1.5, last ? GOLD : MID, { name: "Pipeline step" });
    s.addText(x[0], { x: px + 0.15, y: by + 0.2, w: bw - 0.3, h: 0.4, fontFace: HF, fontSize: 16, bold: true, color: last ? DARK : WHITE, margin: 0, isTextBox: true, objectName: "Step name" });
    s.addText(x[1], { x: px + 0.15, y: by + 0.65, w: bw - 0.3, h: 0.7, fontFace: BF, fontSize: 13, color: last ? DARK : ONDARK, margin: 0, valign: "top", isTextBox: true, objectName: "Step detail" });
    if (i < 3) s.addText("›", { x: px + bw, y: by + 0.4, w: gap, h: 0.5, fontFace: HF, fontSize: 28, bold: true, color: GOLD, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: "Flow arrow" });
  });
  const pts = [["No cloud API", "no per-call cost"], ["Data stays on-site", "privacy by design"], ["Clinician in control", "draft, never final"]];
  pts.forEach((p, i) => {
    const px = MX + i * 2.95;
    s.addText(p[0], { x: px, y: 3.8, w: 2.7, h: 0.35, fontFace: HF, fontSize: 14, bold: true, color: GOLD, margin: 0, isTextBox: true, objectName: "Benefit" });
    s.addText(p[1], { x: px, y: 4.15, w: 2.7, h: 0.35, fontFace: BF, fontSize: 13, color: ONDARK, margin: 0, isTextBox: true, objectName: "Benefit detail" });
  });
}

// ---------------------------------------------------------------- 9 Evidence
{
  const s = base(false, "Part 2  ·  Reliability and evidence",
    "Evidence that the system is engineered, not just demonstrated. Left: load test of the /predict endpoint. Before the fix throughput stayed flat at about 14 requests per second regardless of concurrency; after the fix it scales to about 139 per second at 40 concurrent requests. Note this endpoint is from the supporting ML service, tested as a separate load test. Right: safeguards in the AraCare backend: 36 automated tests, account lockout after 5 wrong passwords for 15 minutes, forced password change for the first admin, the server refusing to start in production with a weak secret or wildcard CORS, and sessions invalidated on password or role change.");
  title(s, "Engineered to be trusted", false, { size: 32 });
  s.addChart(pres.charts.LINE, [
    { name: "Before fix", labels: ["1", "5", "10", "20", "40"], values: [12, 14, 15, 15, 14] },
    { name: "After fix", labels: ["1", "5", "10", "20", "40"], values: [45, 78, 112, 134, 139] },
  ], {
    x: MX, y: 1.5, w: 5.2, h: 3.5, chartColors: [RUST, MID], lineSize: 3, lineDataSymbolSize: 8,
    showTitle: true, title: "Load test: requests handled per second", titleFontSize: 13, titleColor: DARK, titleFontFace: "+mn-lt",
    showLegend: true, legendPos: "b", legendFontSize: 11, legendColor: INK, legendFontFace: "+mn-lt",
    catAxisLabelColor: MUTED, valAxisLabelColor: MUTED, catAxisLabelFontSize: 11, valAxisLabelFontSize: 11,
    catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
    showCatAxisTitle: true, catAxisTitle: "Concurrent requests", catAxisTitleColor: MUTED, catAxisTitleFontSize: 11, catAxisTitleFontFace: "+mn-lt",
    valGridLine: { color: "D9E2DD", size: 0.75 }, catGridLine: { style: "none" },
    showValue: false,
  });
  const rx = 6.2;
  card(s, rx, 1.5, 3.2, 1.2, DARK, { name: "Stat card" });
  s.addText("36", { x: rx + 0.25, y: 1.55, w: 1.2, h: 1.1, fontFace: HF, fontSize: 48, bold: true, color: GOLD, valign: "middle", margin: 0, isTextBox: true, objectName: "Stat number" });
  s.addText("automated tests covering flow, queue, scribe and security", { x: rx + 1.45, y: 1.55, w: 1.55, h: 1.1, fontFace: BF, fontSize: 12, color: ONDARK, valign: "middle", margin: 0, isTextBox: true, objectName: "Stat label" });
  card(s, rx, 2.9, 3.2, 2.1, PALE, { name: "Safeguards card" });
  s.addText("Safeguards built in", { x: rx + 0.25, y: 3.0, w: 2.7, h: 0.35, fontFace: HF, fontSize: 15, bold: true, color: DARK, margin: 0, isTextBox: true, objectName: "Card heading" });
  body(s, [
    { text: "Role-based access", options: { breakLine: true, bullet: true } },
    { text: "Account lockout after repeated failures", options: { breakLine: true, bullet: true } },
    { text: "Refuses weak secrets in production", options: { breakLine: true, bullet: true } },
    { text: "Versioned database migrations", options: { bullet: true } },
  ], false, { x: rx + 0.25, y: 3.4, w: 2.8, h: 1.55, size: 12, gap: 4 });
}

// ---------------------------------------------------------------- 10 Close
{
  const s = base(true, "Conclusion",
    "Close the loop on Mrs. Ngozi: on her next visit she is registered once, receives a queue position, her history is already on screen, and the doctor can listen while the scribe drafts the note. Then be straightforward about limits: the first release covers registration, queue, EHR and the scribe. Billing, pharmacy and cloud sync are designed but not built. Thank the panel and invite questions. The photo is the developer working on the system locally.");
  title(s, "Her next visit looks different", true);
  const items = [
    ["Registered once", "identity on record"],
    ["Position known", "an ordered, visible queue"],
    ["History on screen", "at the point of care"],
    ["Doctor listens", "the scribe drafts the note"],
  ];
  items.forEach((it, i) => {
    const y = 1.75 + i * 0.68;
    s.addShape(pres.shapes.OVAL, { x: MX, y: y + 0.05, w: 0.4, h: 0.4, fill: { color: GOLD }, line: { color: GOLD, width: 0 }, objectName: "Check badge" });
    s.addText("✓", { x: MX, y: y + 0.05, w: 0.4, h: 0.4, fontFace: BF, fontSize: 14, bold: true, color: DARK, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: "Check mark" });
    s.addText([{ text: it[0], options: { bold: true, color: WHITE, fontFace: HF, fontSize: 16 } }, { text: "   " + it[1], options: { color: MINT, fontFace: BF, fontSize: 13 } }],
      { x: MX + 0.6, y, w: 4.7, h: 0.5, valign: "middle", margin: 0, isTextBox: true, objectName: "Outcome" });
  });
  s.addText("Next:  billing  ·  pharmacy and inventory  ·  cloud sync", { x: MX, y: 4.55, w: 5, h: 0.3, fontFace: BF, fontSize: 12, italic: true, color: MINT, margin: 0, isTextBox: true, objectName: "Roadmap" });
  const pw = 3.5, ph = pw * 0.75;
  s.addImage({ path: "builder.jpg", x: 5.9, y: 1.45, w: pw, h: ph, sizing: { type: "cover", w: pw, h: ph }, altText: "Developer working at a desk with a laptop and handwritten notes", objectName: "Developer photo" });
  s.addText("Thank you. Questions welcome.", { x: 5.9, y: 1.45 + ph + 0.15, w: pw, h: 0.4, fontFace: HF, fontSize: 18, bold: true, color: GOLD, margin: 0, isTextBox: true, objectName: "Closing line" });
}

(async () => {
  await pres.writeFile({ fileName: "AraCare_Defense.pptx" });
  await applyTheme("AraCare_Defense.pptx", THEME);
  console.log("done");
})();
