/* studio.js: draws the 8-bit studio and animates the cast.

   Everything is drawn in code on a small 320 x 180 canvas, then scaled up
   with sharp pixels. app.js tells the studio what's happening:
     Studio.setMode("idle" | "preshow" | "countdown" | "live" | "done")
     Studio.speak("royce", "heated", "line text")   who is talking, and how
     Studio.silence()                               nobody is talking
   Each character's look comes from the "Look" section of their bible. */

const Studio = (() => {
  const W = 320, H = 180;
  const DESK = 118;           // the y of the desk top; characters sit behind it
  const canvas = document.getElementById("studio");
  canvas.width = W; canvas.height = H;
  const screen = canvas.getContext("2d");
  const reducedMotion = !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
  let g = screen;             // where R() draws (the studio, or a small portrait)

  // Draw one solid rectangle of pixels.
  function R(x, y, w, h, color) {
    if (w <= 0 || h <= 0) return;
    g.fillStyle = color;
    g.fillRect(Math.round(x), Math.round(y), Math.round(w), Math.round(h));
  }

  // A random-number helper that gives the same numbers every time, so the crowd
  // in the stands looks the same on every visit.
  let seed = 20261104;
  function rand() { seed = (seed * 16807) % 2147483647; return seed / 2147483647; }

  // ---------- A tiny 5x7 pixel font for the signs drawn into the set ----------
  const GLYPHS = {
    R: ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    E: ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    C: ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    I: ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    P: ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    T: ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    S: ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    O: ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    N: ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    A: ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    D: ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    L: ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
  };
  function pixelText(text, x, y, scale, color) {
    for (const ch of text) {
      const rows = GLYPHS[ch] || GLYPHS[" "];
      rows.forEach((row, ry) => {
        for (let rx = 0; rx < 5; rx++) if (row[rx] === "1") R(x + rx * scale, y + ry * scale, scale, scale, color);
      });
      x += 6 * scale;
    }
  }

  // ---------- The cast: seats and colors (from each bible's "Look") ----------
  const CAST = {
    hal:    { x: 70,  half: 17, tall: 2, skin: "#f1cba8", shade: "#d6a985", blush: "#efa69b", lip: "#9b4a43",
              hair: "#d6d9e0", hairShade: "#a8aebb", outfit: "#7f8797", outfitShade: "#646c7c" },
    royce:  { x: 118, half: 17, tall: 0, skin: "#f2c9a3", shade: "#d8a881", blush: "#efa69b", lip: "#9b4a43",
              hair: "#e1e4e9", hairShade: "#b2b8c4", outfit: "#1f2b58", outfitShade: "#151e40" },
    deacon: { x: 204, half: 21, tall: 0, skin: "#ebb592", shade: "#cf9472", blush: "#ec9b8b", lip: "#8f3f39",
              hair: "#a1a6ad", hairShade: "#7d838b", outfit: "#b91f2d", outfitShade: "#8c1622",
              beard: "#b1b5bb", beardShade: "#8d9299" },
    lonnie: { x: 252, half: 17, tall: 0, skin: "#6e4429", shade: "#56331e", blush: null, lip: "#a0604c",
              hair: "#16110f", hairShade: "#30241d", outfit: "#eef1f6", outfitShade: "#c8cfdb" },
  };
  const HEAD_TOP = 79;
  // Each person's accent color (the score bug uses the same ones).
  const ACCENT = { hal: "#c9d2e3", royce: "#f2c14e", deacon: "#e0414e", lonnie: "#5ccfe6" };

  // How each delivery tag moves the body.
  const POSE = {
    building: "lean", confident: "lean", emphatic: "point", heated: "pump",
    frustrated: "handsup", conceding: "handsup", laughing: "laugh",
    sarcastic: "turn", dismissive: "turn", cold: "cold", quiet: "still",
    fired_up: "stand", slam: "slam", exasperated: "away",
  };

  // ---------- What's happening right now ----------
  const S = {
    mode: "idle", speaker: null, delivery: "calm", paused: false,
    props: null, countdown: 0, dim: 0, modeAt: 0,
    scene: -1, sceneAt: 0, onScene: null, onAir: false,
    lineAt: 0, slammed: false, onSlam: null,
    artist: { x: -24, from: -24, to: -24, at: 0, target: null },
    producer: { at: -1e9, x: 344, to: 344 },
    nextBlink: {}, blinkUntil: {}, glance: {}, glanceUntil: {},
    // added Nov 6, 2026: listener reactions, extra talking poses, idle fidgets, crowd,
    // flashes, the winner's celebration, and the camera operator
    react: {}, altPose: null, fidget: { id: null, act: null, until: 0, next: 5000 },
    waveAt: 9000, slamAt: -1e9, flashAt: -1e9, winner: null, doneAt: 0, confetti: [], camOp: -1e9,
  };
  function freshProps() {
    return { pencil: "hand", toothpick: true, sleeves: false, phonesOff: false, heated: 0 };
  }
  S.props = freshProps();
  for (const id in CAST) { S.nextBlink[id] = 800 + Math.random() * 3000; S.blinkUntil[id] = 0; S.glance[id] = 0; S.glanceUntil[id] = 0; }

  // ---------- Pre-show: what everyone does while the script is being written ----------
  // The scenes follow what the pipeline is really doing (app.js calls setStep as the server
  // reports each step), with makeup and small talk mixed in between.
  const SCENE_MS = 6000;
  const PRODUCER_SPOT = 300;   // where the floor producer stands: the right end of the desk
  const sc = (who, name, title, text, acts, extra = {}) => ({ who, name, title, text, artist: null, acts, ...extra });
  // Most scenes are silent: the set just gets ready. A few have a short, natural line
  // (changed Nov 6, 2026: the old lines read like scripted narration).
  const STEP_SCENES = {
    start: [
      sc("hal", "Hal Brennan", "On the phone", "Yeah, you're next. Hang tight.",
         { hal: "miccheck", royce: "notes", deacon: "coffee", lonnie: "tablet" }),
    ],
    research: [
      sc("deacon", "Deacon Pettiford", "Pulling stats", "",
         { hal: "notes", royce: "makeup", deacon: "laptop", lonnie: "tablet" }, { artist: "royce" }),
      sc("lonnie", "Lonnie Fairweather", "Doing research", "",
         { hal: "notes", royce: "write", deacon: "laptop", lonnie: "tablet" }),
    ],
    verify: [
      sc("deacon", "Deacon Pettiford", "Checking the numbers", "That one doesn't match. Toss it.",
         { hal: "notes", royce: "notes", deacon: "laptop", lonnie: "tablet" }),
      sc("royce", "Royce Stanhope", "Pre-show", "",
         { hal: "notes", royce: "write", deacon: "laptop", lonnie: "makeup" }, { artist: "lonnie" }),
    ],
    write: [
      sc("royce", "Royce Stanhope", "Writing his open", "",
         { hal: "notes", royce: "write", deacon: "laptop", lonnie: "coffee" }),
      sc("producer", "Floor producer", "Pre-show", "Two minutes!",
         { hal: "notes", royce: "write", deacon: "makeup", lonnie: "coffee" }, { artist: "deacon", producer: true }),
    ],
    check: [
      sc("hal", "Hal Brennan", "Reading the script", "",
         { hal: "notes", royce: "notes", deacon: "laptop", lonnie: "tablet" }),
      sc("artist", "Makeup", "Pre-show", "Chin up for me.",
         { hal: "makeup", royce: "tie", deacon: "coffee", lonnie: "tablet" }, { artist: "hal" }),
    ],
    judge: [
      sc("lonnie", "Lonnie Fairweather", "Pre-show", "",
         { hal: "notes", royce: "tie", deacon: "stretch", lonnie: "tablet" }),
      sc("deacon", "Deacon Pettiford", "Loosening up", "",
         { hal: "notes", royce: "notes", deacon: "stretch", lonnie: "coffee" }),
    ],
    close: [
      sc("producer", "Floor producer", "Places", "Places, everybody.",
         { hal: "miccheck", royce: "tie", deacon: "coffee", lonnie: "tablet" }, { producer: true }),
    ],
  };
  const FILLER = [
    sc("artist", "Makeup", "Pre-show", "Hold still.",
       { hal: "notes", royce: "makeup", deacon: "laptop", lonnie: "tablet" }, { artist: "royce" }),
    sc("lonnie", "Lonnie Fairweather", "Pre-show", "",
       { hal: "notes", royce: "write", deacon: "laptop", lonnie: "coffee" }),
    sc("hal", "Hal Brennan", "Mic check", "Check, one, two.",
       { hal: "miccheck", royce: "tie", deacon: "laptop", lonnie: "tablet" }),
    sc("deacon", "Deacon Pettiford", "Pre-show", "",
       { hal: "notes", royce: "notes", deacon: "makeup", lonnie: "tablet" }, { artist: "deacon" }),
    sc("crew", "Camera two", "Pre-show", "",
       { hal: "notes", royce: "tie", deacon: "coffee", lonnie: "tablet" }, { camera: true }),
    sc("lonnie", "Lonnie Fairweather", "On the phone", "",
       { hal: "notes", royce: "write", deacon: "laptop", lonnie: "phone" }),
    sc("crew", "Lighting", "Light check", "",
       { hal: "notes", royce: "notes", deacon: "coffee", lonnie: "tablet" }, { lights: true }),
    sc("deacon", "Deacon Pettiford", "Pre-show", "",
       { hal: "notes", royce: "laugh", deacon: "laugh", lonnie: "coffee" }),
    sc("royce", "Royce Stanhope", "On the phone", "",
       { hal: "miccheck", royce: "phone", deacon: "laptop", lonnie: "tablet" }),
  ];
  const STEP_ALIAS = { topic: "start" };

  // ---------- The set (drawn once, then reused every frame) ----------
  const bg = document.createElement("canvas");
  bg.width = W; bg.height = H;
  function paintBackground() {
    g = bg.getContext("2d");
    // ceiling and lighting rig
    R(0, 0, W, 7, "#060b20");
    R(0, 7, W, 2, "#26335f");
    for (let x = 6; x < W; x += 22) { R(x, 5, 6, 3, "#3a4675"); R(x + 1, 8, 4, 1, "#ffe7a1"); }
    // Behind the desk: a night stadium. A football field on the left runs into a
    // basketball court on the right, with one painted sideline across both.
    // night sky
    for (const [y, h, c] of [[9, 12, "#070d2a"], [21, 13, "#0b1440"], [34, 14, "#111d55"]]) R(0, y, W, h, c);
    // crowd in the stands
    R(0, 48, W, 42, "#1b2450");
    const crowd = ["#3a4a8a", "#5a3a5a", "#8a6a4a", "#c7a27a", "#2f3f6f", "#d8323a", "#f4b740", "#e9eefc", "#6b4226", "#4a7a9a"];
    for (let y = 49; y < 89; y += 2) {
      if ((y - 49) % 10 === 8) { R(0, y, W, 1, "#121a3f"); continue; }   // aisle railings
      for (let x = (y % 4 === 1 ? 0 : 1); x < W; x += 2) {
        if (rand() < 0.78) R(x, y, 1, 1, crowd[(rand() * crowd.length) | 0]);
      }
    }
    // light towers, in the gaps between the monitors
    for (const x of [100, 218, 2, 315]) {
      R(x, 22, 2, 66, "#3a4675");
      R(x - 5, 13, 12, 7, "#232c58");
      for (let bx = 0; bx < 3; bx++) for (let by = 0; by < 2; by++) R(x - 4 + bx * 4, 14 + by * 3, 2, 2, "#fff6d0");
      g.fillStyle = "rgba(255,240,200,0.10)"; g.fillRect(x - 12, 9, 26, 26);
      g.fillStyle = "rgba(255,240,200,0.05)"; g.fillRect(x - 20, 9, 42, 44);
    }
    // the field (football) and the court (basketball)
    for (let x = 0; x < 160; x += 8) R(x, 90, 8, 14, (x / 8) % 2 ? "#2a7234" : "#2f7d3a");
    for (let x = 4; x < 160; x += 16) R(x, 90, 1, 14, "#e9eefc");
    for (let x = 12; x < 160; x += 16) { R(x, 93, 1, 1, "#e9eefc"); R(x, 98, 1, 1, "#e9eefc"); }
    for (let y = 90; y < 104; y++) R(160, y, 160, 1, y % 2 ? "#c98a4b" : "#bf8243");
    for (let x = 166; x < W; x += 13) R(x, 90 + (x % 3) * 3, 1, 3, "#a8703c");
    R(286, 91, 34, 10, "#9d1f27");                          // the paint
    R(286, 91, 1, 10, "#f2efe6"); R(286, 91, 34, 1, "#f2efe6");
    R(160, 90, 1, 14, "#f2efe6");                           // where the field meets the court
    R(0, 101, W, 1, "#ffffff");                             // the sideline
    // rail behind the desk
    R(0, 104, W, 1, "#6f8ff0"); R(0, 105, W, 3, "#3456c2"); R(0, 108, W, 1, "#f4b740"); R(0, 109, W, 1, "#d8323a");
    // lower wall panels with rivets
    R(0, 110, W, 50, "#12286b");
    for (let x = -6; x < W; x += 34) {
      for (const y of [113, 137]) {
        R(x + 2, y, 30, 20, "#152f7c"); R(x + 2, y, 30, 1, "#1d3b93"); R(x + 2, y + 19, 30, 1, "#0e2160");
        for (const [dx, dy] of [[3, 3], [26, 3], [3, 16], [26, 16]]) R(x + 2 + dx, y + dy, 1, 1, "#6f86d6");
      }
    }
    // hardwood floor with a painted sideline
    R(0, 160, W, 20, "#a8703c");
    for (let y = 162; y < H; y += 3) R(0, y, W, 1, "#9a6634");
    for (let y = 160; y < H; y += 3) for (let x = (y * 7) % 23; x < W; x += 23) R(x, y, 1, 3, "#8e5c2e");
    R(0, 164, W, 2, "#f2efe6");
    g = screen;
  }

  // Game balls for the desk.
  function football(x, y) {   // 12 x 6, top-left at (x, y)
    R(x + 2, y, 8, 1, "#7a3f1c"); R(x, y + 1, 12, 4, "#7a3f1c"); R(x + 2, y + 5, 8, 1, "#5e2f14");
    R(x + 2, y + 1, 8, 1, "#9b5a2c");
    R(x + 1, y + 1, 1, 4, "#f2efe6"); R(x + 10, y + 1, 1, 4, "#f2efe6");
    R(x + 4, y + 2, 4, 1, "#f2efe6"); R(x + 4, y + 1, 1, 1, "#f2efe6"); R(x + 6, y + 1, 1, 1, "#f2efe6");
  }
  function basketball(x, y) { // 9 x 9, top-left at (x, y)
    const rows = [[2, 5], [1, 7], [0, 9], [0, 9], [0, 9], [0, 9], [0, 9], [1, 7], [2, 5]];
    rows.forEach(([dx, w], dy) => R(x + dx, y + dy, w, 1, dy > 5 ? "#b85d1c" : "#e07a2c"));
    R(x + 4, y, 1, 9, "#1a1412"); R(x, y + 4, 9, 1, "#1a1412");
    R(x + 1, y + 1, 1, 2, "#1a1412"); R(x + 1, y + 6, 1, 2, "#1a1412"); R(x + 7, y + 1, 1, 2, "#1a1412"); R(x + 7, y + 6, 1, 2, "#1a1412");
    R(x + 2, y + 1, 1, 1, "#f2a05a");
  }
  paintBackground();

  function drawOnAirSign() {
    const x = 140, y = 86;
    if (S.onAir) {
      g.fillStyle = "rgba(255,60,70,0.14)"; g.fillRect(x - 5, y - 4, 50, 22);
      g.fillStyle = "rgba(255,60,70,0.10)"; g.fillRect(x - 9, y - 7, 58, 28);
    }
    R(x - 1, y - 1, 42, 14, "#12060a");
    R(x, y, 40, 12, S.onAir ? "#4a0f16" : "#260a0e");
    pixelText("ON AIR", x + 3, y + 3, 1, S.onAir ? "#ff5a64" : "#5a2026");
  }

  function drawDesk(t) {
    R(32, DESK, 256, 1, "#ffffff");
    R(32, DESK + 1, 256, 4, "#e6ecf5");
    R(32, DESK + 5, 256, 1, "#8f9bb6");
    R(31, DESK + 1, 1, 4, "#c9d2e3"); R(288, DESK + 1, 1, 4, "#c9d2e3");
    R(36, DESK + 6, 248, 34, "#1e43a6");
    R(36, DESK + 6, 248, 1, "#7a9bff");
    for (const x of [92, 226]) { R(x, DESK + 7, 2, 27, "#173893"); R(x + 2, DESK + 7, 1, 27, "#2a52bf"); }
    g.fillStyle = "rgba(255,255,255,0.03)";
    for (let y = DESK + 9; y < DESK + 33; y += 3) g.fillRect(37, y, 246, 1);
    // logo panel on the front
    R(111, DESK + 9, 98, 23, "#0f2463"); R(111, DESK + 9, 98, 1, "#3a63d6"); R(111, DESK + 31, 98, 1, "#08163f");
    pixelText("SIDELINE", 114, DESK + 15, 2, "#0a1433");
    pixelText("SIDELINE", 113, DESK + 14, 2, "#ffffff");
    // a football and a basketball on either side of the logo
    football(97, DESK + 17);
    basketball(213, DESK + 15);
    // stripes at the base
    R(36, DESK + 34, 248, 2, "#d8323a"); R(36, DESK + 36, 248, 1, "#f4b740"); R(36, DESK + 37, 248, 3, "#0c1a4a");
    g.fillStyle = "rgba(0,0,0,0.35)"; g.fillRect(30, DESK + 40, 260, 2);
    if (t == null) return;
    // LED chase lights along the red stripe, in the speaker's color when we're live
    const accent = S.mode === "live" && ACCENT[S.speaker] && !S.paused ? ACCENT[S.speaker] : "#f4b740";
    for (let k = 0; k < 4; k++) {
      const pos = (t / 11 + k * 62) % 248;
      g.globalAlpha = 0.35; R(36 + pos - 6, DESK + 34, 6, 2, accent);
      g.globalAlpha = 1; R(36 + pos, DESK + 34, Math.min(8, 248 - pos), 2, accent);
    }
    g.globalAlpha = 1;
    if (t - S.slamAt < 200) R(36, DESK + 34, 248, 3, "#ffffff");
    // a shine sweeps across the logo panel every few seconds
    const k = (t % 7000) / 800;
    if (k < 1) {
      const sx = 104 + k * 118;
      g.save();
      g.beginPath(); g.rect(111, DESK + 10, 98, 21); g.clip();
      g.fillStyle = "rgba(255,255,255,0.22)";
      g.beginPath(); g.moveTo(sx, DESK + 10); g.lineTo(sx + 7, DESK + 10); g.lineTo(sx - 3, DESK + 31); g.lineTo(sx - 10, DESK + 31); g.fill();
      g.restore();
    }
  }

  // ---------- Life around the set (added Nov 6, 2026) ----------
  // Tiny players running drills behind the desk: a pass play on the field, a jumper on the court.
  function tinyPlayer(x, feet, jersey, helmet, step) {
    R(x, feet - 6, 2, 2, helmet);
    R(x, feet - 4, 2, 2, jersey);
    R(x, feet - 2, 1, 2, "#e9eefc"); R(x + 1, feet - 2 + step, 1, 2 - step, "#e9eefc");
  }
  function drawFieldLife(t) {
    // football: the receiver runs a go route, the quarterback hits him in stride
    const p = t % 6400;
    const run = (p / 140) | 0;
    const wr = 26 + Math.min(p, 4600) / 4600 * 124;
    tinyPlayer(24, 99, "#d8323a", "#f4b740", 0);                       // quarterback
    tinyPlayer(wr, 99, "#d8323a", "#f4b740", run % 2);                 // receiver
    tinyPlayer(wr - 7, 99, "#e9eefc", "#11224f", (run + 1) % 2);       // the corner, a step behind
    if (p > 1300 && p < 2900) {
      const k = (p - 1300) / 1600;
      const tx = 26 + 2900 / 4600 * 124;
      R(24 + (tx - 24) * k, 92 - Math.sin(Math.PI * k) * 10, 2, 1, "#7a3f1c");
    }
    // basketball: dribble in, pull up, swish
    const q = t % 5200;
    const hoopX = 311;
    R(316, 85, 1, 8, "#f2efe6"); R(311, 92, 5, 1, "#e07a2c");                 // backboard and rim
    const swish = q > 2500 && q < 2800;
    R(312, 93 + (swish ? 1 : 0), 1, 3, "#d8dde8"); R(314, 93 + (swish ? 1 : 0), 1, 3, "#d8dde8");
    let px, bx, by;
    if (q < 1800) {
      px = 272 + (q / 1800) * 24;
      bx = px + 2; by = ((q / 180) | 0) % 2 ? 99 : 96;
    } else if (q < 2600) {
      px = 296;
      const k = (q - 1800) / 800;
      bx = 298 + (hoopX + 2 - 298) * k; by = 93 - Math.sin(Math.PI * k) * 12 + k * -1;
    } else {
      px = 296 - ((q - 2600) / 2600) * 24;
      const k = Math.min(1, (q - 2600) / 500);
      bx = hoopX + 2; by = 92 + k * 7;
    }
    tinyPlayer(px, 100, "#1f44a8", "#6e4429", ((q / 150) | 0) % 2);
    R(bx, by, 2, 2, "#e07a2c");
  }

  // The crowd: camera flashes, a wave now and then, and a roar of flashes on a desk slam.
  function drawCrowdLife(t) {
    if (Math.random() < 0.35) R(Math.random() * W, 49 + Math.random() * 38, 1, 1, "#ffffff");
    if (t - S.slamAt < 450) for (let i = 0; i < 14; i++) R(Math.random() * W, 74 + Math.random() * 15, 1, 1, "#ffffff");
    if (S.mode === "preshow" || S.mode === "countdown" || reducedMotion) return;
    if (t > S.waveAt + 4200) S.waveAt = t + 22000 + Math.random() * 18000;
    if (t > S.waveAt) {
      const wx = -12 + ((t - S.waveAt) / 4200) * (W + 24);
      g.fillStyle = "rgba(255,248,220,0.12)"; g.fillRect(wx - 6, 74, 12, 15);
      for (let x = Math.round(wx) - 5; x < wx + 5; x += 2) R(x, 74 + ((x * 7) & 1), 1, 1, "#fff6d0");
    }
  }

  // Light beams from the towers between the monitors, swaying slowly.
  function drawBeams(t) {
    const flicker = S.mode === "preshow" && S.current && S.current.lights;
    const base = S.mode === "live" ? 0.05 : 0.035;
    [100, 218, 2, 315].forEach((x, i) => {
      const on = flicker ? ((t / 90 + i * 3) | 0) % 3 !== 0 : true;
      if (!on) { R(x - 4, 14, 10, 5, "#232c58"); return; }
      const sway = Math.sin(t / 2700 + i * 1.7) * 16 + (x < 20 ? 30 : x > 300 ? -30 : 0);
      g.fillStyle = `rgba(255,236,190,${flicker ? base * 2 : base})`;
      g.beginPath(); g.moveTo(x - 3, 18); g.lineTo(x + 5, 18); g.lineTo(x + 1 + sway + 20, 104); g.lineTo(x + 1 + sway - 20, 104); g.fill();
    });
  }

  // A warm spotlight cone on whoever's talking.
  function drawCone(t) {
    if (S.mode !== "live" || !CAST[S.speaker] || S.paused) return;
    const c = CAST[S.speaker];
    const k = Math.min(1, (t - S.lineAt) / 220);
    g.fillStyle = `rgba(255,230,160,${(0.09 * k).toFixed(3)})`;
    g.beginPath(); g.moveTo(c.x - 4, 9); g.lineTo(c.x + 4, 9); g.lineTo(c.x + 30, DESK); g.lineTo(c.x - 30, DESK); g.fill();
    g.fillStyle = `rgba(255,226,150,${(0.06 * k).toFixed(3)})`;
    for (let i = 0; i < 3; i++) g.fillRect(c.x - 18 - i * 4, HEAD_TOP - 8 - i * 3, 36 + i * 8, 48 + i * 3);
  }

  // Confetti for the winner.
  function spawnConfetti(colors, n) {
    for (let i = 0; i < n; i++) {
      S.confetti.push({ x: Math.random() * W, y: -Math.random() * 60, vx: (Math.random() - 0.5) * 0.4,
                        vy: 0.4 + Math.random() * 0.6, w: Math.random() < 0.5 ? 2 : 1,
                        c: colors[(Math.random() * colors.length) | 0], ph: Math.random() * 6 });
    }
  }
  function drawConfetti(t, dt) {
    if (!S.confetti.length) return;
    const k = Math.min(3, dt / 16.7);
    for (const p of S.confetti) {
      p.y += p.vy * k; p.x += (p.vx + Math.sin(t / 300 + p.ph) * 0.25) * k;
      R(p.x, p.y, p.w, ((t / 120 + p.ph) | 0) % 2 ? 1 : 2, p.c);
    }
    S.confetti = S.confetti.filter((p) => p.y < H);
  }

  // A camera operator rolls camera two across the floor.
  function drawCameraOp(t) {
    const since = t - S.camOp;
    if (since < 0 || since > SCENE_MS) return;
    const x = Math.round(-36 + (since / SCENE_MS) * 390);
    const skin = "#b9825a";
    crewLegs(x, true, t);
    R(x - 7, 99, 14, 42, "#3b3f4f"); R(x - 7, 99, 14, 1, "#565b70");
    R(x - 2, 96, 4, 3, "#9a6a48"); R(x - 6, 83, 12, 13, skin);
    R(x - 1, 88, 1, 2, "#16161f"); R(x + 3, 88, 1, 2, "#16161f");
    R(x - 7, 80, 14, 4, "#1d1a18"); R(x - 8, 79, 16, 1, "#22242d"); R(x - 9, 84, 2, 5, "#22242d");
    R(x + 6, 108, 8, 3, "#3b3f4f"); R(x + 13, 108, 3, 3, skin);                       // arm on the handle
    // the camera on its pedestal
    R(x + 22, 126, 2, 32, "#3a3f50"); R(x + 15, 157, 16, 2, "#22242d");
    R(x + 15, 159, 2, 2, "#111"); R(x + 29, 159, 2, 2, "#111");
    R(x + 14, 112, 18, 12, "#2b2f3d"); R(x + 14, 112, 18, 1, "#4a5268");
    R(x + 32, 114, 5, 8, "#11131a"); R(x + 36, 115, 1, 6, "#5ccfe6");
    R(x + 10, 114, 4, 6, "#22242d");
    if (((t / 400) | 0) % 2) R(x + 15, 110, 3, 2, "#ff3b3b");                          // tally light
  }

  // ---------- People ----------
  function chair(cx, hy, wide) {
    const w = wide ? 32 : 28;
    R(cx - w / 2, hy + 8, w, DESK - hy - 8, "#1b1e2e");
    R(cx - w / 2 + 1, hy + 7, w - 2, 1, "#2d3248");
    R(cx - w / 2, hy + 9, 1, DESK - hy - 9, "#2d3248");
  }

  // One seated character, head and shoulders. o = how they look this frame.
  function drawPerson(id, cx, hy, o) {
    const c = CAST[id];
    const P = (x, y, w, h, col) => R(cx + x, hy + y, w, h, col);
    const half = c.half;
    const bottom = o.bottom - hy;

    // torso
    P(-half + 2, 21, half * 2 - 4, 1, c.outfit);
    P(-half, 22, half * 2, bottom - 22, c.outfit);
    P(-half, 22, 2, bottom - 22, c.outfitShade);
    P(half - 2, 22, 2, bottom - 22, c.outfitShade);
    OUTFIT[id](P, half, bottom, o);

    // neck and head
    P(-3, 17, 6, 5, c.shade);
    if (id === "deacon") { P(-6, 18, 12, 4, c.outfit); P(-6, 18, 12, 1, "#d8424f"); }  // quarter-zip collar
    P(-8, 1, 16, 1, c.skin); P(-9, 2, 18, 15, c.skin); P(-8, 17, 16, 1, c.skin);
    P(8, 3, 1, 13, c.shade);
    P(-10, 7, 1, 4, c.skin); P(9, 7, 1, 4, c.shade);
    if (c.blush) { P(-7, 12, 2, 1, c.blush); P(5, 12, 2, 1, c.blush); }
    const mx = o.mx || 0;   // turning away shifts the nose and mouth to one side
    P(-1 + mx, 11, 2, 2, c.shade);

    // eyes
    const lx = o.lx || 0, ly = o.ly || 0;
    if (o.blink) { P(-5 + lx, 10 + ly, 3, 1, "#16161f"); P(3 + lx, 10 + ly, 3, 1, "#16161f"); }
    else if (o.squint) { P(-5 + lx, 9 + ly, 2, 2, "#16161f"); P(3 + lx, 9 + ly, 2, 2, "#16161f"); }
    else { P(-5 + lx, 8 + ly, 2, 3, "#16161f"); P(3 + lx, 8 + ly, 2, 3, "#16161f"); }

    // brows
    const b = id === "lonnie" ? c.hair : c.hairShade;
    if (o.brow === "angry") { P(-6, 6, 2, 1, b); P(-4, 7, 1, 1, b); P(3, 7, 1, 1, b); P(4, 6, 2, 1, b); }
    else if (o.brow === "raise") { P(-6, 6, 3, 1, b); P(3, 5, 3, 1, b); }
    else if (o.brow === "low") { P(-6, 7, 3, 1, b); P(3, 7, 3, 1, b); }
    else { P(-6, 6, 3, 1, b); P(3, 6, 3, 1, b); }

    // beards go under the mouth
    if (id === "deacon") {
      P(-9, 10, 2, 4, c.beard); P(7, 10, 2, 4, c.beard);
      P(-9, 13, 18, 4, c.beard); P(-8, 17, 16, 2, c.beard); P(-3, 13, 6, 1, c.beardShade);
    }
    if (id === "lonnie") {
      P(-9, 9, 1, 5, c.hair); P(8, 9, 1, 5, c.hair);
      P(-8, 13, 16, 3, c.hair); P(-6, 16, 12, 2, c.hair);
    }

    // mouth
    if (o.mouth === "open") { P(-2 + mx, 14, 4, 3, "#5e1a1f"); P(-2 + mx, 14, 4, 1, "#f2f2f2"); }
    else if (o.mouth === "wide") { P(-3 + mx, 14, 6, 3, "#5e1a1f"); P(-3 + mx, 14, 6, 1, "#f2f2f2"); }
    else if (o.mouth === "smile") { P(-3, 14, 1, 1, c.lip); P(-2, 15, 4, 1, c.lip); P(2, 14, 1, 1, c.lip); }
    else P(-2 + mx, 15, 4, 1, c.lip);

    HAIR[id](P, c, o);
  }

  // Clothes, from each bible's "Look".
  const OUTFIT = {
    hal(P, half, bottom) {   // gray cardigan over a collared shirt
      P(-3, 21, 6, 6, "#cfe0f5"); P(-2, 27, 4, 3, "#cfe0f5"); P(-1, 30, 2, 2, "#cfe0f5");
      P(-4, 20, 3, 2, "#eef5fe"); P(1, 20, 3, 2, "#eef5fe");
      P(-4, 26, 1, bottom - 26, "#6a7282"); P(3, 26, 1, bottom - 26, "#6a7282");
      for (let y = 33; y < bottom; y += 5) P(-5, y, 1, 1, "#3c4250");
    },
    royce(P, half, bottom) { // navy suit, white shirt, burgundy tie
      P(-3, 21, 6, 10, "#f5f6f8");
      P(-6, 21, 3, 13, "#2c3c78"); P(3, 21, 3, 13, "#2c3c78");
      P(-1, 21, 2, 1, "#a8243a"); P(-1, 22, 2, 11, "#8a1c2e"); P(-1, 33, 2, 1, "#6d1524");
      P(-13, 26, 3, 1, "#f5f6f8");
    },
    deacon(P, half, bottom) { // red quarter-zip
      P(0, 20, 1, bottom - 20, "#d9d9de"); P(-1, 24, 3, 2, "#c4c4cc");
    },
    lonnie(P, half, bottom) { // white button-down
      P(-4, 20, 3, 2, "#ffffff"); P(1, 20, 3, 2, "#ffffff"); P(-1, 21, 2, 2, "#d9dee8");
      P(0, 23, 1, bottom - 23, "#c3cad8");
      for (let y = 26; y < bottom; y += 5) P(-1, y, 1, 1, "#9aa3b5");
    },
  };

  // Hair, glasses, headphones, toothpick.
  const HAIR = {
    hal(P, c, o) {
      P(-8, 0, 16, 2, c.hair); P(-9, 2, 3, 6, c.hair); P(6, 2, 3, 6, c.hair); P(-9, 2, 1, 6, c.hairShade);
      // reading glasses pushed up on the forehead
      P(-6, 3, 5, 1, "#2a2e38"); P(1, 3, 5, 1, "#2a2e38"); P(-1, 3, 2, 1, "#2a2e38");
      P(-6, 4, 5, 1, "#9cc2ee"); P(1, 4, 5, 1, "#9cc2ee");
      // headphones over one ear; they slide off before he cuts in
      P(-8, -2, 16, 1, "#22242d"); P(-10, -1, 2, 7, "#22242d"); P(8, -1, 2, 3, "#22242d"); P(10, 1, 2, 5, "#22242d");
      if (o.phonesOff) { P(-13, 11, 3, 6, "#22242d"); P(-13, 12, 1, 2, "#4b5061"); }
      else { P(-12, 5, 3, 7, "#22242d"); P(-12, 6, 1, 3, "#4b5061"); }
    },
    royce(P, c) {
      P(-9, 0, 18, 3, c.hair); P(-9, 3, 2, 5, c.hair); P(7, 3, 2, 5, c.hair);
      P(-6, 0, 3, 1, c.hairShade); P(0, 1, 4, 1, c.hairShade); P(5, 0, 2, 1, c.hairShade);
      // rimless glasses
      const f = "#e3ecf8";
      P(-7, 7, 5, 1, f); P(2, 7, 5, 1, f); P(-2, 8, 4, 1, f); P(-7, 8, 1, 2, f); P(6, 8, 1, 2, f);
    },
    deacon(P, c, o) {
      P(-9, 0, 18, 2, c.hair); P(-9, 2, 1, 4, c.hair); P(8, 2, 1, 4, c.hair);
      for (const [x, y] of [[-7, 0], [-3, 1], [2, 0], [6, 1]]) P(x, y, 1, 1, c.hairShade);
      if (o.toothpick) { P(2, 15, 3, 1, "#e2c38c"); P(5, 16, 2, 1, "#e2c38c"); }
    },
    lonnie(P, c) {
      P(-9, 0, 18, 3, c.hair); P(-9, 3, 1, 3, c.hairShade); P(8, 3, 1, 3, c.hairShade);
      P(-8, 3, 16, 1, c.hair);
    },
  };

  // Arms. "rest" puts forearms on the desk (drawn after the desk so they sit on it).
  function sleeveOf(id) {
    if (id === "lonnie" && S.props.sleeves) return CAST.lonnie.skin;
    return CAST[id].outfit;
  }
  function restArm(id, cx, side) {
    const c = CAST[id], half = c.half, sleeve = sleeveOf(id);
    if (side < 0) {
      R(cx - half + 1, 115, half - 6, 5, sleeve);
      if (id === "lonnie" && S.props.sleeves) R(cx - half + 1, 115, 3, 5, "#eef1f6");
      R(cx - 6, 116, 5, 4, c.skin); R(cx - 6, 119, 5, 1, c.shade);
      if (id === "lonnie") R(cx - 7, 116, 1, 4, "#c7ccd6");   // watch
    } else {
      R(cx + 5, 115, half - 6, 5, sleeve);
      if (id === "lonnie" && S.props.sleeves) R(cx + half - 4, 115, 3, 5, "#eef1f6");
      R(cx + 1, 116, 5, 4, c.skin); R(cx + 1, 119, 5, 1, c.shade);
    }
  }
  function raisedArm(id, cx, hy, side, lift, finger) {
    const c = CAST[id], half = c.half, sleeve = sleeveOf(id);
    const x = side > 0 ? cx + half - 3 : cx - half - 1;
    R(x, hy + 12 - lift, 4, 16 + lift, sleeve);
    if (id === "lonnie" && S.props.sleeves) R(x, hy + 22, 4, 2, "#eef1f6");
    R(x, hy + 8 - lift, 4, 4, c.skin);
    if (finger) R(x + 1, hy + 5 - lift, 2, 3, c.skin);
    return { x, y: hy + 8 - lift };
  }

  // Things on the desk.
  // Game balls on little stands at each end of the desk.
  function deskBalls() {
    R(36, 117, 10, 1, "#c8cdd8"); R(40, 116, 2, 1, "#c8cdd8"); football(35, 110);
    R(275, 117, 11, 1, "#c8cdd8"); R(279, 116, 3, 1, "#c8cdd8"); basketball(276, 107);
  }

  function deskItems(id, cx, t, act) {
    if (id === "hal") { R(cx - 22, 116, 9, 2, "#f4f1e6"); R(cx - 21, 116, 7, 1, "#d8d2bf"); }
    if (id === "royce") { R(cx - 22, 116, 9, 3, "#efe4c2"); R(cx - 22, 119, 9, 1, "#c9bc94"); }
    if (id === "deacon" && act !== "coffee") { R(cx + 17, 112, 5, 6, "#e9e9e9"); R(cx + 22, 113, 1, 3, "#e9e9e9"); R(cx + 17, 112, 5, 1, "#5a3b22"); }
    if (id === "lonnie" && act !== "tablet") { R(cx + 11, 116, 11, 3, "#2a2f3d"); R(cx + 12, 116, 9, 1, "#5ccfe6"); }
    if (id === "royce" && S.props.pencil === "desk") { R(cx + 7, 119, 1, 1, "#333"); R(cx + 8, 119, 9, 1, "#f2c14e"); R(cx + 17, 119, 1, 1, "#e98ea0"); }
    if (id === "deacon" && !S.props.toothpick) { R(cx + 9, 120, 4, 1, "#e2c38c"); }
    if (id === "lonnie" && act === "coffee") { R(cx + 14, 112, 5, 6, "#d8323a"); R(cx + 19, 113, 1, 3, "#d8323a"); }
  }

  function pencilInHand(x, y, click) {
    R(x, y - click, 1, 1, "#e98ea0"); R(x, y + 1, 1, 1, "#c8c8c8"); R(x, y + 2, 1, 8, "#f2c14e"); R(x, y + 10, 1, 1, "#333");
  }

  // ---------- Crew for the pre-show ----------
  function crewLegs(x, walking, t) {
    const step = walking ? ((t / 140) | 0) % 2 : 0;
    R(x - 4, 140, 3, 21 - step, "#2b2f45"); R(x + 1, 140, 3, 20 + step, "#2b2f45");
    R(x - 5, 160 - step, 4, 2, "#111"); R(x + 1, 160 + step - 1, 4, 2, "#111");
  }
  function drawArtist(t) {
    const a = S.artist;
    const walking = a.x !== a.to;
    const x = a.x;
    if (x < -20 || x > 340) return;
    const skin = "#c98e64";
    crewLegs(x, walking, t);
    R(x - 7, 99, 14, 42, "#22252f"); R(x - 7, 99, 14, 1, "#2fb3a0"); R(x - 1, 101, 2, 38, "#2fb3a0");
    R(x - 2, 96, 4, 3, "#b27a52");
    R(x - 6, 83, 12, 13, skin);
    R(x - 3, 88, 1, 2, "#16161f"); R(x + 2, 88, 1, 2, "#16161f"); R(x - 1, 92, 2, 1, "#7a3b33");
    R(x - 7, 80, 14, 4, "#3a1f3a"); R(x - 3, 76, 6, 4, "#3a1f3a"); R(x - 7, 84, 2, 6, "#3a1f3a");
    if (!walking && a.target) {
      // reach over and dab with the powder puff
      const c = CAST[a.target], hy = HEAD_TOP - c.tall;
      const reach = c.x - 9;
      const dab = ((t / 220) | 0) % 2;
      R(x + 6, hy + 14, reach - (x + 6), 3, "#22252f");
      R(reach - 2, hy + 12, 3, 4, skin);
      R(reach - 1, hy + 9 + dab, 5, 4, "#f6b3c8");
      if (dab) {
        g.fillStyle = "rgba(255,255,255,0.75)";
        for (let i = 0; i < 4; i++) g.fillRect(reach + 1 + ((t / 37 + i * 3) % 7 | 0), hy + 5 + ((t / 53 + i * 5) % 9 | 0), 1, 1);
      }
    } else {
      R(x + 6, 104, 3, 14, "#22252f"); R(x + 6, 117, 3, 3, skin);
    }
  }
  function drawProducer(t, x, fingers) {
    if (x < -20 || x > 340) return;
    const walking = fingers == null && S.producer.x !== S.producer.to;
    const skin = "#e3b48d";
    crewLegs(x, walking, t);
    R(x - 7, 99, 14, 42, "#2c3b6e"); R(x - 7, 99, 14, 1, "#3d4f8c");
    R(x - 1, 99, 2, 12, "#d8323a"); R(x - 2, 111, 4, 3, "#f4f1e6");
    R(x - 2, 96, 4, 3, "#c99a74");
    R(x - 6, 83, 12, 13, skin);
    R(x - 3, 88, 1, 2, "#16161f"); R(x + 2, 88, 1, 2, "#16161f");
    R(x - 1, 92, 3, fingers ? 2 : 1, "#7a3b33");
    R(x - 7, 80, 14, 4, "#5a3b22"); R(x - 7, 84, 1, 4, "#5a3b22");
    R(x - 8, 79, 16, 1, "#22242d"); R(x - 9, 84, 2, 5, "#22242d"); R(x - 8, 89, 1, 3, "#22242d"); R(x - 8, 92, 4, 1, "#22242d");
    if (fingers != null) {
      // floor producer counting down on one hand
      R(x + 7, 86, 4, 16, "#2c3b6e"); R(x + 7, 81, 5, 5, skin);
      for (let i = 0; i < fingers; i++) R(x + 7 + i * 2, 77, 1, 4, skin);
      R(x - 9, 104, 3, 14, "#2c3b6e"); R(x - 9, 117, 3, 3, skin);
    } else {
      R(x + 1, 104, 10, 13, "#c9a46a"); R(x + 2, 106, 8, 10, "#f4f1e6");
      for (let y = 108; y < 115; y += 2) R(x + 3, y, 6, 1, "#c9c2ad");
      R(x + 1, 112, 3, 3, skin);
    }
  }

  // ---------- Each frame ----------
  function lerp(a, b, k) { return a + (b - a) * Math.max(0, Math.min(1, k)); }

  function updateScene(t) {
    if (S.mode !== "preshow") return;
    if (S.scene >= 0 && t < S.nextSceneAt) return;
    // Alternate: a scene about the current step, then a filler scene. A new step cuts in
    // right away (after at least 2.5 seconds on the current scene).
    S.scene += 1;
    S.sceneAt = t;
    S.nextSceneAt = t + SCENE_MS;
    const pool = STEP_SCENES[S.step] || STEP_SCENES.start;
    const fromStep = S.stepFresh || S.scene % 2 === 0;
    const scene = fromStep ? pool[(S.stepCount++) % pool.length] : FILLER[(S.fillCount++) % FILLER.length];
    S.stepFresh = false;
    S.current = scene;
    moveArtist(scene.artist, t);
    if (scene.producer) S.producer = { at: t, x: 344, to: PRODUCER_SPOT };
    if (scene.camera) S.camOp = t;
    if (S.onScene) S.onScene(scene);
  }
  function moveArtist(target, t) {
    const a = S.artist;
    a.from = a.x; a.at = t; a.target = target;
    a.to = target ? CAST[target].x - 17 : -24;
  }

  function personState(id, t) {
    const c = CAST[id];
    const o = { lx: 0, ly: 0, mx: 0, blink: false, squint: false, mouth: "closed", brow: "flat", pose: "rest", bob: 0, act: null };
    // blinking
    if (t >= S.nextBlink[id]) { S.blinkUntil[id] = t + 130; S.nextBlink[id] = t + 2400 + Math.random() * 4200; }
    o.blink = t < S.blinkUntil[id];

    const flap = ((t + c.x * 7) / 120 | 0) % 2 === 0;

    if (S.mode === "preshow") {
      const scene = S.current || FILLER[0];
      o.act = scene.acts[id];
      const sceneTalk = scene.who === id && t - S.sceneAt > 400 && t - S.sceneAt < 4200;
      if (sceneTalk) o.mouth = flap ? "open" : "closed";
      switch (o.act) {
        case "makeup": o.blink = true; o.mouth = "closed"; break;
        case "laptop": case "notes": case "write": case "tablet": o.ly = 1; break;
        case "stretch": o.bob = ((t / 600) | 0) % 2; break;
        case "tie": o.ly = 1; break;
        case "laugh": o.mouth = "wide"; o.squint = true; o.bob = ((t / 140) | 0) % 2; break;
        case "phone": o.lx = -1; o.mouth = flap && ((t / 900) | 0) % 2 ? "open" : "closed"; break;
      }
      return o;
    }

    if (S.mode === "live" && S.speaker && !S.paused) {
      if (S.speaker === id) {
        o.pose = S.altPose || POSE[S.delivery] || "rest";
        if (o.pose === "think") { o.ly = -1; o.brow = "raise"; }
        if (o.pose === "count" || o.pose === "tap") o.brow = o.pose === "tap" ? "angry" : "flat";
        o.mouth = flap ? "open" : "closed";
        if (o.pose === "laugh") { o.mouth = "wide"; o.squint = true; o.bob = ((t / 110) | 0) % 2; }
        if (o.pose === "lean") o.bob = 1;
        if (o.pose === "pump" || o.pose === "point") o.brow = "angry";
        if (o.pose === "turn") { o.brow = "raise"; o.lx = 1; }
        if (o.pose === "cold") { o.brow = "low"; o.squint = true; }
        if (o.pose === "still") o.mouth = flap ? "open" : "closed";
        if (o.pose === "stand") { o.bob = -7; o.brow = "angry"; }
        if (o.pose === "away") { o.lx = 3; o.mx = 2; o.brow = "low"; }
        if (o.pose === "slam") {
          // hands go up, then come down hard on the desk
          const since = t - S.lineAt;
          o.brow = "angry";
          if (since < 320) { o.pose = "handsup"; o.bob = -2; o.mouth = "closed"; }
          else {
            if (!S.slammed) { S.slammed = true; S.slamAt = t; if (S.onSlam) S.onSlam(); }
            o.pose = "rest"; o.bob = since < 470 ? 1 : 0;
          }
        }
      } else {
        const target = S.speaker === "caller" ? 52 : (CAST[S.speaker] ? CAST[S.speaker].x : c.x);
        o.lx = target < c.x - 4 ? -1 : target > c.x + 4 ? 1 : 0;
        // listeners react: a nod, a smirk, a raised eyebrow, a head shake
        const rx = S.react[id];
        if (rx && t > rx.at && t < rx.at + rx.dur) {
          const e = t - rx.at;
          if (rx.kind === "nod") o.ly = ((e / 230) | 0) % 2;
          else if (rx.kind === "smile") o.mouth = "smile";
          else if (rx.kind === "raise") o.brow = "raise";
          else if (rx.kind === "low") { o.brow = "low"; o.squint = true; }
          else if (rx.kind === "lean") { o.bob = -1; o.brow = "raise"; }
          else if (rx.kind === "shake") o.lx = ((e / 170) | 0) % 2 ? -1 : 1;
        }
      }
      return o;
    }

    // idle, countdown, done: small glances around the room
    if (t > S.glanceUntil[id]) {
      S.glance[id] = [-1, 0, 0, 1][(Math.random() * 4) | 0];
      S.glanceUntil[id] = t + 1800 + Math.random() * 3000;
    }
    o.lx = S.glance[id];
    // between calls, somebody always has something to do
    if (S.mode === "idle" && S.fidget.id === id && t < S.fidget.until) {
      o.act = S.fidget.act;
      if (o.act === "laugh") { o.mouth = "wide"; o.squint = true; o.bob = ((t / 140) | 0) % 2; }
      if (["notes", "write", "tablet", "laptop"].includes(o.act)) o.ly = 1;
    }
    if (S.mode === "done") {
      o.lx = 0; o.mouth = "smile";
      const since = t - S.doneAt;
      if (S.winner === id && since < 5200) { o.pose = "pump"; o.bob = ((t / 260) | 0) % 2 ? -1 : 0; o.squint = true; o.mouth = "wide"; }
      else if (S.winner && id !== "hal" && since < 3600) { o.pose = "clap"; o.lx = CAST[S.winner].x < c.x ? -1 : 1; }
      else if (S.winner && id === "hal" && since < 3600) o.ly = ((since / 300) | 0) % 2;
    }
    return o;
  }
  const FIDGETS = { hal: ["miccheck", "notes"], royce: ["write", "tie", "notes"], deacon: ["coffee", "stretch"],
                    lonnie: ["tablet", "coffee", "phone"] };

  let lastT = 0;
  function frame(t, once) {
    const dt = lastT ? t - lastT : 16.7;
    lastT = t;
    updateScene(t);
    if (S.mode === "idle" && t > S.fidget.next) {
      const ids = Object.keys(CAST);
      const id = ids[(Math.random() * ids.length) | 0];
      const acts = FIDGETS[id];
      S.fidget = { id, act: acts[(Math.random() * acts.length) | 0], until: t + 3400, next: t + 6500 + Math.random() * 6000 };
      if (id === "deacon" && S.fidget.act === "coffee") S.sceneAt = t;      // start the sip from the top
    }
    // lights: dimmer before the show, full when live
    const targetDim = S.mode === "preshow" || S.mode === "countdown" ? 0.24 : 0;
    S.dim += (targetDim - S.dim) * 0.06;

    const a = S.artist;
    a.x = Math.round(lerp(a.from, a.to, (t - a.at) / 1200));
    // the producer walks in, stops at the end of the desk to talk, then walks off
    const p = S.producer;
    const since = t - p.at;
    if (since < 1400) { p.x = Math.round(lerp(344, PRODUCER_SPOT, since / 1400)); p.to = PRODUCER_SPOT; }
    else if (since < SCENE_MS - 1400) p.x = p.to = PRODUCER_SPOT;
    else { p.x = Math.round(lerp(PRODUCER_SPOT, 344, (since - (SCENE_MS - 1400)) / 1400)); p.to = 344; }

    g = screen;
    g.drawImage(bg, 0, 0);
    drawCrowdLife(t);
    drawBeams(t);
    drawFieldLife(t);
    drawOnAirSign();

    const states = {};
    for (const id in CAST) states[id] = personState(id, t);

    // spotlight on whoever is talking
    drawCone(t);

    // chairs, then people, then the desk in front of them
    for (const id in CAST) {
      const c = CAST[id], o = states[id];
      const hy = HEAD_TOP - c.tall + o.bob;
      chair(c.x, HEAD_TOP - c.tall, id === "deacon");   // the chair stays put when he stands
      drawPerson(id, c.x, hy, Object.assign({ bottom: DESK, phonesOff: S.props.phonesOff, toothpick: S.props.toothpick }, o));
      o.hy = hy;
      // arms raised above the desk
      if (o.pose === "point" || o.pose === "stand") o.hand = raisedArm(id, c.x, hy, 1, 0, true);
      if (o.pose === "away") {
        // arms crossed over the chest
        const sleeve = sleeveOf(id);
        R(c.x - c.half + 2, hy + 27, c.half * 2 - 4, 5, sleeve);
        R(c.x - c.half + 2, hy + 27, c.half * 2 - 4, 1, "rgba(255,255,255,0.15)");
        R(c.x - c.half + 3, hy + 27, 4, 4, c.skin); R(c.x + c.half - 7, hy + 28, 4, 4, c.skin);
      }
      if (o.pose === "pump") o.hand = raisedArm(id, c.x, hy, 1, ((t / 220) | 0) % 2 ? 3 : 0, true);
      if (o.pose === "handsup" || (o.act === "stretch" && o.bob)) { raisedArm(id, c.x, hy, -1, 0, false); o.hand = raisedArm(id, c.x, hy, 1, 0, false); }
      if (o.act === "miccheck") raisedArm(id, c.x, hy - 6, -1, 0, false);
      // counting points off on his fingers
      if (o.pose === "count") {
        o.hand = raisedArm(id, c.x, hy, 1, 2, false);
        const n = 1 + (((t - S.lineAt) / 650) | 0) % 3;
        for (let i = 0; i < n; i++) R(o.hand.x + i, o.hand.y - 3, 1, 3, i % 2 ? c.shade : c.skin);
      }
      // hand to the chin, thinking it over
      if (o.pose === "think") {
        R(c.x + 5, hy + 19, 4, DESK - (hy + 19), sleeveOf(id));
        R(c.x + 3, hy + 15, 5, 4, c.skin);
      }
      // applause for the winner
      if (o.pose === "clap") {
        const sep = ((t / 170) | 0) % 2 ? 0 : 3;
        const sl = sleeveOf(id);
        R(c.x - 9 - sep, hy + 27, 4, DESK - (hy + 27), sl); R(c.x + 5 + sep, hy + 27, 4, DESK - (hy + 27), sl);
        R(c.x - 6 - sep, hy + 23, 4, 4, c.skin); R(c.x + 2 + sep, hy + 23, 4, 4, c.skin);
      }
      // on the phone
      if (o.act === "phone") {
        R(c.x - 13, hy + 12, 4, DESK - (hy + 12), sleeveOf(id));
        R(c.x - 13, hy + 8, 4, 4, c.skin);
        R(c.x - 12, hy + 5, 2, 9, "#16161f"); R(c.x - 12, hy + 6, 1, 1, "#5ccfe6");
      }
    }

    drawDesk(t);
    deskBalls();

    for (const id in CAST) {
      const c = CAST[id], o = states[id], cx = c.x, hy = o.hy;
      deskItems(id, cx, t, o.act);
      const armsOff = o.pose === "away" || o.pose === "stand";   // crossed, or standing with the other arm down
      const raisedRight = armsOff || ["point", "pump", "handsup", "count", "think", "clap"].includes(o.pose) || (o.act === "stretch" && o.bob);
      const raisedLeft = armsOff || o.pose === "handsup" || o.pose === "clap" || o.act === "miccheck" || o.act === "phone" || (o.act === "stretch" && o.bob);
      const holding = o.act === "notes" || o.act === "tablet";

      if (holding) {
        if (o.act === "notes") { R(cx - 8, 101, 16, 12, "#f4f1e6"); for (let y = 103; y < 112; y += 2) R(cx - 6, y, 12, 1, "#c9c2ad"); }
        else { R(cx - 7, 101, 14, 11, "#2a2f3d"); R(cx - 7, 101, 14, 1, "#4a5268"); }
        R(cx - 10, 106, 3, 4, c.skin); R(cx + 7, 106, 3, 4, c.skin);
        R(cx - 11, 110, 4, 8, sleeveOf(id)); R(cx + 7, 110, 4, 8, sleeveOf(id));
        continue;
      }
      if (o.act === "laptop") {
        const type = ((t / 160) | 0) % 2;
        R(cx - 6, 115 + type, 4, 3, c.skin); R(cx + 2, 116 - type, 4, 3, c.skin);
        R(cx - 11, 116, 22, 3, "#454b5c");
        R(cx - 10, 102, 20, 14, "#c8cdd8"); R(cx - 10, 102, 20, 1, "#e6e9ef"); R(cx - 1, 108, 2, 2, "#9aa3b5");
        g.fillStyle = "rgba(110,190,255,0.12)"; g.fillRect(cx - 9, hy + 3, 18, 14);
        continue;
      }
      if (!raisedLeft) restArm(id, cx, -1);
      if (o.act === "tie") {
        R(cx + 3, hy + 23, c.half - 3, 4, sleeveOf(id)); R(cx - 2, hy + 21, 5, 4, c.skin);
      } else if (o.act === "write") {
        const dx = [0, 2, 1, 3][((t / 150) | 0) % 4];
        R(cx - 6, 117, 12, 3, "#efe4c2");
        R(cx + 5, 115, c.half - 6, 5, sleeveOf(id)); R(cx + 1 + dx, 115, 5, 4, c.skin);
        pencilInHand(cx + 4 + dx, 109, 0);
      } else if (o.act === "coffee") {
        const sip = ((t - S.sceneAt) % 3000) < 1100;
        if (sip) {
          R(cx + 4, hy + 18, c.half - 4, 4, sleeveOf(id));
          R(cx + 1, hy + 12, 6, 7, id === "lonnie" ? "#d8323a" : "#e9e9e9"); R(cx + 2, hy + 18, 4, 3, c.skin);
        } else {
          restArm(id, cx, 1);
          R(cx + 7, 112, 5, 6, id === "lonnie" ? "#d8323a" : "#e9e9e9");
        }
      } else if (!raisedRight) {
        restArm(id, cx, 1);
        // tapping the desk to make the point
        if (o.pose === "tap") R(cx + 5, 112 + (((t / 150) | 0) % 2) * 2, 1, 4, c.skin);
      }

      // Royce's pencil: clicks while he talks, stops when he goes cold, lies down at the close
      if (id === "royce" && S.props.pencil !== "desk" && o.act !== "write" && o.act !== "tie") {
        const click = S.speaker === "royce" && S.mode === "live" && S.props.pencil === "hand" && !S.paused ? ((t / 260) | 0) % 2 : 0;
        if (raisedRight && o.hand) pencilInHand(o.hand.x + 3, o.hand.y - 6, click);
        else if (!raisedRight) pencilInHand(cx + 5, 107, click);
        else if (o.pose === "away") pencilInHand(cx + c.half - 5, hy + 22, 0);
      }
    }

    // crew walks in front of the desk
    if (S.mode === "preshow") {
      drawArtist(t);
      drawProducer(t, p.x, null);
    }
    if (S.mode === "countdown") {
      drawArtist(t);
      drawProducer(t, PRODUCER_SPOT, S.countdown);
    }
    if (S.mode === "preshow") drawCameraOp(t);
    // dust off the desk on a slam
    if (t - S.slamAt < 400 && CAST[S.speaker]) {
      const c = CAST[S.speaker], k = (t - S.slamAt) / 400;
      g.fillStyle = `rgba(230,236,245,${(0.8 * (1 - k)).toFixed(2)})`;
      for (const dx of [-14, -8, 8, 14]) g.fillRect(c.x + dx * (1 + k), DESK - 2 - k * 6, 1, 1);
    }

    if (S.dim > 0.005) { g.fillStyle = `rgba(4,8,30,${S.dim.toFixed(3)})`; g.fillRect(0, 0, W, H); }
    drawConfetti(t, dt);
    // the lights hit full when we go to air
    const flash = 1 - (t - S.flashAt) / 380;
    if (flash > 0) { g.fillStyle = `rgba(255,250,235,${(0.55 * flash).toFixed(3)})`; g.fillRect(0, 0, W, H); }
    if (!once) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  // ---------- What app.js calls ----------
  return {
    setMode(mode) {
      const t = performance.now();
      S.mode = mode; S.modeAt = t;
      if (mode === "preshow") {
        S.scene = -1; S.props = freshProps(); S.speaker = null;
        S.step = "start"; S.stepFresh = true; S.stepCount = 0; S.fillCount = 0; S.current = null; S.nextSceneAt = 0;
        S.artist = { x: -24, from: -24, to: -24, at: t, target: null };
        S.producer = { at: -1e9, x: 344, to: 344 };
      }
      if (mode === "countdown") moveArtist(null, t);
      if (mode === "live") { S.props = freshProps(); S.speaker = null; S.flashAt = t; S.react = {}; }
      if (mode !== "live") S.speaker = null;
      if (mode === "done") S.doneAt = t;
      if (mode !== "done") { S.winner = null; S.confetti = []; }
    },
    // The winner celebrates: confetti in his color, a fist pump, and applause from the desk.
    celebrate(id) {
      S.winner = CAST[id] ? id : null;
      S.doneAt = performance.now();
      if (S.winner) spawnConfetti([ACCENT[id], "#f4b740", "#ffffff", "#d8323a"], reducedMotion ? 40 : 140);
    },
    accent(id) { return ACCENT[id] || "#f4b740"; },
    setOnAir(on) { S.onAir = on; },
    // The pipeline moved to a new step (start, research, verify, write, check, judge, close).
    setStep(step) {
      const next = STEP_ALIAS[step] || step;
      if (!STEP_SCENES[next] || next === S.step) return;
      S.step = next; S.stepFresh = true; S.stepCount = 0;
      S.nextSceneAt = Math.min(S.nextSceneAt, (S.sceneAt || 0) + 2500);
    },
    setCountdown(n) { S.countdown = n; },
    setPaused(paused) { S.paused = paused; },
    onScene(callback) { S.onScene = callback; },
    // Someone starts a line. Their bible tells set the props.
    onSlam(callback) { S.onSlam = callback; },
    speak(id, delivery, text, isCutIn) {
      S.speaker = id; S.delivery = delivery;
      S.lineAt = performance.now(); S.slammed = false;
      const lower = (text || "").toLowerCase();
      const pr = S.props;
      pr.phonesOff = id === "hal" && isCutIn;
      if (id === "royce") {
        if (lower.includes("pencil goes down") || lower.includes("pencil down")) pr.pencil = "desk";
        else if (pr.pencil !== "desk") pr.pencil = (delivery === "cold" || lower.includes("pencil stops")) ? "still" : "hand";
      }
      if (id === "deacon") {
        if (delivery === "heated") pr.heated += 1;
        if (lower.includes("toothpick") || pr.heated >= 2) pr.toothpick = false;
      }
      if (id === "lonnie") {
        const questions = (text.match(/\?/g) || []).length;
        if (delivery === "emphatic" || delivery === "heated" || questions >= 2 || lower.includes("sleeve")) pr.sleeves = true;
      }
      // a little variety in how he talks: counting off numbers, tapping the desk, thinking it over
      S.altPose = null;
      if (CAST[id]) {
        const r = Math.random();
        if (/\d/.test(text) && ["confident", "building", "calm", "warm", "curious"].includes(delivery) && r < 0.4) S.altPose = "count";
        else if (delivery === "emphatic" && r < 0.5) S.altPose = "tap";
        else if (["curious", "quiet", "calm"].includes(delivery) && (text || "").includes("?") && r < 0.5) S.altPose = "think";
      }
      // and the others react while he talks
      S.react = {};
      const now = performance.now();
      for (const other in CAST) {
        if (other === id) continue;
        const r = Math.random();
        let kind = "none";
        if (other === "hal") kind = r < 0.25 ? "nod" : "none";
        else if (delivery === "laughing") kind = r < 0.7 ? "smile" : "none";
        else if (["heated", "fired_up", "slam", "emphatic"].includes(delivery)) kind = r < 0.35 ? "raise" : r < 0.55 ? "lean" : "none";
        else if (["sarcastic", "dismissive", "cold"].includes(delivery)) kind = r < 0.3 ? "low" : r < 0.45 ? "smile" : "none";
        else kind = r < 0.25 ? "nod" : r < 0.36 ? "shake" : r < 0.44 ? "smile" : "none";
        S.react[other] = { kind, at: now + 300 + Math.random() * 900, dur: 900 + Math.random() * 900 };
      }
    },
    silence() { S.speaker = null; },
    // Where to point a speech bubble, in studio pixels.
    anchor(id) {
      if (CAST[id]) return { x: CAST[id].x, y: HEAD_TOP - CAST[id].tall - 3 };
      if (id === "artist") return { x: S.artist.to, y: 74 };      // where she's headed
      if (id === "producer") return { x: PRODUCER_SPOT, y: 76 };
      return { x: 52, y: 74 };   // the caller is on the left monitor
    },
    size: { W, H },
    // For testing: draw a single frame right now (useful when the page is in the background).
    renderOnce() { frame(performance.now(), true); },
    // The Sideline logo: a phone handset badge, SIDE on red, LINE on navy, and a
    // dashed chalk sideline underneath. Draws on a 130 x 26 canvas.
    logo(target) {
      g = target.getContext("2d");
      g.clearRect(0, 0, 130, 26);
      // handset badge
      R(1, 3, 20, 18, "#f4b740"); R(2, 2, 18, 1, "#f4b740"); R(2, 21, 18, 1, "#f4b740");
      R(5, 6, 12, 3, "#0a1433"); R(4, 7, 3, 7, "#0a1433"); R(15, 7, 3, 7, "#0a1433");
      R(7, 12, 8, 6, "#d8323a"); R(8, 13, 6, 1, "#f4f1e6"); R(8, 15, 6, 1, "#f4f1e6");
      // SIDE / LINE
      R(24, 3, 52, 18, "#d8323a"); R(24, 3, 52, 1, "#ff5a64");
      pixelText("SIDE", 27, 5, 2, "#ffffff");
      R(76, 3, 53, 18, "#11224f"); R(76, 3, 53, 1, "#2a57c9");
      pixelText("LINE", 79, 5, 2, "#ffffff");
      // chalk sideline
      for (let x = 24; x < 129; x += 7) R(x, 23, 4, 2, "#e9eefc");
      g = screen;
    },
    // A 16 x 16 pixel trophy for the end card.
    trophy(target) {
      g = target.getContext("2d");
      g.clearRect(0, 0, 16, 16);
      const gold = "#f4b740", light = "#ffe08a", dark = "#b8862a";
      R(3, 2, 10, 1, light); R(3, 3, 10, 4, gold); R(4, 7, 8, 1, gold); R(5, 8, 6, 1, gold); R(6, 9, 4, 1, dark);
      R(7, 10, 2, 2, dark); R(1, 3, 2, 1, gold); R(1, 3, 1, 3, gold); R(1, 6, 2, 1, gold);
      R(13, 3, 2, 1, gold); R(14, 3, 1, 3, gold); R(13, 6, 2, 1, gold);
      R(5, 12, 6, 1, gold); R(4, 13, 8, 2, "#7a4a1c"); R(4, 3, 1, 3, light); R(6, 14, 4, 1, light);
      g = screen;
    },
    // A 16 x 16 icon for the browser tab.
    icon(target) {
      g = target.getContext("2d");
      R(0, 0, 16, 16, "#d8323a");
      R(3, 3, 10, 2, "#ffffff"); R(2, 4, 3, 5, "#ffffff"); R(11, 4, 3, 5, "#ffffff");
      R(5, 8, 6, 4, "#f4b740");
      for (let x = 1; x < 16; x += 4) R(x, 14, 2, 1, "#ffffff");
      g = screen;
    },
    // A head-and-shoulders portrait for the monitors and the cast cards (32 x 32 canvas).
    portrait(target, id, opts = {}) {
      const pg = target.getContext("2d");
      g = pg;
      R(0, 0, 32, 32, opts.bg || "#2a57c9");
      R(0, 26, 32, 6, opts.bg2 || "#2350b8");
      if (CAST[id]) {
        drawPerson(id, 16, 6, { bottom: 32, mouth: opts.mouth || "closed", brow: opts.brow || "flat", blink: !!opts.blink,
                                lx: opts.lx || 0, phonesOff: false, toothpick: true });
      } else {
        // a phone handset for the caller
        R(9, 8, 14, 4, "#16161f"); R(7, 9, 4, 8, "#16161f"); R(21, 9, 4, 8, "#16161f");
        R(8, 16, 3, 2, "#3a3f50"); R(22, 16, 3, 2, "#3a3f50");
        R(10, 18, 12, 8, "#d8323a"); R(12, 20, 8, 1, "#f4f1e6"); R(12, 22, 8, 1, "#f4f1e6"); R(12, 24, 8, 1, "#f4f1e6");
      }
      g = screen;
    },
  };
})();
