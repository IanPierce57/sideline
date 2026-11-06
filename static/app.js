// app.js: runs the show. It sends your topic to the server, plays the pre-show
// while the script is written, counts down, then plays the segment line by line.

const WORDS_PER_MINUTE = 150;
const MIN_SECONDS = 1.2;        // so one-word lines ("Nah.") don't flash past
const MAX_BUBBLE_CHARS = 170;   // longer lines are split into two subtitle cards

const $ = (id) => document.getElementById(id);

const PEOPLE = {
  // Card text is background and personality only. How each one argues shows up on air.
  hal: {
    name: "Hal Brennan", role: "Moderator",
    blurb: "Hosted overnight call-in sports radio for thirty years before Sideline. Calm, warm, and unhurried, he sounds like he's heard every argument before and still enjoys this one.",
    before: "Before Sideline: overnight radio",
  },
  royce: {
    name: "Royce Stanhope", role: "Host · The Columnist",
    blurb: "Grew up in Irving, Texas, close enough to the old Cowboys stadium to hear the crowd on Sundays. Forty years a newspaper columnist, a Cowboys fan for life, and the best-dressed man on set.",
    before: "Before Sideline: newspaper columnist",
  },
  deacon: {
    name: "Deacon Pettiford", role: "Host · Hall of Famer",
    blurb: "Raised by his great-aunt Inez on a South Carolina tobacco farm. Thirteen seasons at linebacker for Kansas City and a spot in the Hall of Fame, but never a ring. Direct, a little loud, and never without a toothpick.",
    before: "Before Sideline: Chiefs linebacker",
  },
  lonnie: {
    name: "Lonnie Fairweather", role: "Host · Former Front Office",
    blurb: "The youngest of six in Duluth, Minnesota, where every sibling picked a different team. Left college eleven credits short for an unpaid NBA video-room job, then spent fifteen years in front offices. Warm, curious, and the calmest man at the desk.",
    before: "Before Sideline: NBA and NFL front offices",
  },
};
const HOSTS = ["royce", "deacon", "lonnie"];
const CALLER_TYPES = {
  diehard: "The diehard", stats_nerd: "The stats nerd", rival_fan: "The rival fan",
  old_timer: "The old-timer", skeptic: "The skeptic", settler: "The settler",
};
const FORMATS = { debate: "WHO'S BETTER?", prediction: "WHO WINS?", buy_or_sell: "BUY OR SELL?",
                  real_or_not: "REAL OR NOT?", rank_em: "RANK 'EM", overrated: "OVERRATED OR UNDERRATED?" };

// ---------- Small helpers for the on-screen graphics ----------

const REDUCED_MOTION = !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
const ACCENTS = { hal: "#c9d2e3", royce: "#f2c14e", deacon: "#e0414e", lonnie: "#5ccfe6",
                  caller: "#f4b740", producer: "#f4b740", artist: "#2fb3a0", crew: "#9aa8d6" };

// The show's state drives the glow behind the TV and the pill in the masthead.
const AIR_TEXT = { idle: "Lines open", preshow: "Pre-show", countdown: "Stand by", live: "On the air", done: "That's the board" };
function setShowMode(mode) {
  document.documentElement.dataset.mode = mode;
  $("air-text").textContent = AIR_TEXT[mode] || "";
}

function setNameplate(name, title, who) {
  const plate = $("nameplate-name").parentElement;
  const changed = $("nameplate-name").textContent !== name;
  $("nameplate-name").textContent = name;
  $("nameplate-title").textContent = title;
  $("phone-name").textContent = name;          // subtitles under the TV on small screens
  plate.style.setProperty("--accent", ACCENTS[who] || "var(--gold)");
  if (changed && !REDUCED_MOTION) { plate.classList.remove("swap"); void plate.offsetWidth; plate.classList.add("swap"); }
}

function setCamera(id, name, info) {
  Studio.portrait($("cam-portrait"), id);
  $("cam-name").textContent = name.toUpperCase();
  $("cam-info").innerHTML = info;
}

function setCenter(topic, foot, big) {
  const el = $("center-topic");
  el.textContent = topic;
  const n = topic.length;
  el.style.fontSize = n <= 30 ? "3.2cqw" : n <= 60 ? "2.6cqw" : n <= 95 ? "2.15cqw" : "1.8cqw";
  el.classList.remove("count");
  if (big) { void el.offsetWidth; el.classList.add("count"); }
  $("center-foot").textContent = foot;
}

// The center monitor's loading animations (monitor.js) during the pre-show.
function monitorAnim(on, step) {
  $("center-mon").classList.toggle("anim", on);
  if (on) Monitor.start(step); else Monitor.stop();
}

function setRight(big, small) {
  $("right-format").textContent = big;
  $("right-source").textContent = small;
}

function setTicker(items) {
  const html = items.map(([label, text]) => {
    const kind = label === "NFL" ? "nfl" : label === "NBA" ? "nba" : "show";
    return `<span class="tag ${kind}">${escapeHtml(label)}</span>${escapeHtml(text)}<span class="gem">&#9670;</span>`;
  }).join("");
  const el = $("ticker");
  el.innerHTML = `<span>${html}</span><span>${html}</span>`;   // two copies so it loops smoothly
  const chars = items.reduce((sum, [a, b]) => sum + a.length + b.length, 0);
  el.style.animationDuration = `${Math.max(25, chars * 0.22)}s`;
}

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}

// The speech bubble floats above whoever is talking, with its tail pointing at them.
let typing = null;
const BUBBLE_NAMES = { hal: "Hal", royce: "Royce", deacon: "Deacon", lonnie: "Lonnie",
                       artist: "Makeup", producer: "Floor producer" };
function showBubble(anchorId, text, revealSeconds = 0) {
  const bubble = $("bubble"), tail = $("tail");
  const tag = $("bubble-name");
  const callerName = anchorId === "caller" && script && script.caller ? `${script.caller.name} from ${script.caller.city}` : "Caller";
  tag.textContent = anchorId === "caller" ? callerName : (BUBBLE_NAMES[anchorId] || "");
  tag.className = "bubble-name " + (["artist", "producer"].includes(anchorId) ? "crew" : anchorId);
  const { x, y } = Studio.anchor(anchorId);
  const xPct = (x / Studio.size.W) * 100;
  bubble.hidden = false;
  bubble.classList.toggle("small", text.length > 120);
  bubble.classList.toggle("tiny", text.length > 165);
  if (anchorId === "caller") {
    // the caller is on the left monitor, so the bubble sits beside it
    bubble.style.left = "31.5%"; bubble.style.bottom = "auto"; bubble.style.top = "9%"; bubble.style.width = "46%";
    tail.className = "tail side";
    tail.style.left = "";
  } else {
    // short lines get a narrower bubble, so they cover less of the set
    const width = text.length <= 45 ? 26 : text.length <= 80 ? 34 : 46;
    // always over the speaker (it may cover part of the stat monitor; the speaker matters more)
    const rightEdge = 98.5;
    const left = Math.min(Math.max(xPct - width / 2, 1.5), rightEdge - width);
    bubble.style.left = `${left}%`;
    bubble.style.width = `${width}%`;
    bubble.style.top = "auto";
    bubble.style.bottom = `${((Studio.size.H - y) / Studio.size.H) * 100 + 2.5}%`;
    tail.className = "tail";
    tail.style.left = `${Math.min(Math.max(((xPct - left) / width) * 100, 6), 94)}%`;
  }
  if (!REDUCED_MOTION) { bubble.classList.remove("pop"); void bubble.offsetWidth; bubble.classList.add("pop"); }
  typeText(text, revealSeconds);
}

function typeText(text, seconds) {
  clearInterval(typing);
  const targets = [$("bubble-text"), $("phone-text")];
  const write = (t) => { for (const el of targets) el.textContent = t; };
  if (!seconds) { write(text); return; }
  const started = performance.now();
  typing = setInterval(() => {
    const k = Math.min(1, (performance.now() - started) / (seconds * 1000));
    write(text.slice(0, Math.ceil(text.length * k)));
    if (k >= 1) clearInterval(typing);
  }, 30);
}

function hideBubble() { clearInterval(typing); $("bubble").hidden = true; }

function setLines(state, text) {
  $("lines").className = `lines ${state}`;
  $("lines-text").textContent = text;
}

function setStatus(message, isError = false) {
  $("status").textContent = message;
  $("status").className = isError ? "console-status error" : "console-status";
}

function setOnAir(on) {
  Studio.setOnAir(on);
  $("bug-live").textContent = on ? "LIVE" : "OFF AIR";
  $("bug-live").classList.toggle("on", on);
}

// ---------- Stat chyron, score meter, and end card ----------

// Count a number up to its value, then show the value exactly as the fact pack has it
// ("1,715", "+0.21", "55.1%"). Anything that isn't a plain number ("8-7") just appears.
const counting = new Map();
function countUp(el, value, ms = 650) {
  clearInterval(counting.get(el));
  const text = String(value);
  const m = text.match(/^([+-]?)([\d,]*\.?\d+)(%?)$/);
  if (!m || REDUCED_MOTION) { el.textContent = text; return; }
  const target = parseFloat(m[2].replace(/,/g, ""));
  const decimals = (m[2].split(".")[1] || "").length;
  const commas = m[2].includes(",");
  const started = performance.now();
  const id = setInterval(() => {
    const k = Math.min(1, (performance.now() - started) / ms);
    if (k >= 1) { el.textContent = text; clearInterval(id); return; }
    const v = (target * (1 - Math.pow(1 - k, 3))).toFixed(decimals);
    el.textContent = m[1] + (commas ? Number(v).toLocaleString("en-US", { minimumFractionDigits: decimals }) : v) + m[3];
  }, 40);
  counting.set(el, id);
}

// A stat from the fact pack: { value, label, definition, source, asOf }.
function showChyron(stat, sample) {
  countUp($("stat-value"), stat.value);
  $("stat-label").textContent = stat.label;
  $("stat-def").textContent = stat.definition;
  $("stat-foot").textContent = `Source: ${stat.source} · ${stat.asOf}`;
  $("stat-sample").hidden = !sample;
  $("right-default").hidden = true;
  const layer = $("right-stat");
  layer.hidden = false;
  layer.style.animation = "none"; void layer.offsetWidth; layer.style.animation = "";   // replay the pop-in
}
function hideChyron() {
  $("right-stat").hidden = true;
  $("right-default").hidden = false;
}

// Scores out of 100, e.g. { royce: 66, deacon: 74 }. Hosts not listed keep their score.
let scores = {};
function setScores(update, sample) {
  Object.assign(scores, update);
  $("scorecard").hidden = false;
  $("score-sample").hidden = !sample;
  const best = Math.max(...HOSTS.map((h) => scores[h] ?? -1));
  for (const host of HOSTS) {
    const value = scores[host];
    const num = $(`num-${host}`), row = num.parentElement;
    const shown = value == null ? "--" : String(Math.round(value));
    if (num.textContent !== shown && value != null) {
      countUp(num, shown, 500);
      row.classList.remove("bump"); void row.offsetWidth; row.classList.add("bump");
    } else if (value == null) num.textContent = "--";
    $(`bar-${host}`).style.width = value == null ? "0" : `${value}%`;
    row.classList.toggle("lead", value != null && value === best);
  }
}
function hideScores() { scores = {}; $("scorecard").hidden = true; }

function showEndCard() {
  const sample = !!script.sample;
  // the meter always ends on the judge's final scores
  if (script.scores && Object.keys(script.scores).length) setScores(script.scores, sample);
  $("end-sample").hidden = !sample;
  $("end-topic").textContent = script.topic;
  const rows = $("end-rows");
  rows.innerHTML = "";
  // Only the winner (changed Nov 6, 2026): his argument and the key stats he used.
  const wc = script.winning_case;
  const winner = (wc && wc.host) || script.winner;
  if (!winner) {
    $("end-label").textContent = script.tie ? "Split decision" : "Final answers";
    $("endcard").hidden = false;
    return;
  }
  $("end-label").textContent = "The winning argument";
  $("endcard").style.setProperty("--accent", ACCENTS[winner] || "var(--gold)");
  Studio.celebrate(winner);
  const row = document.createElement("div");
  row.className = "end-row winner";
  const face = document.createElement("canvas");
  face.width = 32; face.height = 32;
  Studio.portrait(face, winner);
  row.append(face);
  const score = wc && wc.score != null ? `<em class="end-score">${Math.round(wc.score)}</em>`
    : (script.scores && script.scores[winner] != null ? `<em class="end-score">${Math.round(script.scores[winner])}</em>` : "");
  let argument = wc ? spokenText(wc.argument) : "";
  if (!argument) {
    const last = [...script.lines].reverse().find((line) => line.speaker === winner);
    argument = last ? spokenText(last.text) : "";
  }
  row.insertAdjacentHTML("beforeend", `<div class="end-text"><b>${PEOPLE[winner].name} <i class="win-tag">WINNER</i></b>`
    + `<span>${escapeHtml(argument)}</span></div>${score}`);
  rows.append(row);
  const stats = (wc && wc.stats) || [];
  if (stats.length) {
    const box = document.createElement("div");
    box.className = "end-stats";
    for (const st of stats) {
      const chip = document.createElement("div");
      chip.className = "end-stat";
      const value = String(st.say).replace(/\s*\(.*\)\s*$/, "");   // "8-7 (playoffs after...)" -> "8-7"
      chip.innerHTML = `<strong>${escapeHtml(value)}</strong><span>${escapeHtml(st.subject)} · ${escapeHtml(st.label)}`
        + (st.scope ? ` <em>(${escapeHtml(st.scope)})</em>` : "") + `</span>`;
      box.append(chip);
    }
    rows.append(box);
  }
  $("endcard").hidden = false;
}
function hideEndCard() { $("endcard").hidden = true; }

function clearGraphics() { hideChyron(); hideScores(); hideEndCard(); }

// ---------- Desk-slam sound (made in code, no audio file) ----------

let soundOn = true;
let audio = null;
function thump() {
  if (!soundOn) return;
  audio = audio || new (window.AudioContext || window.webkitAudioContext)();
  const now = audio.currentTime;
  const osc = audio.createOscillator();
  const gain = audio.createGain();
  osc.type = "square";
  osc.frequency.setValueAtTime(120, now);
  osc.frequency.exponentialRampToValueAtTime(38, now + 0.18);
  gain.gain.setValueAtTime(0.35, now);
  gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);
  osc.connect(gain).connect(audio.destination);
  osc.start(now);
  osc.stop(now + 0.26);
}
Studio.onSlam(() => {
  const tv = $("tv");
  tv.classList.remove("shake"); void tv.offsetWidth; tv.classList.add("shake");
  thump();
});
$("sound").addEventListener("click", () => {
  soundOn = !soundOn;
  $("sound").textContent = soundOn ? "Sound: on" : "Sound: off";
  $("sound").setAttribute("aria-pressed", String(soundOn));
});

// ---------- The screens: idle, pre-show, countdown, live, done ----------

// While the lines are open: short in-character chatter, and real upcoming games on the
// right-hand monitor. Bubbles are short and brief so they don't sit on the monitors.
const IDLE_CHATTER = [
  ["hal", "Lines are open."],
  ["deacon", "Somebody call in already."],
  ["royce", "Give me something worth arguing about."],
  ["lonnie", "Anybody got a trade idea?"],
  ["deacon", "Quiet night."],
  ["royce", "Bev says I talk too much. She's not wrong."],
  ["lonnie", "NBA, NFL. I'll take anything."],
]
let idleTimer = null, upNextTimer = null, upcoming = { games: [], questions: [] };
function stopIdle() { clearTimeout(idleTimer); clearInterval(upNextTimer); upNextTimer = null; }
function idleChatter(i = 0) {
  const [who, text] = IDLE_CHATTER[i % IDLE_CHATTER.length];
  const person = PEOPLE[who];
  setNameplate(person.name, person.role.replace("Host · ", ""), who);
  showBubble(who, text, 0.6);
  idleTimer = setTimeout(() => {
    hideBubble();
    idleTimer = setTimeout(() => idleChatter(i + 1), 9000);   // mostly quiet; a line every ~12 seconds
  }, 3800);
}
function showUpNext() {
  let k = 0;
  const step = () => {
    const g = upcoming.games[k % Math.max(upcoming.games.length, 1)];
    if (g) setRight("UP NEXT", `${g.league} · ${g.text} · ${g.when}`);
    k += 1;
  };
  step();
  upNextTimer = setInterval(step, 6000);
}
// Hal says something that has to stay readable (a screened call, a dropped line): the
// idle chatter waits 20 seconds before it starts again.
function holdChatter() {
  clearTimeout(idleTimer);
  idleTimer = setTimeout(() => idleChatter(0), 20000);
}

function showIdle() {
  stopIdle();
  Studio.setMode("idle");
  setShowMode("idle");
  monitorAnim(false);
  setOnAir(false);
  clearGraphics();
  setCenter("ASK THE DESK", "NBA · NFL · today's players and teams");
  setRight("TONIGHT", "NBA · NFL · call-in debate");
  setCamera("hal", "Hal Brennan", "Moderator<br><span class=\"gold\">Lines open</span>");
  $("show-tag").textContent = "Sideline";
  setNameplate("Hal Brennan", "Moderator", "hal");
  hideBubble();
  idleTimer = setTimeout(() => idleChatter(0), 1200);
  if (upcoming.games.length) showUpNext();
}

// Try-questions: two from real upcoming games plus three evergreen ones, redrawn every time
// someone asks the desk (changed Nov 6, 2026). The evergreen ones avoid records or streaks
// that would go stale, and cover all six segment types.
const EVERGREEN = [
  "Is Josh Allen the best quarterback in the NFL right now?",
  "Is Shai Gilgeous-Alexander better than Nikola Jokic right now?",
  "Rank the top three quarterbacks in the NFL right now",
  "Rank the top three players in the NBA right now",
  "Is Jalen Hurts overrated?",
  "Is Victor Wembanyama the best defender in basketball?",
  "Are the Thunder still the team to beat in the West?",
  "Should the Bears trade for a pass rusher?",
  "Is Caleb Williams a franchise quarterback?",
  "Who's better right now, Lamar Jackson or Joe Burrow?",
  "Is Puka Nacua the best receiver in football?",
  "Who wins the Super Bowl this season?",
  "Who wins the NBA title this season?",
  "Is Bijan Robinson the best running back in the NFL?",
  "Is Anthony Edwards a better player than Jayson Tatum?",
  "Rank the top three pass rushers in the NFL right now",
  "Is Luka Doncic overrated or underrated?",
  "Are the Lions real Super Bowl contenders?",
  "Who's the best young quarterback in the NFL?",
  "Should the Lakers make a trade before the deadline?",
];
let lastShown = new Set();
let liveTurn = 0;
function chip(text, live) {
  const b = document.createElement("button");
  b.type = "button"; b.className = live ? "chip live" : "chip"; b.textContent = text;
  b.addEventListener("click", () => { $("topic").value = text; $("topic").focus(); });
  return b;
}
function refreshChips() {
  const box = $("examples-live");
  box.innerHTML = "";
  const live = upcoming.questions || [];
  const shown = new Set();
  for (let k = 0; k < Math.min(2, live.length); k += 1) {
    const q = live[(liveTurn + k) % live.length];
    if (shown.has(q)) continue;
    box.append(chip(q, true));
    shown.add(q);
  }
  liveTurn += 2;
  const fresh = EVERGREEN.filter((q) => !lastShown.has(q));
  for (let k = 0; k < 3 && fresh.length; k += 1) {
    const q = fresh.splice(Math.floor(Math.random() * fresh.length), 1)[0];
    box.append(chip(q, false));
    shown.add(q);
  }
  lastShown = shown;
}

// Real upcoming games (from the same schedules the game finder uses): the right-hand
// monitor's "up next" list and the live try-questions.
async function loadUpcoming() {
  try {
    upcoming = await (await fetch("/api/upcoming")).json();
  } catch (error) {
    upcoming = { games: [], questions: [] };
  }
  refreshChips();
  if (Studio && !script && !upNextTimer && upcoming.games.length) showUpNext();
}

let preshowTimer = null;
function showPreshow(topic) {
  stopIdle();
  stopPlayback();
  clearGraphics();
  setPlayButtons(false);
  Studio.setMode("preshow");
  setShowMode("preshow");
  setOnAir(false);
  monitorAnim(true, "start");
  const started = Date.now();
  const tick = () => {
    const s = Math.round((Date.now() - started) / 1000);
    $("center-foot").textContent = `Making your segment · ${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  };
  tick();
  preshowTimer = setInterval(tick, 1000);
  setRight("PRE-SHOW", "On air in a minute or two");
  setCamera("caller", "Line 1", "Caller<br><span class=\"gold\">Holding</span>");
  $("show-tag").textContent = "Pre-show";
}
Studio.onScene((scene) => {
  setNameplate(scene.name, scene.title, scene.who);
  if (scene.text) showBubble(scene.who, scene.text, 0.6);   // most pre-show scenes are silent
  else hideBubble();
});

function countdown() {
  return new Promise((resolve) => {
    clearInterval(preshowTimer);
    Studio.setMode("countdown");
    setShowMode("countdown");
    monitorAnim(false);
    $("center-brand").textContent = "ON AIR IN";
    setNameplate("Floor producer", "Countdown", "producer");
    let n = 3;
    const step = () => {
      if (n === 0) { $("center-brand").textContent = "· SIDELINE ·"; resolve(); return; }
      Studio.setCountdown(n);
      setCenter(String(n), "Quiet on set", true);
      showBubble("producer", n === 3 ? "Quiet on set! We're live in three..." : n === 2 ? "...two..." : "...one.");
      n -= 1;
      setTimeout(step, 1000);
    };
    step();
  });
}

let endTimer = null;
function showDone() {
  Studio.setMode("done");
  setShowMode("done");
  hideChyron();
  setCenter("THAT'S THE BOARD", "Ask the desk another one");
  setNameplate("Hal Brennan", "That's the board", "hal");
  hideBubble();
  setLines("", "Lines are open");
  setStatus("That's the board. Ask the desk another one.");
  $("progress").textContent = "Finished";
  endTimer = setTimeout(() => stinger(() => { setOnAir(false); showEndCard(); }), 900);
}

// ---------- Playing a script ----------

let script = null;
let cards = [];     // subtitle cards: each line, split if it's long
let cardIndex = 0;
let lineTimer = null;
let paused = false;

function spokenText(text) {
  // Stage directions like "(the pencil stops)" drive the animation; they aren't spoken.
  return text.replace(/\([^)]*\)/g, " ").replace(/\s+/g, " ").trim();
}

function secondsFor(text) {
  const words = text ? text.split(/\s+/).length : 0;
  return Math.max(MIN_SECONDS, (words / WORDS_PER_MINUTE) * 60);
}

// Split at real sentence ends: a period, ! or ? followed by a space and a new sentence.
// "0.37" (no space) and abbreviations like "Jr.", "St.", "vs.", "Nov." don't end a sentence.
const ABBREVIATIONS = /(?:^|\s)(?:jr|sr|st|vs|mr|mrs|dr|no|mt|ft|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec|a\.m|p\.m|u\.s)\.$/i;
function sentences(text) {
  const out = [];
  let start = 0;
  const end = /[.!?]+["'’”)\]]*\s+/g;
  let m;
  while ((m = end.exec(text))) {
    const piece = text.slice(start, m.index + m[0].trimEnd().length);
    const next = text[end.lastIndex] || "";
    if (ABBREVIATIONS.test(piece) || !/[A-Z0-9"'“(]/.test(next)) continue;
    out.push(piece.trim());
    start = end.lastIndex;
  }
  if (start < text.length) out.push(text.slice(start).trim());
  return out.filter(Boolean);
}

function buildCards(lines) {
  const out = [];
  let hostHasSpoken = false;
  for (const line of lines) {
    const spoken = spokenText(line.text);
    const parts = sentences(spoken);
    const chunks = [];
    let current = "";
    for (const s of parts.length ? parts : [spoken]) {
      if (current && (current + " " + s).length > MAX_BUBBLE_CHARS) { chunks.push(current); current = s; }
      else current = current ? `${current} ${s}` : s;
    }
    if (current || !chunks.length) chunks.push(current);
    const isCutIn = line.speaker === "hal" && hostHasSpoken;
    if (HOSTS.includes(line.speaker)) hostHasSpoken = true;
    chunks.forEach((text, i) => out.push({ line, text, first: i === 0, isCutIn, seconds: secondsFor(text) }));
  }
  return out;
}

function playCard() {
  if (cardIndex >= cards.length) { Studio.silence(); hideBubble(); showDone(); return; }
  const card = cards[cardIndex];
  const { line } = card;
  if (card.first) {
    Studio.speak(line.speaker, line.delivery, line.text, card.isCutIn);
    // Later pipeline steps attach these to lines: a fact-pack stat, and the judge's scores.
    if (line.stat) showChyron(line.stat, !!script.sample); else hideChyron();
    if (line.score) setScores(line.score, !!script.sample);
  }

  if (line.speaker === "caller") {
    const caller = script.caller;
    setNameplate(`${caller.name} from ${caller.city}`, `On the line · ${CALLER_TYPES[caller.type] || "Caller"}`, "caller");
    setCamera("caller", "Line 1", `${escapeHtml(caller.name)}<br><span class="gold">${escapeHtml(caller.city)}</span>`);
  } else {
    const person = PEOPLE[line.speaker];
    setNameplate(person.name, person.role, line.speaker);
    setCamera(line.speaker, person.name, `${person.role.replace("Host · ", "")}<br><span class="gold">${FORMATS[script.format] || ""}</span>`);
  }
  showBubble(line.speaker, card.text, Math.min(card.seconds * 0.6, card.text.length / 45));
  $("progress").textContent = `LINE ${line.line} / ${script.lines.length}`;
  lineTimer = setTimeout(() => { cardIndex += 1; playCard(); }, card.seconds * 1000);
}

function stopPlayback() {
  clearTimeout(lineTimer);
  clearTimeout(endTimer);
  clearInterval(typing);
  paused = false;
  Studio.setPaused(false);
  $("pause").textContent = "Pause";
}

function setPlayButtons(enabled) {
  $("pause").disabled = !enabled;
  $("replay").disabled = !enabled;
}

// The Sources panel: this segment's receipts (every fact used and what it was checked against).
function showReceipts(s) {
  const box = $("receipts");
  const rows = s.receipts || [];
  if (s.sample || !rows.length) { box.hidden = true; return; }
  const m = s.meta || {};
  $("receipts-summary").textContent =
    `${rows.length} facts on air · ${m.stats_verified ?? "?"} of ${m.stats_found ?? "?"} checked facts kept · `
    + `${m.lines_rewritten ?? 0} lines fixed, ${m.lines_cut ?? 0} cut by the line check`;
  const list = $("receipts-list");
  list.innerHTML = "";
  for (const r of rows) {
    const ok = String(r.status || "").startsWith("verified");
    const check = ok ? `✓ ${r.checked}` : (r.checked || "Trusted source");
    const row = document.createElement("div");
    row.className = "receipt";
    row.innerHTML = `<b>${escapeHtml(r.subject || "")}</b><span>${escapeHtml(r.label || "")}: `
      + `<strong>${escapeHtml(String(r.say || ""))}</strong> <em>(${escapeHtml(r.scope || "")})</em></span>`
      + `<i class="${ok ? "ok" : "trusted"}">${escapeHtml(check)}</i>`;
    list.append(row);
  }
  box.hidden = false;
}

async function play(newScript) {
  stopIdle();
  stopPlayback();
  clearGraphics();
  setPlayButtons(false);
  script = newScript;
  cards = buildCards(script.lines);
  cardIndex = 0;
  showReceipts(script);
  await countdown();
  await stinger(() => {
    Studio.setMode("live");
    setShowMode("live");
    setOnAir(true);
    setLines("live", "On the air");
    const format = FORMATS[script.format] || "DEBATE";
    setCenter(script.topic.toUpperCase(), `Line 1 · ${script.caller.name} from ${script.caller.city}`);
    setRight(format, `Caller: ${script.caller.name}, ${script.caller.city}`);
    const TAGS = { debate: "Who's better", prediction: "Who wins", buy_or_sell: "Buy or sell", real_or_not: "Real or not",
                   rank_em: "Rank 'em", overrated: "Over/under" };
    $("show-tag").textContent = TAGS[script.format] || "Sideline";
    if (script.sample) setScores({}, true);   // the preview shows the meter from the start
  });
  setPlayButtons(true);
  playCard();
}

// ---------- The pipeline strip: how a segment gets made ----------

const PIPE = ["topic", "research", "verify", "write", "check", "judge", "close"];
// How long each step usually takes (seconds), so the bar keeps creeping through a step
// instead of jumping; it never fills a step until the server says that step is done.
const PIPE_EXPECT = { topic: 3, research: 7, verify: 12, write: 50, check: 30, judge: 11, close: 9 };
const PIPE_NAMES = { topic: "Screening the call", research: "Pulling stats", verify: "Checking every number twice",
                     write: "Writing the segment", check: "Checking every line", judge: "Blind judges scoring",
                     close: "The verdict" };
const pipe = { idx: -1, stepAt: 0, startedAt: 0, timer: null };
function clockText(ms) {
  const s = Math.round(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}
function renderPipeline() {
  const box = $("pipeline"), step = PIPE[pipe.idx];
  const frac = Math.min(0.92, 1 - Math.exp(-(Date.now() - pipe.stepAt) / 1000 / PIPE_EXPECT[step]));
  const pct = ((pipe.idx + frac) / PIPE.length) * 100;
  $("pbar-fill").style.width = `${pct}%`;
  $("pbar").setAttribute("aria-valuenow", String(Math.round(pct)));
  $("pipeline-title").textContent = `Step ${pipe.idx + 1} of 7 · ${PIPE_NAMES[step]}`;
  $("pipeline-clock").textContent = clockText(Date.now() - pipe.startedAt);
  box.querySelectorAll(".psteps li").forEach((li, i) => {
    li.classList.toggle("done", i < pipe.idx);
    li.classList.toggle("active", i === pipe.idx);
  });
}
function setPipeline(step, startedAt) {
  const box = $("pipeline");
  const idx = PIPE.indexOf(step === "start" ? "topic" : step);
  if (idx < 0) {                                       // back to the explainer
    clearInterval(pipe.timer); pipe.timer = null; pipe.idx = -1;
    box.classList.remove("running", "complete");
    $("pbar-fill").style.width = "0";
    $("pipeline-title").textContent = "How a segment gets made: 7 steps, about a minute and a half";
    $("pipeline-clock").textContent = "";
    box.querySelectorAll(".psteps li").forEach((li) => li.classList.remove("done", "active"));
    return;
  }
  if (startedAt) pipe.startedAt = startedAt;
  if (idx !== pipe.idx) { pipe.idx = idx; pipe.stepAt = Date.now(); }
  box.classList.add("running"); box.classList.remove("complete");
  if (!pipe.timer) pipe.timer = setInterval(renderPipeline, 200);
  renderPipeline();
}
function pipelineDone() {
  const box = $("pipeline");
  clearInterval(pipe.timer); pipe.timer = null;
  box.classList.remove("running"); box.classList.add("complete");
  $("pbar-fill").style.width = "100%";
  $("pipeline-title").textContent = `Made and checked in ${clockText(Date.now() - pipe.startedAt)}`;
  $("pipeline-clock").textContent = "";
  box.querySelectorAll(".psteps li").forEach((li) => { li.classList.add("done"); li.classList.remove("active"); });
}

// ---------- The broadcast wipe ----------

// Red, gold, and navy bars sweep across with the logo. onCovered runs while the screen is
// covered, so the switch to the show (or the end card) happens behind it.
function stinger(onCovered) {
  return new Promise((resolve) => {
    if (REDUCED_MOTION) { onCovered(); resolve(); return; }
    const el = $("stinger");
    el.hidden = false;
    el.classList.remove("play"); void el.offsetWidth; el.classList.add("play");
    setTimeout(onCovered, 480);
    setTimeout(() => { el.hidden = true; el.classList.remove("play"); resolve(); }, 1250);
  });
}

// ---------- Asking the desk ----------

// The pre-show's control room shows what the pipeline is really doing.
const STEP_NAMES = { start: "ON THE LINE", topic: "SCREENING", research: "PULLING STATS",
                     verify: "CHECKING STATS", write: "WRITING", check: "LINE CHECK",
                     judge: "JUDGE SCORING", close: "THE VERDICT" };
function showControlRoom(job) {
  const c = job.counts || {};
  const step = job.step || {};
  let detail = `Stats found ${c.found || 0} · verified ${c.verified || 0} · dropped ${c.dropped || 0}`;
  if (c.lines_checked != null) {
    detail = `Lines checked ${c.lines_checked} · flagged ${c.lines_flagged || 0}`
      + (c.lines_rewritten != null ? ` · fixed ${c.lines_rewritten} · cut ${c.lines_cut}` : "");
  }
  setRight(STEP_NAMES[step.step] || "PRE-SHOW", step.text || "Getting ready");
  if (step.step && Studio.setStep) Studio.setStep(step.step);
  if (step.step) { Monitor.setStep(step.step); setPipeline(step.step, askedAt); }
  setStatus(`${step.text || "Working"}...`);
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

let chosenPlayers = [];
let askedAt = 0;
async function askDesk(topic) {
  $("go").disabled = true;
  askedAt = Date.now();
  setPipeline(null);
  setPipeline("topic", askedAt);
  setLines("busy", "Patching you through");
  showPreshow(topic);
  try {
    const start = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic, chosen: chosenPlayers }),
    });
    const started = await start.json();
    if (!start.ok) throw new Error(started.error || "Something went wrong.");
    let job;
    for (;;) {
      await wait(900);
      job = await (await fetch(`/api/job/${started.job}`)).json();
      if (job.state !== "running") break;
      showControlRoom(job);
    }
    if (job.state === "topic") return screenCall(topic, job.topic);
    if (job.state === "error") throw new Error(job.error);
    chosenPlayers = [];
    const m = job.script.meta;
    pipelineDone();
    setStatus("On air.");
    await play(job.script);
  } catch (error) {
    clearInterval(preshowTimer);
    setPipeline(null);
    showIdle();
    holdChatter();
    setCenter("LINE DROPPED", "Try that one again");
    showBubble("hal", "Looks like we lost the line. Give us another call.");
    setLines("", "Lines are open");
    setStatus(error.message, true);
  } finally {
    $("go").disabled = false;
  }
}

// The call screener: a topic that was turned away, or a name that needs a choice.
function screenCall(topic, details) {
  clearInterval(preshowTimer);
  setPipeline(null);
  showIdle();
  holdChatter();
  setLines("", "Lines are open");
  const status = $("status");
  status.className = "console-status";
  status.innerHTML = "";
  if (details.confirm) {
    const ask = details.confirm[0];
    setCenter("QUICK QUESTION", "Before we go to air");
    showBubble("hal", `Before we go to air: which ${ask.asked} do you mean?`);
    status.append(`Which ${ask.asked} do you mean? `);
    for (const choice of ask.choices) {
      const b = document.createElement("button");
      b.type = "button"; b.className = "chip"; b.textContent = choice.label;
      b.addEventListener("click", () => { chosenPlayers.push(choice.key); askDesk(topic); });
      status.append(b, " ");
    }
    return;
  }
  setCenter("CALL SCREENED", "Try another topic");
  showBubble("hal", `The call screener stopped that one. ${details.reason}`);
  status.className = "console-status error";
  status.append(details.reason + " ");
  for (const idea of details.suggestions || []) {
    const b = document.createElement("button");
    b.type = "button"; b.className = "chip"; b.textContent = idea;
    b.addEventListener("click", () => { $("topic").value = idea; $("topic").focus(); });
    status.append(b, " ");
  }
}

$("form").addEventListener("submit", (event) => {
  event.preventDefault();
  const topic = $("topic").value.trim();
  if (!topic) return;
  chosenPlayers = [];
  setStatus("You're on hold. The desk is getting ready (usually about two minutes).");
  askDesk(topic);
  refreshChips();          // new suggestions every time someone asks
});


$("pause").addEventListener("click", () => {
  if (!script || cardIndex >= cards.length) return;
  if (paused) {
    paused = false;
    Studio.setPaused(false);
    $("pause").textContent = "Pause";
    playCard();
  } else {
    paused = true;
    clearTimeout(lineTimer);
    Studio.setPaused(true);
    typeText(cards[cardIndex].text, 0);
    $("pause").textContent = "Resume";
  }
});

$("replay").addEventListener("click", () => { if (script) play(script); });
$("end-replay").addEventListener("click", () => { if (script) play(script); });
$("end-ask").addEventListener("click", () => {
  $("topic").scrollIntoView({ behavior: "smooth", block: "center" });
  $("topic").focus();
});

// ---------- Preview: every graphic, with clearly marked sample data ----------

const PREVIEW = {
  sample: true,
  topic: "Graphics preview (sample data)",
  format: "debate",
  caller: { type: "settler", name: "Sam", city: "Denver" },
  sources: ["Sample data, not real"],
  scores: { royce: 66, deacon: 74, lonnie: 69 },
  winner: "deacon",
  tie: false,
  winning_case: { host: "deacon", score: 74, argument: "Sample argument: this is where the winner's case goes.",
                  stats: [{ subject: "Sample Player", label: "EPA per dropback", say: "+0.21", scope: "sample data" },
                          { subject: "Sample Player", label: "record as a starting QB", say: "6-1", scope: "sample data" }] },
  lines: [
    { line: 1, speaker: "hal", delivery: "warm", argument: null,
      text: "This is a graphics preview. Every number you see here is sample data, not real." },
    { line: 2, speaker: "deacon", delivery: "confident", argument: 1, score: { deacon: 71 },
      text: "Sample line. Over on the right monitor, that's the stat chyron.",
      stat: { value: "+0.21", label: "EPA per dropback", definition: "How many points each pass play adds to what a team expects to score.", source: "Sample data", asOf: "Through Week 9" } },
    { line: 3, speaker: "royce", delivery: "exasperated", argument: 2, score: { royce: 66 },
      text: "Sample line. This is me turning away with my arms crossed." },
    { line: 4, speaker: "deacon", delivery: "slam", argument: 3, score: { deacon: 74 },
      text: "Sample line. And this is the desk slam. Turn the sound on." },
    { line: 5, speaker: "lonnie", delivery: "fired_up", argument: 4, score: { lonnie: 69 },
      text: "Sample line. Here's me standing up to make a point." },
    { line: 6, speaker: "royce", delivery: "quiet", argument: 2, text: "Sample final answer: this shows up on the end card." },
    { line: 7, speaker: "deacon", delivery: "calm", argument: 3, text: "Sample final answer: mine does too." },
    { line: 8, speaker: "lonnie", delivery: "calm", argument: 4, text: "Sample final answer: and so does mine." },
    { line: 9, speaker: "hal", delivery: "calm", argument: null, score: { royce: 66, deacon: 74, lonnie: 69 },
      text: "Sample verdict: on the scorecard, tonight goes to Deacon. That's how the close sounds." },
    { line: 10, speaker: "hal", delivery: "warm", argument: null, text: "That's the end of the preview." },
  ],
};
$("preview").addEventListener("click", () => {
  setStatus("Playing the graphics preview. Everything marked SAMPLE is made-up data.");
  play(PREVIEW);
});

// ---------- Logo, tab icon, clock, and cast cards ----------

Studio.logo($("logo"));
Studio.logo($("stinger-logo"));
Studio.trophy($("end-trophy"));
const icon = document.createElement("canvas");
icon.width = 16; icon.height = 16;
Studio.icon(icon);
const link = document.createElement("link");
link.rel = "icon"; link.href = icon.toDataURL("image/png");
document.head.append(link);

function tickClock() {
  $("bug-clock").textContent = new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}
tickClock();
setInterval(tickClock, 10000);

// Cast cards: each in his own color, and the portrait talks and blinks when you hover.
const CARD_BG = { hal: ["#3a4258", "#323a4f"], royce: ["#2a3f86", "#233775"], deacon: ["#6b1d27", "#5a1820"], lonnie: ["#1d5a6b", "#184c5b"] };
for (const id of ["hal", ...HOSTS]) {
  const person = PEOPLE[id];
  const card = document.createElement("article");
  card.className = "card";
  card.style.setProperty("--accent", ACCENTS[id]);
  const portrait = document.createElement("canvas");
  portrait.width = 32; portrait.height = 32;
  const [bg, bg2] = CARD_BG[id];
  const draw = (opts = {}) => Studio.portrait(portrait, id, { bg, bg2, ...opts });
  draw();
  card.append(portrait);
  card.insertAdjacentHTML("beforeend",
    `<h3>${person.name}</h3><div class="role">${person.role}</div><p>${person.blurb}</p><div class="lean">${person.before}</div>`);
  let talk = null;
  card.addEventListener("mouseenter", () => {
    let k = 0;
    clearInterval(talk);
    talk = setInterval(() => { k += 1; draw({ mouth: k % 2 ? "open" : "closed", blink: k % 9 === 0, brow: k % 6 < 3 ? "raise" : "flat" }); }, 150);
  });
  card.addEventListener("mouseleave", () => { clearInterval(talk); draw({ mouth: "smile" }); setTimeout(() => draw(), 700); });
  $("cast-grid").append(card);
}

// The empty question box suggests a question now and then.
setInterval(() => {
  const input = $("topic");
  if (input.value || document.activeElement === input) return;
  input.placeholder = `Try: ${EVERGREEN[Math.floor(Math.random() * EVERGREEN.length)]}`;
}, 5000);

// The ticker at the bottom is the news crawl: real-time NFL and NBA headlines, each
// confirmed by two outlets (pipeline/news.py). No fantasy trends (decided Nov 4, 2026).
// Until confirmed headlines arrive it shows a placeholder, never made-up headlines.
const NEWS_PLACEHOLDER = [
  ["Sideline", "Live NFL and NBA headlines are on the way"],
  ["Lines are open", "Ask the desk any NFL or NBA topic about current players"],
];
setTicker(NEWS_PLACEHOLDER);

async function loadNews() {
  try {
    const news = await (await fetch("/api/news")).json();
    const items = news.headlines.map((h) => [h.league, `${h.text} (${h.outlets.join(", ")})`]);
    if (items.length) setTicker(items);
  } catch (error) {
    /* keep whatever the ticker shows now */
  }
}
loadNews();
setInterval(loadNews, 5 * 60 * 1000);

showIdle();
loadUpcoming();
