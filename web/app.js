// Exam Buddy front end. Every Sarvam call goes through our server (/api/...), so the browser never sees a key.

const $ = (id) => document.getElementById(id);
const NATIVE = {
  "en-IN": "English", "hi-IN": "हिंदी", "te-IN": "తెలుగు", "ta-IN": "தமிழ்", "kn-IN": "ಕನ್ನಡ", "ml-IN": "മലയാളം",
  "mr-IN": "मराठी", "bn-IN": "বাংলা", "gu-IN": "ગુજરાતી", "pa-IN": "ਪੰਜਾਬੀ", "od-IN": "ଓଡ଼ିଆ",
};
const MAX_RECORD_MS = 25000;            // Saaras accepts up to 30 s per request
const RING = 2 * Math.PI * 52;          // exam countdown circle
const DONUT = 2 * Math.PI * 50;         // results circle
const VERDICT = { correct: "Correct", partial: "Partly correct", incorrect: "Not quite", skipped: "Skipped" };

let quiz = null, question = null, pendingNext = null, lastForm = null, pickedFile = null;
let player = null, recorder = null, chunks = [], recordTimer = null, meter = null;
let qInterval = null, qDeadline = 0;

// ---------- helpers ----------
const show = (id, on = true) => { $(id).hidden = !on; };
function banner(text) { $("banner").textContent = text || ""; show("banner", !!text); if (text) $("banner").scrollIntoView({ behavior: "smooth", block: "center" }); }
const fmt = (s) => { s = Math.max(0, Math.ceil(s)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
const radio = (name) => document.querySelector(`input[name=${name}]:checked`).value;
function form(fields) { const f = new FormData(); for (const [k, v] of Object.entries(fields)) if (v != null) f.append(k, v); return f; }

async function api(path, body) {
  const res = await fetch(path, { method: "POST", body });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Something went wrong (${res.status}). Please try again.`);
  return data;
}

function play(b64) {
  if (player) { player.pause(); player = null; }
  $("replay").classList.remove("playing");
  if (!b64) return;
  player = new Audio("data:audio/wav;base64," + b64);
  player.onplay = () => $("replay").classList.add("playing");
  player.onended = player.onpause = () => $("replay").classList.remove("playing");
  player.play().catch(() => {}); // autoplay may be blocked; the Repeat button still works
}

// ---------- setup ----------
async function init() {
  const cfg = await (await fetch("/api/config")).json();
  const order = ["en-IN", "hi-IN", ...Object.keys(cfg.languages).filter((c) => c !== "en-IN" && c !== "hi-IN")];
  for (const code of order) {
    const label = document.createElement("label");
    label.innerHTML = `<input type="radio" name="language" value="${code}"><span></span>`;
    label.querySelector("span").textContent = NATIVE[code] || cfg.languages[code];
    label.title = cfg.languages[code];
    if (code === "en-IN") label.querySelector("input").checked = true;
    $("langs").append(label);
  }
  if (!cfg.sarvam_ready) banner("Add your Sarvam key: copy .env.example to .env, put SARVAM_API_KEY in it, then reload this page.");
  setupLiveAgent(cfg.indus);
}

function pickFile(file) {
  if (!file) return;
  pickedFile = file;
  $("useSample").checked = false;
  $("fileName").textContent = `${file.name} · ${(file.size / 1024).toFixed(0)} KB`;
  const img = $("filePreview");
  if (file.type.startsWith("image/")) { img.src = URL.createObjectURL(file); img.hidden = false; } else img.hidden = true;
  show("fileChip");
}
$("file").addEventListener("change", () => pickFile($("file").files[0]));
const drop = $("drop");
drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") $("file").click(); });
["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", (e) => pickFile(e.dataTransfer.files[0]));
$("clearFile").addEventListener("click", () => { pickedFile = null; $("file").value = ""; show("fileChip", false); });
$("togglePaste").addEventListener("click", () => { show("notesText", $("notesText").hidden); $("notesText").focus(); });
$("notesText").addEventListener("input", () => { if ($("notesText").value.trim()) $("useSample").checked = false; });

function loadingSteps(on) {
  const steps = ["ls1", "ls2", "ls3"];
  show("loading", on);
  steps.forEach((id) => $(id).className = "");
  clearTimeout(loadingSteps.t1); clearTimeout(loadingSteps.t2);
  if (!on) return;
  $("ls1").className = "active";
  loadingSteps.t1 = setTimeout(() => { $("ls1").className = "done"; $("ls2").className = "active"; }, pickedFile ? 6000 : 1200);
  loadingSteps.t2 = setTimeout(() => { $("ls2").className = "done"; $("ls3").className = "active"; }, pickedFile ? 12000 : 3500);
}

async function startQuiz(f) {
  $("start").disabled = true; banner(""); loadingSteps(true);
  try {
    const data = await api("/api/quiz", f);
    quiz = { id: data.session_id, mode: data.mode, language: data.language,
             seconds: data.seconds_per_question, total: data.question.total, verdicts: [] };
    show("setup", false); show("results", false); show("quiz");
    $("modeBadge").textContent = quiz.mode === "exam" ? "⏱ Exam mode" : "💡 Learning mode";
    $("modeBadge").className = `badge ${quiz.mode}`;
    show("hint", quiz.mode === "learn"); show("endExam", quiz.mode === "exam"); show("examRing", quiz.mode === "exam");
    $("dots").innerHTML = "<i></i>".repeat(quiz.total);
    $("app").scrollIntoView({ behavior: "smooth" });
    showQuestion(data.question);
  } catch (e) { banner(e.message); }
  finally { $("start").disabled = false; loadingSteps(false); }
}

$("start").addEventListener("click", () => {
  if (!pickedFile && !$("notesText").value.trim() && !$("useSample").checked) {
    return banner("Add your notes first: upload a file, paste text, or tick the sample notes.");
  }
  const fields = { language: radio("language"), count: radio("count"), mode: radio("mode"),
                   notes_text: $("notesText").value, use_sample: $("useSample").checked ? "true" : "false" };
  lastForm = { fields, file: pickedFile };
  const f = form(fields); if (pickedFile) f.append("file", pickedFile);
  startQuiz(f);
});

// ---------- quiz ----------
function paintDots() {
  [...$("dots").children].forEach((dot, i) => {
    dot.className = quiz.verdicts[i] || (i === (question ? question.number - 1 : -1) ? "current" : "");
  });
}

function showQuestion(q) {
  question = q;
  $("progress").textContent = `Question ${q.number} of ${q.total}`;
  $("topic").textContent = q.topic;
  $("difficulty").textContent = q.difficulty;
  $("questionText").textContent = q.text;
  $("typed").value = "";
  show("feedback", false); show("answerArea"); show("hintText", false); show("working", false);
  for (const id of ["mic", "send", "skip", "hint", "typed", "endExam"]) $(id).disabled = false;
  $("micStatus").textContent = "Tap the mic and answer out loud";
  paintDots();
  play(q.audio);
  if (quiz.mode === "exam") startTimer();
}
$("replay").addEventListener("click", () => question && play(question.audio));

function startTimer() {
  clearInterval(qInterval);
  const limit = quiz.seconds; qDeadline = Date.now() + limit * 1000;
  const tick = () => {
    const left = (qDeadline - Date.now()) / 1000;
    $("ringText").textContent = fmt(left);
    $("ringArc").style.strokeDashoffset = RING * (1 - Math.max(0, left) / limit);
    $("examRing").classList.toggle("low", left <= 15);
    if (left <= 0) {
      clearInterval(qInterval);
      if (recorder && recorder.state === "recording") recorder.stop(); else submitAnswer({ text: "" });
    }
  };
  $("ringArc").style.strokeDasharray = RING;
  tick(); qInterval = setInterval(tick, 250);
}

function busy(on) {
  for (const id of ["mic", "send", "skip", "hint", "typed", "endExam"]) $(id).disabled = on;
  show("working", on);
}

async function submitAnswer({ text = "", audio = null }) {
  clearInterval(qInterval);
  if (player) player.pause();
  busy(true);
  try {
    const f = form({ session_id: quiz.id, text });
    if (audio) f.append("audio", audio, "answer.webm");
    const data = await api("/api/answer", f);
    if (quiz.mode === "exam") {
      quiz.verdicts[question.number - 1] = "done";
      toast("Noted. Next question.");
      if (data.summary) return showResults(data.summary);
      return showQuestion(data.next_question);
    }
    showFeedback(data);
  } catch (e) {
    banner(e.message); busy(false);
    if (quiz.mode === "exam") startTimer();
  }
}

function toast(text) { $("toast").textContent = text; show("toast"); clearTimeout(toast.t); toast.t = setTimeout(() => show("toast", false), 1400); }

function showFeedback(data) {
  const g = data.grade;
  quiz.verdicts[question.number - 1] = g.verdict;
  paintDots();
  show("answerArea", false); show("working", false); show("feedback");
  $("verdict").textContent = data.verdict_text + (data.capped_by_hint ? "  (hint: max ½)" : "");
  $("verdict").className = `verdict v-${g.verdict}`;
  const pts = data.capped_by_hint ? Math.min(g.points, 0.5) : g.points;
  $("pointsPop").textContent = pts === 1 ? "+1 mark" : pts === 0.5 ? "+½ mark" : "";
  $("heard").textContent = data.transcript ? `You said: "${data.transcript}"` : "";
  $("feedbackText").textContent = g.feedback;
  $("correctAnswer").textContent = g.correct_answer;
  $("explanation").textContent = g.explanation;
  $("next").textContent = data.summary ? "See my results" : "Next question →";
  pendingNext = data;
  play(data.feedback_audio);
}
$("next").addEventListener("click", () => {
  if (!pendingNext) return;
  const d = pendingNext; pendingNext = null;
  d.summary ? showResults(d.summary) : showQuestion(d.next_question);
});

$("send").addEventListener("click", () => {
  const text = $("typed").value.trim();
  if (!text) { $("micStatus").textContent = "Type an answer first, or tap the mic."; return; }
  submitAnswer({ text });
});
$("typed").addEventListener("keydown", (e) => { if (e.key === "Enter") $("send").click(); });
$("skip").addEventListener("click", () => submitAnswer({ text: "I don't know" }));

$("hint").addEventListener("click", async () => {
  $("hint").disabled = true;
  try {
    const d = await api("/api/hint", form({ session_id: quiz.id }));
    $("hintText").textContent = d.hint; show("hintText"); play(d.audio);
  } catch (e) { banner(e.message); }
});

$("endExam").addEventListener("click", async () => {
  if (!confirm("End the exam now? Unanswered questions count as skipped.")) return;
  clearInterval(qInterval); busy(true);
  try { showResults((await api("/api/end", form({ session_id: quiz.id }))).summary); }
  catch (e) { banner(e.message); busy(false); }
});

// ---------- microphone ----------
$("mic").addEventListener("click", async () => {
  if (recorder && recorder.state === "recording") { recorder.stop(); return; }
  if (player) player.pause();
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
  catch { $("micStatus").textContent = "Microphone blocked. Allow it in the browser, or type your answer."; return; }
  const type = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
  recorder = new MediaRecorder(stream, type ? { mimeType: type } : undefined);
  chunks = [];
  startMeter(stream);
  const started = Date.now();
  const clock = setInterval(() => { $("micStatus").textContent = `Listening... ${fmt((Date.now() - started) / 1000)}  ·  tap to finish`; }, 250);
  recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
  recorder.onstop = () => {
    clearInterval(clock); clearTimeout(recordTimer); stopMeter();
    stream.getTracks().forEach((t) => t.stop());
    $("mic").classList.remove("recording");
    const blob = new Blob(chunks, { type: "audio/webm" });
    if (blob.size < 1000) { $("micStatus").textContent = "I didn't catch that. Tap the mic and try again."; return; }
    $("micStatus").textContent = "Got it!";
    submitAnswer({ audio: blob });
  };
  recorder.start();
  $("mic").classList.add("recording");
  recordTimer = setTimeout(() => recorder.state === "recording" && recorder.stop(), MAX_RECORD_MS);
});

function startMeter(stream) {
  try {
    const ctx = new AudioContext(); const src = ctx.createMediaStreamSource(stream); const an = ctx.createAnalyser();
    an.fftSize = 256; src.connect(an); const data = new Uint8Array(an.frequencyBinCount);
    const loop = () => {
      an.getByteTimeDomainData(data);
      let peak = 0; for (const v of data) peak = Math.max(peak, Math.abs(v - 128));
      $("micLevel").style.transform = `scale(${1 + Math.min(peak / 60, 0.45)})`;
      meter.raf = requestAnimationFrame(loop);
    };
    meter = { ctx }; loop();
  } catch { meter = null; }
}
function stopMeter() { if (meter) { cancelAnimationFrame(meter.raf); meter.ctx.close(); meter = null; } $("micLevel").style.transform = "scale(1)"; }

// ---------- results ----------
function showResults(s) {
  clearInterval(qInterval);
  s.review.forEach((r, i) => { quiz.verdicts[i] = r.verdict; });
  show("quiz", false); show("results");
  $("resultMode").textContent = s.mode === "exam" ? "⏱ Exam review" : "💡 Learning mode";
  $("resultMode").className = `badge ${s.mode}`;
  $("resultTitle").textContent = s.percent >= 80 ? "Brilliant! You're exam-ready." : s.percent >= 50 ? "Good going, a little more revision." : "Let's revise and go again.";
  $("percent").textContent = `${s.percent}%`;
  $("score").textContent = `${s.score} / ${s.total} marks`;
  const arc = $("donutArc");
  arc.style.stroke = s.percent >= 80 ? "var(--ok)" : s.percent >= 50 ? "#f0a12a" : "var(--bad)";
  arc.style.strokeDashoffset = DONUT;
  requestAnimationFrame(() => requestAnimationFrame(() => { arc.style.strokeDashoffset = DONUT * (1 - s.percent / 100); }));
  const tiles = [[s.correct, "correct"], [s.partial, "partly correct"], [s.answered - s.correct - s.partial - s.skipped, "not quite"], [s.skipped, "skipped"]];
  if (s.hints_used) tiles.push([s.hints_used, "hints used"]);
  if (s.late_answers) tiles.push([s.late_answers, "over time"]);
  $("tiles").innerHTML = "";
  for (const [n, label] of tiles) {
    const t = document.createElement("div"); t.className = "tile";
    t.innerHTML = "<b></b><span></span>"; t.firstChild.textContent = n; t.lastChild.textContent = label; $("tiles").append(t);
  }
  $("revise").innerHTML = "";
  if (s.topics_to_revise.length) {
    const lab = document.createElement("b"); lab.textContent = "Revise:"; $("revise").append(lab);
    for (const topic of s.topics_to_revise) { const c = document.createElement("span"); c.className = "chip"; c.textContent = topic; $("revise").append(c); }
  }
  $("review").innerHTML = "";
  for (const r of s.review) {
    const li = document.createElement("li");
    const head = document.createElement("div");
    const badge = document.createElement("span"); badge.className = `verdict v-${r.verdict}`;
    badge.textContent = `${r.number}. ${VERDICT[r.verdict]} · ${r.points === 0.5 ? "½" : r.points} mark${r.points === 1 ? "" : "s"}`;
    head.append(badge);
    const q = document.createElement("p"); q.className = "q"; q.textContent = r.question;
    const yours = document.createElement("p"); yours.className = "yours"; yours.textContent = `You: ${r.your_answer || "(no answer)"}`;
    const ans = document.createElement("p"); ans.textContent = `Answer: ${r.correct_answer}`;
    li.append(head, q, yours, ans);
    if (r.feedback && r.verdict !== "skipped") { const fb = document.createElement("p"); fb.className = "muted"; fb.textContent = r.feedback; li.append(fb); }
    $("review").append(li);
  }
  $("app").scrollIntoView({ behavior: "smooth" });
  if (s.percent >= 80) confetti();
}

function confetti() {
  const box = $("confetti"); box.innerHTML = "";
  const colors = ["#ff8a1f", "#2d2fb3", "#138a57", "#f0a12a", "#7d80ff"];
  for (let i = 0; i < 90; i++) {
    const c = document.createElement("i");
    c.style.left = `${Math.random() * 100}%`; c.style.background = colors[i % colors.length];
    c.style.animationDelay = `${Math.random() * 0.6}s`; c.style.animationDuration = `${1.8 + Math.random() * 1.4}s`;
    box.append(c);
  }
  setTimeout(() => { box.innerHTML = ""; }, 3800);
}

$("again").addEventListener("click", () => { show("results", false); show("setup"); $("app").scrollIntoView({ behavior: "smooth" }); });
$("retryLearn").addEventListener("click", () => {
  if (!lastForm) return;
  const f = form({ ...lastForm.fields, mode: "learn" }); if (lastForm.file) f.append("file", lastForm.file);
  show("results", false); show("setup");
  document.querySelector('input[name=mode][value=learn]').checked = true;
  startQuiz(f);
});

// ---------- live voice agent (Sarvam Indus) ----------
// Our own big button opens Sarvam's call card and presses its call button (the microphone is asked for on this click).
function openLiveCall(widget) {
  const root = widget.shadowRoot;
  if (!root) return;
  const callButton = () => [...root.querySelectorAll("button")].find((b) => /talk to exam buddy/i.test(b.textContent));
  if (callButton()) { callButton().click(); return; }
  const fab = root.querySelector("button");  // the round launcher opens the card first
  if (fab) fab.click();
  setTimeout(() => { const b = callButton(); if (b) b.click(); }, 350);
}

function setupLiveAgent(ids) {
  // the Sarvam widget needs all three IDs; without them, explain instead of showing a broken button
  if (!ids || !ids.app_id || !ids.org_id || !ids.workspace_id) { show("liveOff"); return; }
  const s = document.createElement("script");
  s.src = "https://unpkg.com/sarvam-convai-embed";
  s.onload = () => {
    const w = document.createElement("sarvam-widget");
    let visitor = null;
    try { visitor = sessionStorage.getItem("eb-visitor"); } catch {}
    if (!visitor) { visitor = `student-${Math.random().toString(36).slice(2, 10)}`; try { sessionStorage.setItem("eb-visitor", visitor); } catch {} }
    const attrs = { "session-endpoint": "/api/sarvam/", "app-id": ids.app_id, "org-id": ids.org_id,
                    "workspace-id": ids.workspace_id, "user-id": visitor, "button-text": "Talk to Exam Buddy",
                    "interaction-type": "call" };
    for (const [k, v] of Object.entries(attrs)) if (v) w.setAttribute(k, v);
    $("widgetSlot").append(w);
    show("liveOn");
    $("liveCall").addEventListener("click", () => openLiveCall(w));
    $("heroLive").addEventListener("click", (e) => { e.preventDefault(); $("live").scrollIntoView({ behavior: "smooth" }); openLiveCall(w); });
  };
  s.onerror = () => { $("liveOff").textContent = "The live agent could not load (no internet?). The quiz above still works."; show("liveOff"); };
  document.head.append(s);
}

init();
