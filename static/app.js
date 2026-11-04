// app.js: runs the show. It sends your topic to the server, plays the pre-show
// while the script is written, counts down, then plays the segment line by line.

const WORDS_PER_MINUTE = 150;
const MIN_SECONDS = 1.2;        // so one-word lines ("Nah.") don't flash past
const MAX_BUBBLE_CHARS = 170;   // longer lines are split into two subtitle cards

const $ = (id) => document.getElementById(id);

const PEOPLE = {
  hal: {
    name: "Hal Brennan", role: "Moderator",
    blurb: "Thirty years of overnight call-in radio. He lets the argument run, then brings everyone back.",
    lean: "Takes the calls. Never takes a side.",
  },
  royce: {
    name: "Royce Stanhope", role: "Host · The Columnist",
    blurb: "Forty years in press boxes. He wins with the story, and one number you'll remember.",
    lean: "Leans on the eye test and the big moment.",
  },
  deacon: {
    name: "Deacon Pettiford", role: "Host · Hall of Famer",
    blurb: "A ringless Hall of Fame linebacker who taught himself the math. Show him the number.",
    lean: "Leans on analytics.",
  },
  lonnie: {
    name: "Lonnie Fairweather", role: "Host · Former Front Office",
    blurb: "Fifteen years arguing against every big decision before teams made it. Always lands on a call.",
    lean: "Leans on the cap sheet and the roster.",
  },
};
const CALLER_TYPES = {
  diehard: "The diehard", stats_nerd: "The stats nerd", rival_fan: "The rival fan",
  old_timer: "The old-timer", skeptic: "The skeptic", settler: "The settler",
};
const FORMATS = { debate: "DEBATE", buy_or_sell: "BUY OR SELL?", prediction: "PREDICTION" };

// ---------- Small helpers for the on-screen graphics ----------

function setNameplate(name, title) {
  $("nameplate-name").textContent = name;
  $("nameplate-title").textContent = title;
}

function setCamera(id, name, info) {
  Studio.portrait($("cam-portrait"), id);
  $("cam-name").textContent = name.toUpperCase();
  $("cam-info").innerHTML = info;
}

function setCenter(topic, foot) {
  const el = $("center-topic");
  el.textContent = topic;
  const n = topic.length;
  el.style.fontSize = n <= 30 ? "3.2cqw" : n <= 60 ? "2.6cqw" : n <= 95 ? "2.15cqw" : "1.8cqw";
  $("center-foot").textContent = foot;
}

function setRight(big, small) {
  $("right-format").textContent = big;
  $("right-source").textContent = small;
}

function setTicker(items) {
  const html = items.map(([label, text]) =>
    `<span class="gold">${escapeHtml(label)}</span>&nbsp;${escapeHtml(text)}<span class="gem">&#9670;</span>`).join("");
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
function showBubble(anchorId, text, revealSeconds = 0) {
  const bubble = $("bubble"), tail = $("tail");
  const { x, y } = Studio.anchor(anchorId);
  const xPct = (x / Studio.size.W) * 100;
  bubble.hidden = false;
  bubble.classList.toggle("small", text.length > 120);
  bubble.classList.toggle("tiny", text.length > 165);
  if (anchorId === "caller") {
    // the caller is on the left monitor, so the bubble sits beside it
    bubble.style.left = "31.5%"; bubble.style.bottom = "auto"; bubble.style.top = "9%";
    tail.className = "tail side";
    tail.style.left = "";
  } else {
    const width = 46;
    const left = Math.min(Math.max(xPct - width / 2, 1.5), 98.5 - width);
    bubble.style.left = `${left}%`;
    bubble.style.top = "auto";
    bubble.style.bottom = `${((Studio.size.H - y) / Studio.size.H) * 100 + 2.5}%`;
    tail.className = "tail";
    tail.style.left = `${Math.min(Math.max(((xPct - left) / width) * 100, 6), 94)}%`;
  }
  typeText(text, revealSeconds);
}

function typeText(text, seconds) {
  clearInterval(typing);
  const p = $("bubble-text");
  if (!seconds) { p.textContent = text; return; }
  const started = performance.now();
  typing = setInterval(() => {
    const k = Math.min(1, (performance.now() - started) / (seconds * 1000));
    p.textContent = text.slice(0, Math.ceil(text.length * k));
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

// ---------- The screens: idle, pre-show, countdown, live, done ----------

function showIdle() {
  Studio.setMode("idle");
  setOnAir(false);
  setCenter("ASK THE DESK", "NBA · NFL · current or all-time");
  setRight("TONIGHT", "NBA · NFL · call-in debate");
  setCamera("hal", "Hal Brennan", "Moderator<br><span class=\"gold\">Lines open</span>");
  $("show-tag").textContent = "Sideline";
  setNameplate("Hal Brennan", "Moderator");
  showBubble("hal", "Lines are open. Ask the desk anything NBA or NFL, and these three will argue it out.");
  setTicker([
    ["Tonight", "Ask the desk any NBA or NFL topic, current or all-time"],
    ["Royce Stanhope", "The eye test and the big moment"],
    ["Deacon Pettiford", "Show me the number"],
    ["Lonnie Fairweather", "What's the actual decision?"],
    ["Hal Brennan", "Lines are open"],
  ]);
}

let preshowTimer = null;
function showPreshow(topic) {
  stopPlayback();
  $("controls").hidden = true;
  Studio.setMode("preshow");
  setOnAir(false);
  const started = Date.now();
  const tick = () => {
    const s = Math.round((Date.now() - started) / 1000);
    setCenter("STAND BY", `Writing your segment · 0:${String(s).padStart(2, "0")}`);
  };
  tick();
  preshowTimer = setInterval(tick, 1000);
  setRight("PRE-SHOW", "On air in about a minute");
  setCamera("caller", "Line 1", "Caller<br><span class=\"gold\">Holding</span>");
  $("show-tag").textContent = "Pre-show";
  setTicker([
    ["Pre-show", "The desk is getting ready"],
    ["Line 1", "Your caller is holding"],
    ["Up next", topic],
  ]);
}
Studio.onScene((scene) => {
  setNameplate(scene.name, scene.title);
  showBubble(scene.who, scene.text, 1.2);
});

function countdown() {
  return new Promise((resolve) => {
    clearInterval(preshowTimer);
    Studio.setMode("countdown");
    setNameplate("Floor producer", "Countdown");
    let n = 3;
    const step = () => {
      if (n === 0) { resolve(); return; }
      Studio.setCountdown(n);
      setCenter(`ON AIR IN ${n}`, "Quiet on set");
      showBubble("producer", n === 3 ? "Quiet on set! We're live in three..." : n === 2 ? "...two..." : "...one.");
      n -= 1;
      setTimeout(step, 1000);
    };
    step();
  });
}

function showDone() {
  Studio.setMode("done");
  setCenter("THAT'S THE BOARD", "Ask the desk another one");
  setTimeout(() => setOnAir(false), 1500);
  setLines("", "Lines are open");
  setStatus("That's the board. Ask the desk another one.");
  $("progress").textContent = "Finished";
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

function buildCards(lines) {
  const out = [];
  let hostHasSpoken = false;
  for (const line of lines) {
    const spoken = spokenText(line.text);
    const sentences = spoken.match(/[^.!?]+[.!?]+["')\]]*|[^.!?]+$/g) || [spoken];
    const chunks = [];
    let current = "";
    for (const s of sentences.map((x) => x.trim()).filter(Boolean)) {
      if (current && (current + " " + s).length > MAX_BUBBLE_CHARS) { chunks.push(current); current = s; }
      else current = current ? `${current} ${s}` : s;
    }
    if (current || !chunks.length) chunks.push(current);
    const isCutIn = line.speaker === "hal" && hostHasSpoken;
    if (["royce", "deacon", "lonnie"].includes(line.speaker)) hostHasSpoken = true;
    chunks.forEach((text, i) => out.push({ line, text, first: i === 0, isCutIn, seconds: secondsFor(text) }));
  }
  return out;
}

function playCard() {
  if (cardIndex >= cards.length) { Studio.silence(); hideBubble(); showDone(); return; }
  const card = cards[cardIndex];
  const { line } = card;
  if (card.first) Studio.speak(line.speaker, line.delivery, line.text, card.isCutIn);

  if (line.speaker === "caller") {
    const caller = script.caller;
    setNameplate(`${caller.name} from ${caller.city}`, `On the line · ${CALLER_TYPES[caller.type] || "Caller"}`);
    setCamera("caller", "Line 1", `${escapeHtml(caller.name)}<br><span class="gold">${escapeHtml(caller.city)}</span>`);
  } else {
    const person = PEOPLE[line.speaker];
    setNameplate(person.name, person.role);
    setCamera(line.speaker, person.name, `${person.role.replace("Host · ", "")}<br><span class="gold">${FORMATS[script.format] || ""}</span>`);
  }
  showBubble(line.speaker, card.text, Math.min(card.seconds * 0.6, card.text.length / 45));
  $("progress").textContent = `LINE ${line.line} / ${script.lines.length}`;
  lineTimer = setTimeout(() => { cardIndex += 1; playCard(); }, card.seconds * 1000);
}

function stopPlayback() {
  clearTimeout(lineTimer);
  clearInterval(typing);
  paused = false;
  Studio.setPaused(false);
  $("pause").textContent = "Pause";
}

async function play(newScript) {
  stopPlayback();
  script = newScript;
  cards = buildCards(script.lines);
  cardIndex = 0;
  await countdown();
  Studio.setMode("live");
  setOnAir(true);
  setLines("live", "On the air");
  const format = FORMATS[script.format] || "DEBATE";
  setCenter(script.topic.toUpperCase(), `Line 1 · ${script.caller.name} from ${script.caller.city}`);
  setRight(format, `Caller: ${script.caller.name}, ${script.caller.city}`);
  $("show-tag").textContent = format.replace("?", "");
  setTicker([
    ["Tonight", script.topic],
    ["Format", format],
    ["On the line", `${script.caller.name} from ${script.caller.city}, ${(CALLER_TYPES[script.caller.type] || "caller").toLowerCase()}`],
    ["At the desk", "Royce Stanhope · Deacon Pettiford · Lonnie Fairweather"],
    ["Moderator", "Hal Brennan"],
  ]);
  $("controls").hidden = false;
  playCard();
}

// ---------- Asking the desk ----------

$("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const topic = $("topic").value.trim();
  if (!topic) return;
  $("go").disabled = true;
  setLines("busy", "Patching you through");
  setStatus("You're on hold. The desk is getting ready (usually about a minute).");
  showPreshow(topic);
  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Something went wrong.");
    setStatus(`Script saved to runs/${data.run}/script.json`);
    await play(data);
  } catch (error) {
    clearInterval(preshowTimer);
    showIdle();
    setCenter("LINE DROPPED", "Try that one again");
    setNameplate("Hal Brennan", "Moderator");
    showBubble("hal", "Looks like we lost the line. Give us another call.");
    setLines("", "Lines are open");
    setStatus(error.message, true);
  } finally {
    $("go").disabled = false;
  }
});

for (const chip of document.querySelectorAll(".chip")) {
  chip.addEventListener("click", () => { $("topic").value = chip.textContent; $("topic").focus(); });
}

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

// ---------- Clock and cast cards ----------

function tickClock() {
  $("bug-clock").textContent = new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}
tickClock();
setInterval(tickClock, 10000);

for (const id of ["hal", "royce", "deacon", "lonnie"]) {
  const person = PEOPLE[id];
  const card = document.createElement("article");
  card.className = "card";
  const portrait = document.createElement("canvas");
  portrait.width = 32; portrait.height = 32;
  Studio.portrait(portrait, id);
  card.append(portrait);
  card.insertAdjacentHTML("beforeend",
    `<h3>${person.name}</h3><div class="role">${person.role}</div><p>${person.blurb}</p><div class="lean">${person.lean}</div>`);
  $("cast-grid").append(card);
}

showIdle();
