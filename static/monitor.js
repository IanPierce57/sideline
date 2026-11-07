/* monitor.js: little animations for the center monitor while a segment is being made
   (added Nov 6, 2026). Each one is drawn in code on a tiny 88 x 40 canvas, scaled up with
   sharp pixels, and they rotate every few seconds with a burst of TV static in between.
   The first one shown matches what the pipeline is doing (pulling stats, fact-checking,
   writing, judging). None of them show numbers, so nothing here can be mistaken for a stat.

     Monitor.start(step)    show the animations, starting with the one for this step
     Monitor.setStep(step)  the pipeline moved on: switch to that step's animation
     Monitor.stop()         hide them */

const Monitor = (() => {
  const W = 88, H = 40;
  const canvas = document.getElementById("mon-anim");
  canvas.width = W; canvas.height = H;
  const g = canvas.getContext("2d");
  const title = document.getElementById("center-brand");
  const box = document.getElementById("center-anim");
  const reduced = !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);

  function R(x, y, w, h, c) {
    if (w <= 0 || h <= 0) return;
    g.fillStyle = c;
    g.fillRect(Math.round(x), Math.round(y), Math.round(w), Math.round(h));
  }
  // the same random numbers every time for a given seed (so a receipt line keeps its length)
  function hash(n) { const x = Math.sin(n * 127.1) * 43758.5453; return x - Math.floor(x); }

  // ---------- The animations ----------
  const ANIMS = {
    // X's and O's: the route draws itself, the ball arcs to the receiver
    film: { title: "FILM ROOM", draw(t) {
      for (let x = 0; x < W; x += 11) R(x, 0, 11, H, (x / 11) % 2 ? "#2a7234" : "#2f7d3a");
      for (let x = 5; x < W; x += 11) R(x, 0, 1, H, "rgba(233,238,252,0.55)");
      const O = (x, y) => { R(x - 1, y - 1, 3, 1, "#fff"); R(x - 1, y + 1, 3, 1, "#fff"); R(x - 1, y, 1, 1, "#fff"); R(x + 1, y, 1, 1, "#fff"); };
      const X = (x, y) => { R(x - 1, y - 1, 1, 1, "#ff5a64"); R(x + 1, y - 1, 1, 1, "#ff5a64"); R(x, y, 1, 1, "#ff5a64"); R(x - 1, y + 1, 1, 1, "#ff5a64"); R(x + 1, y + 1, 1, 1, "#ff5a64"); };
      for (const y of [14, 18, 22, 26]) O(26, y);
      O(20, 20); O(14, 20); O(24, 6); O(24, 34);
      for (const [x, y] of [[34, 6], [34, 34], [44, 20], [32, 14], [32, 26]]) X(x, y);
      const p = (t % 4200) / 4200;
      const route = [[24, 6], [52, 6], [68, 18]];
      const len = 28 + Math.hypot(16, 12);
      const drawn = Math.min(1, p / 0.55) * len;
      let walked = 0;
      for (let i = 0; i < route.length - 1; i++) {
        const [ax, ay] = route[i], [bx, by] = route[i + 1];
        const seg = Math.hypot(bx - ax, by - ay);
        for (let d = 0; d < seg && walked + d < drawn; d += 1) {
          if (((walked + d) | 0) % 3 === 2) continue;
          R(ax + (bx - ax) * d / seg, ay + (by - ay) * d / seg, 1, 1, "#f4b740");
        }
        walked += seg;
      }
      if (p > 0.35 && p < 0.62) {
        const k = (p - 0.35) / 0.27;
        R(20 + (68 - 20) * k, 20 + (18 - 20) * k - Math.sin(Math.PI * k) * 9, 2, 1, "#7a3f1c");
      }
      if (p >= 0.62 && p < 0.8 && ((t / 90) | 0) % 2) { R(65, 15, 7, 1, "#fff6d0"); R(65, 21, 7, 1, "#fff6d0"); R(65, 15, 1, 7, "#fff6d0"); R(71, 15, 1, 7, "#fff6d0"); }
    } },

    // a jumper from the wing: up, over, swish
    hoops: { title: "SHOOTAROUND", draw(t) {
      R(0, 0, W, H, "#141a3a");
      for (let x = 0; x < W; x += 9) R(x, 2, 1, 26, "rgba(255,255,255,0.04)");
      for (let y = 30; y < H; y++) R(0, y, W, 1, y % 2 ? "#c98a4b" : "#bf8243");
      R(82, 6, 2, 14, "#f2efe6"); R(81, 10, 1, 4, "#d8323a");
      R(73, 15, 8, 1, "#e07a2c");
      const q = t % 2800;
      const swish = q > 1150 && q < 1450;
      for (const x of [74, 76, 78, 80]) R(x, 16 + (swish ? 1 : 0), 1, 4, "#d8dde8");
      // the shooter
      const jump = q > 700 && q < 1100 ? 2 : 0;
      R(16, 18 - jump, 4, 4, "#6e4429"); R(15, 22 - jump, 6, 6, "#1f44a8"); R(16, 28 - jump, 2, 3, "#e9eefc"); R(19, 28 - jump, 2, 3, "#e9eefc");
      let bx, by;
      if (q < 800) { bx = 21; by = ((q / 140) | 0) % 2 ? 28 : 22; }
      else if (q < 1400) { const k = (q - 800) / 600; bx = 21 + (76 - 21) * k; by = 18 - Math.sin(Math.PI * k) * 16 + k * -3; }
      else { const k = Math.min(1, (q - 1400) / 500); bx = 76; by = 16 + k * 13; }
      R(bx, by, 3, 3, "#e07a2c"); R(bx + 1, by, 1, 3, "#1a1412");
    } },

    // the receipt printer: every line gets checked; the ones that can't be confirmed are crossed off
    receipt: { title: "FACT CHECK", draw(t) {
      R(0, 0, W, H, "#0e1a44");
      for (let x = 0; x < W; x += 4) R(x, 0, 1, H, "rgba(255,255,255,0.03)");
      R(24, 1, 40, 5, "#2b2f3d"); R(26, 4, 36, 1, "#0a0c14"); R(58, 2, 3, 1, ((t / 300) | 0) % 2 ? "#3ddc84" : "#1d5c38");
      const scroll = (t / 600) * 5;
      const first = Math.floor(scroll / 5);
      R(30, 5, 28, H, "#f7ecd0");
      for (let i = first - 7; i <= first; i++) {
        if (i < 0) continue;
        const y = 7 + (first - i) * 5 + (scroll % 5);          // paper feeds down from the printer
        if (y > H) continue;
        const w = 9 + Math.round(hash(i) * 9);
        R(32, y, w, 2, "#8b8270");
        if (i === first && (scroll % 5) < 2.5) continue;           // still printing
        if (hash(i + 99) < 0.22) {
          R(31, y + 1, w + 2, 1, "#d8323a");                          // crossed off
          R(52, y - 1, 1, 1, "#d8323a"); R(54, y - 1, 1, 1, "#d8323a"); R(53, y, 1, 1, "#d8323a"); R(52, y + 1, 1, 1, "#d8323a"); R(54, y + 1, 1, 1, "#d8323a");
        } else {
          R(52, y + 1, 1, 1, "#2f9e55"); R(53, y + 2, 1, 1, "#2f9e55"); R(54, y, 1, 2, "#2f9e55"); R(55, y - 1, 1, 1, "#2f9e55");
        }
      }
      R(30, 5, 28, 1, "#c9bc94");
    } },

    // classic color bars
    bars: { title: "STAND BY", draw(t) {
      const cols = ["#c0c0c0", "#c0c000", "#00c0c0", "#00c000", "#c000c0", "#c00000", "#0000c0"];
      const bw = W / 7;
      cols.forEach((c, i) => R(i * bw, 0, bw + 1, 27, c));
      ["#0000c0", "#131313", "#c000c0", "#131313", "#00c0c0", "#131313", "#c0c0c0"].forEach((c, i) => R(i * bw, 27, bw + 1, 4, c));
      R(0, 31, W, H - 31, "#1d1d1d"); R(12, 31, 16, 9, "#00214c"); R(28, 31, 16, 9, "#ffffff"); R(44, 31, 16, 9, "#32006a");
      const roll = (t / 30) % (H + 10);
      g.fillStyle = "rgba(255,255,255,0.08)"; g.fillRect(0, roll - 6, W, 4);
      for (let i = 0; i < 30; i++) R(Math.random() * W, Math.random() * H, 1, 1, "rgba(255,255,255,0.35)");
    } },

    // radar sweep over the stat database
    radar: { title: "PULLING STATS", draw(t) {
      R(0, 0, W, H, "#03140b");
      const cx = 44, cy = 20;
      for (const r of [18, 12, 6]) for (let a = 0; a < Math.PI * 2; a += 0.06) R(cx + Math.cos(a) * r, cy + Math.sin(a) * r * 0.95, 1, 1, "#0f5a2e");
      R(cx - 19, cy, 39, 1, "#0f5a2e"); R(cx, cy - 18, 1, 37, "#0f5a2e");
      const ang = (t / 650) % (Math.PI * 2);
      for (let k = 0; k < 10; k++) {
        const a = ang - k * 0.07;
        g.globalAlpha = 1 - k / 10;
        for (let d = 1; d < 18; d++) R(cx + Math.cos(a) * d, cy + Math.sin(a) * d * 0.95, 1, 1, "#3ddc84");
      }
      g.globalAlpha = 1;
      for (let i = 0; i < 7; i++) {
        const a = hash(i) * Math.PI * 2, d = 4 + hash(i + 7) * 13;
        let since = (ang - a) % (Math.PI * 2); if (since < 0) since += Math.PI * 2;
        const glow = Math.max(0, 1 - since / 2.5);
        if (glow > 0) { g.globalAlpha = glow; R(cx + Math.cos(a) * d - 1, cy + Math.sin(a) * d * 0.95 - 1, 2, 2, "#b6ffcf"); g.globalAlpha = 1; }
      }
    } },

    // lines of script typing themselves out
    typewriter: { title: "WRITERS' ROOM", draw(t) {
      R(0, 0, W, H, "#1b2347");
      R(16, 3, 56, H, "#f7ecd0"); R(16, 3, 56, 1, "#fffaf0");
      const per = 1600, n = Math.floor(t / per), k = (t % per) / per;
      for (let row = 0; row < 6; row++) {
        const line = n - 5 + row;
        if (line < 0) continue;
        const y = 7 + row * 5;
        let x = 20;
        const full = row === 5 ? k : 1;
        const words = 4 + Math.floor(hash(line) * 3);
        const limit = 20 + 46 * full;
        for (let w = 0; w < words && x < limit; w++) {
          const len = 3 + Math.floor(hash(line * 7 + w) * 6);
          R(x, y, Math.min(len, limit - x), 2, line % 4 === 0 && w === 0 ? "#d8323a" : "#4a4a55");
          x += len + 2;
        }
        if (row === 5 && ((t / 300) | 0) % 2) R(Math.min(x, limit), y - 1, 1, 4, "#141625");
      }
    } },

    // the judges weigh it: the scale tips one way, then the other (no scores)
    scales: { title: "THE JUDGES", draw(t) {
      R(0, 0, W, H, "#16307f");
      for (let y = 0; y < H; y += 3) R(0, y, W, 1, "rgba(255,255,255,0.03)");
      const cx = 44, top = 8, tilt = Math.sin(t / 700) * 4;
      R(cx - 1, top, 2, 26, "#f4b740"); R(cx - 8, 34, 16, 2, "#f4b740"); R(cx - 5, 32, 10, 2, "#b8862a");
      R(cx - 2, top - 2, 4, 3, "#ffe08a");
      for (let d = -22; d <= 22; d++) R(cx + d, top + 1 + (d / 22) * tilt, 1, 1, "#ffe08a");
      for (const side of [-1, 1]) {
        const ex = cx + side * 22, ey = top + 1 + side * tilt;
        R(ex, ey, 1, 10, "#c9d2e3");
        R(ex - 7, ey + 10, 15, 2, "#f4b740"); R(ex - 5, ey + 12, 11, 1, "#b8862a");
        R(ex - 3, ey + 7, 6, 3, "#f7ecd0"); R(ex - 2, ey + 8, 4, 1, "#8b8270");
      }
    } },
  };

  // the voices being recorded: a waveform and two level meters (added with the voices)
  ANIMS.booth = { title: "IN THE BOOTH", draw(t) {
    R(0, 0, W, H, "#0a0f24");
    for (let x = 0; x < W; x += 8) R(x, 0, 1, H, "rgba(255,255,255,0.03)");
    R(10, 20, 68, 1, "#22336f");
    for (let x = 10; x < 78; x++) {
      const k = (x - 10) / 68;
      const amp = (Math.sin(t / 90 + x * 0.55) * 0.6 + Math.sin(t / 37 + x * 1.3) * 0.4) * Math.sin(Math.PI * k) * 12;
      R(x, 20 - Math.abs(amp), 1, Math.abs(amp) * 2 + 1, "#5ccfe6");
    }
    for (const [mx, ph] of [[2, 0], [82, 2]]) {
      const level = Math.round(6 + Math.abs(Math.sin(t / 160 + ph) * Math.sin(t / 410 + ph)) * 26);
      R(mx, 4, 4, 32, "#141a3a");
      for (let y = 0; y < level; y += 2) R(mx, 35 - y, 4, 1, y > 24 ? "#ff5a64" : y > 18 ? "#f4b740" : "#3ddc84");
    }
    if (((t / 500) | 0) % 2) R(40, 3, 8, 3, "#ff3b3b");
  } };

  // What to show first for each pipeline step, then the rest in turn.
  const BY_STEP = {
    start: ["bars", "film", "hoops"], topic: ["bars", "film", "hoops"],
    research: ["radar", "film", "hoops"], verify: ["receipt", "radar", "hoops"],
    write: ["typewriter", "film", "hoops"], check: ["receipt", "typewriter", "film"],
    judge: ["scales", "hoops", "film"], close: ["bars", "scales"], voices: ["booth", "hoops", "film"],
  };
  const ROTATE_MS = 7000, STATIC_MS = 260;
  const state = { on: false, list: [], i: 0, since: 0, step: null, start: 0 };

  function order(step) {
    const first = BY_STEP[step] || BY_STEP.start;
    return [...first, ...Object.keys(ANIMS).filter((k) => !first.includes(k) && k !== "bars" && k !== "booth")];
  }
  function show(name) {
    if (title) title.textContent = ANIMS[name].title;
  }
  function frame(now) {
    if (!state.on) return;
    if (now - state.since > ROTATE_MS) {
      state.i = (state.i + 1) % state.list.length;
      state.since = now;
      show(state.list[state.i]);
    }
    const name = state.list[state.i];
    if (now - state.since < STATIC_MS && !reduced) {
      for (let y = 0; y < H; y++) for (let x = 0; x < W; x += 2) R(x, y, 2, 1, Math.random() < 0.5 ? "#1a1a1a" : "#cfcfcf");
    } else {
      ANIMS[name].draw(now - state.start);
    }
    requestAnimationFrame(frame);
  }

  return {
    start(step = "start") {
      state.list = order(step); state.i = 0; state.step = step;
      state.since = performance.now(); state.start = state.since;
      box.hidden = false;
      show(state.list[0]);
      if (!state.on) { state.on = true; requestAnimationFrame(frame); }
    },
    setStep(step) {
      if (!state.on || !step || step === state.step || !BY_STEP[step]) return;
      state.step = step;
      state.list = order(step); state.i = 0; state.since = performance.now();
      show(state.list[0]);
    },
    stop() {
      state.on = false;
      box.hidden = true;
      if (title) title.textContent = "· SIDELINE ·";
    },
  };
})();
