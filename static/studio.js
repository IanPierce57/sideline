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
  let g = screen;             // where R() draws (the studio, or a small portrait)

  // Draw one solid rectangle of pixels.
  function R(x, y, w, h, color) {
    if (w <= 0 || h <= 0) return;
    g.fillStyle = color;
    g.fillRect(Math.round(x), Math.round(y), Math.round(w), Math.round(h));
  }

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

  // How each delivery tag moves the body.
  const POSE = {
    building: "lean", confident: "lean", emphatic: "point", heated: "pump",
    frustrated: "handsup", conceding: "handsup", laughing: "laugh",
    sarcastic: "turn", dismissive: "turn", cold: "cold", quiet: "still",
  };

  // ---------- What's happening right now ----------
  const S = {
    mode: "idle", speaker: null, delivery: "calm", paused: false,
    props: null, countdown: 0, dim: 0, modeAt: 0,
    scene: -1, sceneAt: 0, onScene: null, onAir: false,
    artist: { x: -24, from: -24, to: -24, at: 0, target: null },
    producer: { at: -1e9, x: 344, to: 344 },
    nextBlink: {}, blinkUntil: {}, glance: {}, glanceUntil: {},
  };
  function freshProps() {
    return { pencil: "hand", toothpick: true, sleeves: false, phonesOff: false, heated: 0 };
  }
  S.props = freshProps();
  for (const id in CAST) { S.nextBlink[id] = 800 + Math.random() * 3000; S.blinkUntil[id] = 0; S.glance[id] = 0; S.glanceUntil[id] = 0; }

  // ---------- Pre-show: what everyone does while the script is being written ----------
  const SCENE_MS = 6000;
  const PRODUCER_SPOT = 300;   // where the floor producer stands: the right end of the desk
  const SCENES = [
    { artist: "royce", acts: { hal: "notes", royce: "makeup", deacon: "laptop", lonnie: "tablet" },
      who: "artist", name: "Makeup", title: "Pre-show", text: "Hold still, Royce. You're shining under these lights." },
    { artist: "deacon", acts: { hal: "miccheck", royce: "write", deacon: "makeup", lonnie: "coffee" },
      who: "hal", name: "Hal Brennan", title: "Mic check", text: "Check, check. Line one, stay with me. We're close." },
    { artist: "lonnie", producer: true, acts: { hal: "notes", royce: "tie", deacon: "laptop", lonnie: "makeup" },
      who: "producer", name: "Floor producer", title: "Pre-show", text: "Two minutes, everybody! Phones away, mics on." },
    { artist: "hal", acts: { hal: "makeup", royce: "notes", deacon: "stretch", lonnie: "tablet" },
      who: "deacon", name: "Deacon Pettiford", title: "Loosening up", text: "Old linebacker habit. Gotta get the shoulders loose before kickoff." },
    { artist: null, acts: { hal: "notes", royce: "write", deacon: "laptop", lonnie: "coffee" },
      who: "royce", name: "Royce Stanhope", title: "Writing his open", text: "One image, not a list of facts. That's how you open a segment." },
    { artist: null, acts: { hal: "notes", royce: "notes", deacon: "laptop", lonnie: "tablet" },
      who: "lonnie", name: "Lonnie Fairweather", title: "Doing research", text: "Pulling up the cap sheet. I want to know who's paying who before we start." },
  ];

  // ---------- The set (drawn once, then reused every frame) ----------
  const bg = document.createElement("canvas");
  bg.width = W; bg.height = H;
  function paintBackground() {
    g = bg.getContext("2d");
    // ceiling and lighting rig
    R(0, 0, W, 7, "#060b20");
    R(0, 7, W, 2, "#26335f");
    for (let x = 6; x < W; x += 22) { R(x, 5, 6, 3, "#3a4675"); R(x + 1, 8, 4, 1, "#ffe7a1"); }
    // back wall with vertical panels
    R(0, 9, W, 95, "#1a3a93");
    for (let x = 0; x < W; x += 12) { R(x, 9, 1, 95, "#16348a"); R(x + 1, 9, 1, 95, "#1e43a3"); }
    for (let x = 6; x < W; x += 22) { g.fillStyle = "rgba(255,231,161,0.05)"; g.fillRect(x - 3, 9, 12, 34); }
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
    // floor
    R(0, 160, W, 20, "#0a1640");
    for (let y = 162; y < H; y += 3) R(0, y, W, 1, "#0c1a4b");
    g = screen;
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

  function drawDesk() {
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
    // stripes at the base
    R(36, DESK + 34, 248, 2, "#d8323a"); R(36, DESK + 36, 248, 1, "#f4b740"); R(36, DESK + 37, 248, 3, "#0c1a4a");
    g.fillStyle = "rgba(0,0,0,0.35)"; g.fillRect(30, DESK + 40, 260, 2);
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
    P(-1, 11, 2, 2, c.shade);

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
    if (o.mouth === "open") { P(-2, 14, 4, 3, "#5e1a1f"); P(-2, 14, 4, 1, "#f2f2f2"); }
    else if (o.mouth === "wide") { P(-3, 14, 6, 3, "#5e1a1f"); P(-3, 14, 6, 1, "#f2f2f2"); }
    else if (o.mouth === "smile") { P(-3, 14, 1, 1, c.lip); P(-2, 15, 4, 1, c.lip); P(2, 14, 1, 1, c.lip); }
    else P(-2, 15, 4, 1, c.lip);

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
    const index = Math.floor((t - S.modeAt) / SCENE_MS) % SCENES.length;
    if (index === S.scene) return;
    S.scene = index;
    S.sceneAt = t;
    const scene = SCENES[index];
    moveArtist(scene.artist, t);
    if (scene.producer) S.producer = { at: t, x: 344, to: PRODUCER_SPOT };
    if (S.onScene) S.onScene(scene);
  }
  function moveArtist(target, t) {
    const a = S.artist;
    a.from = a.x; a.at = t; a.target = target;
    a.to = target ? CAST[target].x - 17 : -24;
  }

  function personState(id, t) {
    const c = CAST[id];
    const o = { lx: 0, ly: 0, blink: false, squint: false, mouth: "closed", brow: "flat", pose: "rest", bob: 0, act: null };
    // blinking
    if (t >= S.nextBlink[id]) { S.blinkUntil[id] = t + 130; S.nextBlink[id] = t + 2400 + Math.random() * 4200; }
    o.blink = t < S.blinkUntil[id];

    const flap = ((t + c.x * 7) / 120 | 0) % 2 === 0;

    if (S.mode === "preshow") {
      const scene = SCENES[Math.max(0, S.scene)];
      o.act = scene.acts[id];
      const sceneTalk = scene.who === id && t - S.sceneAt > 400 && t - S.sceneAt < 4200;
      if (sceneTalk) o.mouth = flap ? "open" : "closed";
      switch (o.act) {
        case "makeup": o.blink = true; o.mouth = "closed"; break;
        case "laptop": case "notes": case "write": case "tablet": o.ly = 1; break;
        case "stretch": o.bob = ((t / 600) | 0) % 2; break;
        case "tie": o.ly = 1; break;
      }
      return o;
    }

    if (S.mode === "live" && S.speaker && !S.paused) {
      if (S.speaker === id) {
        o.pose = POSE[S.delivery] || "rest";
        o.mouth = flap ? "open" : "closed";
        if (o.pose === "laugh") { o.mouth = "wide"; o.squint = true; o.bob = ((t / 110) | 0) % 2; }
        if (o.pose === "lean") o.bob = 1;
        if (o.pose === "pump" || o.pose === "point") o.brow = "angry";
        if (o.pose === "turn") { o.brow = "raise"; o.lx = 1; }
        if (o.pose === "cold") { o.brow = "low"; o.squint = true; }
        if (o.pose === "still") o.mouth = flap ? "open" : "closed";
      } else {
        const target = S.speaker === "caller" ? 52 : (CAST[S.speaker] ? CAST[S.speaker].x : c.x);
        o.lx = target < c.x - 4 ? -1 : target > c.x + 4 ? 1 : 0;
      }
      return o;
    }

    // idle, countdown, done: small glances around the room
    if (t > S.glanceUntil[id]) {
      S.glance[id] = [-1, 0, 0, 1][(Math.random() * 4) | 0];
      S.glanceUntil[id] = t + 1800 + Math.random() * 3000;
    }
    o.lx = S.glance[id];
    if (S.mode === "done") { o.lx = 0; o.mouth = "smile"; }
    return o;
  }

  function frame(t) {
    updateScene(t);
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
    drawOnAirSign();

    const states = {};
    for (const id in CAST) states[id] = personState(id, t);

    // spotlight behind whoever is talking
    if (S.mode === "live" && CAST[S.speaker] && !S.paused) {
      const c = CAST[S.speaker];
      g.fillStyle = "rgba(255,226,150,0.07)";
      for (let i = 0; i < 4; i++) g.fillRect(c.x - 18 - i * 4, HEAD_TOP - 8 - i * 3, 36 + i * 8, 48 + i * 3);
    }

    // chairs, then people, then the desk in front of them
    for (const id in CAST) {
      const c = CAST[id], o = states[id];
      const hy = HEAD_TOP - c.tall + o.bob;
      chair(c.x, hy, id === "deacon");
      drawPerson(id, c.x, hy, Object.assign({ bottom: DESK, phonesOff: S.props.phonesOff, toothpick: S.props.toothpick }, o));
      o.hy = hy;
      // arms raised above the desk
      if (o.pose === "point") o.hand = raisedArm(id, c.x, hy, 1, 0, true);
      if (o.pose === "pump") o.hand = raisedArm(id, c.x, hy, 1, ((t / 220) | 0) % 2 ? 3 : 0, true);
      if (o.pose === "handsup" || (o.act === "stretch" && o.bob)) { raisedArm(id, c.x, hy, -1, 0, false); o.hand = raisedArm(id, c.x, hy, 1, 0, false); }
      if (o.act === "miccheck") raisedArm(id, c.x, hy - 6, -1, 0, false);
    }

    drawDesk();

    for (const id in CAST) {
      const c = CAST[id], o = states[id], cx = c.x, hy = o.hy;
      deskItems(id, cx, t, o.act);
      const raisedRight = o.pose === "point" || o.pose === "pump" || o.pose === "handsup" || (o.act === "stretch" && o.bob);
      const raisedLeft = o.pose === "handsup" || o.act === "miccheck" || (o.act === "stretch" && o.bob);
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
      }

      // Royce's pencil: clicks while he talks, stops when he goes cold, lies down at the close
      if (id === "royce" && S.props.pencil !== "desk" && o.act !== "write" && o.act !== "tie") {
        const click = S.speaker === "royce" && S.mode === "live" && S.props.pencil === "hand" && !S.paused ? ((t / 260) | 0) % 2 : 0;
        if (raisedRight && o.hand) pencilInHand(o.hand.x + 3, o.hand.y - 6, click);
        else if (!raisedRight) pencilInHand(cx + 5, 107, click);
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

    if (S.dim > 0.005) { g.fillStyle = `rgba(4,8,30,${S.dim.toFixed(3)})`; g.fillRect(0, 0, W, H); }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  // ---------- What app.js calls ----------
  return {
    setMode(mode) {
      const t = performance.now();
      S.mode = mode; S.modeAt = t;
      if (mode === "preshow") {
        S.scene = -1; S.props = freshProps(); S.speaker = null;
        S.artist = { x: -24, from: -24, to: -24, at: t, target: null };
        S.producer = { at: -1e9, x: 344, to: 344 };
      }
      if (mode === "countdown") moveArtist(null, t);
      if (mode === "live") { S.props = freshProps(); S.speaker = null; }
      if (mode !== "live") S.speaker = null;
    },
    setOnAir(on) { S.onAir = on; },
    setCountdown(n) { S.countdown = n; },
    setPaused(paused) { S.paused = paused; },
    onScene(callback) { S.onScene = callback; },
    // Someone starts a line. Their bible tells set the props.
    speak(id, delivery, text, isCutIn) {
      S.speaker = id; S.delivery = delivery;
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
    // A head-and-shoulders portrait for the monitors and the cast cards (32 x 32 canvas).
    portrait(target, id) {
      const pg = target.getContext("2d");
      g = pg;
      R(0, 0, 32, 32, "#2a57c9");
      R(0, 26, 32, 6, "#2350b8");
      if (CAST[id]) {
        drawPerson(id, 16, 6, { bottom: 32, mouth: "closed", brow: "flat", phonesOff: false, toothpick: true });
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
