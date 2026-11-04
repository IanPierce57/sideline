// app.js: sends the topic to the server, then plays the script as subtitles.

const WORDS_PER_MINUTE = 150;
const MIN_SECONDS = 1.2; // so one-word lines ("Nah.") don't flash past

const $ = (id) => document.getElementById(id);
const FORMAT_NAMES = { debate: "Debate", buy_or_sell: "Buy or sell", prediction: "Prediction" };

let script = null;   // the script being played
let index = 0;       // which line is on screen
let timer = null;    // the countdown to the next line
let paused = false;

// How long a line stays up: its spoken words at 150 words per minute.
// Stage directions in parentheses, like "(the pencil stops)", aren't spoken.
function secondsFor(text) {
  const spoken = text.replace(/\([^)]*\)/g, " ").trim();
  const words = spoken ? spoken.split(/\s+/).length : 0;
  return Math.max(MIN_SECONDS, (words / WORDS_PER_MINUTE) * 60);
}

function setStatus(message, isError = false) {
  $("status").textContent = message;
  $("status").className = isError ? "error" : "";
}

function showLine() {
  if (index >= script.lines.length) {
    $("speaker").textContent = "";
    $("delivery").textContent = "";
    $("line").textContent = "That's the board.";
    $("progress").textContent = "Finished";
    return;
  }
  const line = script.lines[index];
  $("speaker").textContent = line.speaker_name;
  $("delivery").textContent = `(${line.delivery})`;
  $("line").textContent = line.text;
  $("progress").textContent = `Line ${index + 1} of ${script.lines.length}`;
  timer = setTimeout(() => { index += 1; showLine(); }, secondsFor(line.text) * 1000);
}

function play(newScript) {
  clearTimeout(timer);
  script = newScript;
  index = 0;
  paused = false;
  $("pause").textContent = "Pause";
  $("banner").textContent = `${script.topic}  ·  ${FORMAT_NAMES[script.format] || script.format}  ·  about ${script.estimated_minutes} min`;
  for (const id of ["banner", "stage", "controls"]) $(id).hidden = false;
  showLine();
}

$("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const topic = $("topic").value.trim();
  if (!topic) return;
  clearTimeout(timer);
  for (const id of ["banner", "stage", "controls"]) $(id).hidden = true;
  $("go").disabled = true;
  const started = Date.now();
  setStatus("Generating... the hosts are reading their notes (usually about a minute).");
  const tick = setInterval(() => {
    setStatus(`Generating... ${Math.round((Date.now() - started) / 1000)}s`);
  }, 1000);
  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Something went wrong.");
    setStatus(`Ready in ${Math.round((Date.now() - started) / 1000)}s. Saved to runs/${data.run}/script.json`);
    loadRunList();
    play(data);
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    clearInterval(tick);
    $("go").disabled = false;
  }
});

$("pause").addEventListener("click", () => {
  if (!script) return;
  if (paused) {
    paused = false;
    $("pause").textContent = "Pause";
    showLine();
  } else {
    paused = true;
    clearTimeout(timer);
    $("pause").textContent = "Resume";
  }
});

$("replay").addEventListener("click", () => { if (script) play(script); });

async function loadRunList() {
  const runs = await (await fetch("/api/runs")).json();
  const select = $("runs");
  select.length = 1; // keep the "(choose one)" option
  for (const run of runs) {
    select.add(new Option(`${run.name}  ${run.topic}`, run.name));
  }
}

$("runs").addEventListener("change", async () => {
  const name = $("runs").value;
  if (!name) return;
  const response = await fetch(`/api/runs/${name}`);
  const data = await response.json();
  if (!response.ok) return setStatus(data.error, true);
  setStatus(`Replaying runs/${name}/script.json`);
  play(data);
});

loadRunList();
