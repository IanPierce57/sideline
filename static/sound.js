/* sound.js: Sideline's theme music and sound effects (added Nov 6, 2026).

   Everything is synthesized in code with the Web Audio API: no recordings, no files, nothing
   licensed, and it's original. Music only plays between the talking (hold music while the
   segment is being made, the open, the close), so it never sits under a voice.

     Sound.attach(ctx, out)       the page's audio context and the node to play into
     Sound.hold.start() / stop()  soft hold music while you're "on hold" in the pre-show
     Sound.beep()                 a countdown beep
     Sound.open()                 the theme, timed to the broadcast wipe going on air
     Sound.close()                the closing theme, with a crowd and applause
     Sound.whoosh()               the wipe itself
     Sound.ping()                 a stat card pops up
     Sound.blip()                 the score bug changes
     Sound.slam()                 a desk slam */

const Sound = (() => {
  let ctx = null, out = null, noise = null;
  const hz = (midi) => 440 * Math.pow(2, (midi - 69) / 12);
  const ready = () => !!(ctx && out && ctx.state === "running");

  function noiseBuffer() {
    if (!noise) {
      noise = ctx.createBuffer(1, ctx.sampleRate * 2, ctx.sampleRate);
      const d = noise.getChannelData(0);
      for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    }
    return noise;
  }

  // One note with a simple envelope.
  function tone(freq, at, dur, { type = "sine", gain = 0.2, attack = 0.006, release = 0.08, detune = 0,
                                 lowpass = null, dest = out } = {}) {
    const o = ctx.createOscillator();
    o.type = type; o.frequency.value = freq; o.detune.value = detune;
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, at);
    g.gain.exponentialRampToValueAtTime(gain, at + attack);
    g.gain.setValueAtTime(gain, Math.max(at + attack, at + dur - release));
    g.gain.exponentialRampToValueAtTime(0.0001, at + dur);
    let node = o;
    if (lowpass) {
      const f = ctx.createBiquadFilter();
      f.type = "lowpass"; f.frequency.value = lowpass; f.Q.value = 0.7;
      o.connect(f); node = f;
    }
    node.connect(g).connect(dest);
    o.start(at); o.stop(at + dur + 0.03);
  }
  // A filtered burst of noise: drums, cymbals, whooshes, the crowd.
  function noiseHit(at, dur, { type = "highpass", freq = 5000, q = 0.7, gain = 0.2, attack = 0.002, sweepTo = null,
                               dest = out } = {}) {
    const src = ctx.createBufferSource();
    src.buffer = noiseBuffer();
    const f = ctx.createBiquadFilter();
    f.type = type; f.Q.value = q; f.frequency.setValueAtTime(freq, at);
    if (sweepTo) f.frequency.exponentialRampToValueAtTime(sweepTo, at + dur);
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, at);
    g.gain.exponentialRampToValueAtTime(gain, at + attack);
    g.gain.exponentialRampToValueAtTime(0.0001, at + dur);
    src.connect(f).connect(g).connect(dest);
    src.start(at, Math.random() * 0.3);
    src.stop(at + dur + 0.05);
  }

  // ---------- The band ----------
  function brass(notes, at, dur, gain = 0.06) {         // two detuned saws per note, a bright stab
    for (const n of notes) for (const d of [-8, 8]) {
      tone(hz(n), at, dur, { type: "sawtooth", gain, attack: 0.018, release: Math.min(0.3, dur * 0.5), detune: d, lowpass: 2600 });
    }
  }
  function bass(n, at, dur, gain = 0.22, dest = out) { tone(hz(n), at, dur, { type: "triangle", gain, release: Math.min(0.4, dur * 0.4), dest }); }
  function kick(at, gain = 0.5, dest = out) {
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.type = "sine";
    o.frequency.setValueAtTime(150, at); o.frequency.exponentialRampToValueAtTime(42, at + 0.25);
    g.gain.setValueAtTime(gain, at); g.gain.exponentialRampToValueAtTime(0.0001, at + 0.32);
    o.connect(g).connect(dest); o.start(at); o.stop(at + 0.35);
  }
  function snare(at, gain = 0.16, dest = out) {
    noiseHit(at, 0.15, { type: "bandpass", freq: 1900, q: 0.8, gain, dest });
    tone(190, at, 0.07, { type: "triangle", gain: gain * 0.5, dest });
  }
  function hat(at, gain = 0.04, dest = out) { noiseHit(at, 0.05, { type: "highpass", freq: 7500, gain, dest }); }
  function crash(at, gain = 0.1) { noiseHit(at, 1.7, { type: "highpass", freq: 4200, gain, attack: 0.003 }); }

  // ---------- The theme (D major, 132 beats a minute) ----------
  const E = 60 / 132 / 2;                                // an eighth note
  const D = [62, 66, 69, 74], G = [67, 71, 74], A = [69, 73, 76], DBIG = [62, 69, 74, 78];

  function whoosh(at = ctx.currentTime, rising = true) {
    noiseHit(at, 0.55, { type: "bandpass", freq: rising ? 350 : 3500, sweepTo: rising ? 4500 : 300, q: 1.2, gain: 0.09, attack: 0.25 });
  }
  // The open: three syncopated stabs, a snare roll, and the big chord landing as the wipe clears.
  function open() {
    if (!ready()) return;
    const t = ctx.currentTime + 0.03;
    whoosh(t, true);
    kick(t); crash(t, 0.07); brass(D, t, E * 0.8); bass(38, t, E * 0.9);
    brass(D, t + E * 1.5, E * 0.7); bass(38, t + E * 1.5, E * 0.7);
    kick(t + E * 3); brass(G, t + E * 3, E * 0.8); bass(43, t + E * 3, E * 0.9);
    brass(A, t + E * 4, E * 2.1); bass(45, t + E * 4, E * 2);
    for (let i = 0; i < 4; i++) snare(t + E * 4 + (i * E) / 2, 0.05 + i * 0.03);
    const hit = t + E * 6;
    kick(hit, 0.6); crash(hit, 0.15); brass(DBIG, hit, 1.15, 0.07); bass(38, hit, 1.1, 0.26);
    tone(hz(86), hit, 0.8, { type: "square", gain: 0.025, lowpass: 3200, release: 0.45 });
  }
  // The close: the stabs come back down to the home chord; the crowd and applause rise under it.
  function close() {
    if (!ready()) return;
    const t = ctx.currentTime + 0.03;
    whoosh(t, false);
    brass(A, t, E * 0.8); kick(t); bass(45, t, E * 0.9);
    brass(G, t + E * 1.5, E * 0.8); bass(43, t + E * 1.5, E * 0.8);
    brass([66, 69, 74], t + E * 3, E * 0.8); kick(t + E * 3); bass(42, t + E * 3, E * 0.9);
    const hit = t + E * 4.5;
    kick(hit, 0.55); crash(hit, 0.13); brass([62, 66, 69, 74, 78], hit, 1.9, 0.065); bass(38, hit, 1.8, 0.25);
    crowd(t + 0.3, 3.4);
    applause(t + 0.5, 3.2);
  }
  function crowd(at, dur) {                              // a low roar that swells and fades
    const src = ctx.createBufferSource();
    src.buffer = noiseBuffer(); src.loop = true;
    const f = ctx.createBiquadFilter(); f.type = "lowpass"; f.frequency.value = 850;
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, at);
    g.gain.linearRampToValueAtTime(0.07, at + dur * 0.3);
    g.gain.linearRampToValueAtTime(0.0001, at + dur);
    src.connect(f).connect(g).connect(out);
    src.start(at); src.stop(at + dur + 0.1);
  }
  function applause(at, dur) {                           // lots of tiny claps, thickest in the middle
    for (let i = 0; i < dur * 55; i++) {
      const when = at + Math.random() * dur;
      const env = Math.sin(Math.PI * ((when - at) / dur));
      noiseHit(when, 0.025 + Math.random() * 0.03, { type: "bandpass", freq: 1100 + Math.random() * 2600, q: 1.6,
                                                     gain: 0.004 + 0.045 * env });
    }
  }

  // ---------- Hold music: you're on hold while the desk gets ready ----------
  // A mellow four-bar loop at 92 beats a minute (D major seventh, B minor seventh, G major
  // seventh, A): soft keys, a bass, brushes, and a little bell figure. Quiet on purpose.
  const HOLD_BEAT = 60 / 92;
  const HOLD_BARS = [
    { chord: [62, 66, 69, 73], root: 38, bell: [78, 81, 83, 81] },
    { chord: [59, 62, 66, 69], root: 35, bell: [78, 76, 74, 76] },
    { chord: [55, 59, 62, 66], root: 31, bell: [74, 76, 78, 81] },
    { chord: [57, 61, 64, 66], root: 33, bell: [76, 73, 69, 73] },
    // the second phrase (Nov 7, 2026), so the wait doesn't loop the same ten seconds
    { chord: [64, 67, 71, 74], root: 40, bell: [79, 78, 76, 74] },     // E minor seventh
    { chord: [57, 61, 64, 67], root: 33, bell: [76, 78, 79, 81] },     // A seventh
    { chord: [62, 66, 69, 73], root: 38, bell: [81, 78, 74, 78] },     // D major seventh
    { chord: [59, 62, 66, 69], root: 35, bell: [78, 76, 73, 69] },     // B minor seventh
  ];
  const hold = { gain: null, timer: null, next: 0, bar: 0 };
  function holdBar(at, bar) {
    const b = HOLD_BARS[bar % HOLD_BARS.length], dest = hold.gain;
    for (const n of b.chord) {                           // soft keys: a warm pluck that rings
      tone(hz(n), at, HOLD_BEAT * 3.6, { type: "triangle", gain: 0.035, attack: 0.02, release: HOLD_BEAT * 2, dest });
      tone(hz(n + 12), at, HOLD_BEAT * 1.5, { type: "sine", gain: 0.012, attack: 0.01, release: HOLD_BEAT, dest });
    }
    bass(b.root, at, HOLD_BEAT * 1.4, 0.12, dest);
    bass(b.root + 7, at + HOLD_BEAT * 2.5, HOLD_BEAT * 1.2, 0.09, dest);
    for (let i = 0; i < 8; i++) hat(at + (i * HOLD_BEAT) / 2, i % 2 ? 0.012 : 0.02, dest);
    snare(at + HOLD_BEAT, 0.035, dest); snare(at + HOLD_BEAT * 3, 0.035, dest);
    const second = (bar % HOLD_BARS.length) >= 4;
    if (bar % 2 === 0 || second) b.bell.forEach((n, i) => tone(hz(n), at + HOLD_BEAT * (second ? i : 0.5 + i * 0.75), 0.5,
                                                                { type: "sine", gain: second ? 0.016 : 0.022, release: 0.4, dest }));
    if (second) hat(at + HOLD_BEAT * 3.75, 0.02, dest);                 // a little pickup into the next bar
  }
  hold.start = () => {
    if (!ready() || hold.timer) return;
    hold.gain = ctx.createGain();
    hold.gain.gain.setValueAtTime(0.0001, ctx.currentTime);
    hold.gain.gain.linearRampToValueAtTime(0.9, ctx.currentTime + 1.5);
    hold.gain.connect(out);
    hold.next = ctx.currentTime + 0.1; hold.bar = 0;
    hold.timer = setInterval(() => {                     // schedule a bar ahead, so it never stutters
      while (hold.next < ctx.currentTime + 1.2) { holdBar(hold.next, hold.bar++); hold.next += HOLD_BEAT * 4; }
    }, 200);
  };
  hold.stop = () => {
    if (!hold.timer) return;
    clearInterval(hold.timer); hold.timer = null;
    const g = hold.gain, now = ctx.currentTime;
    g.gain.cancelScheduledValues(now);
    g.gain.setValueAtTime(g.gain.value, now);
    g.gain.linearRampToValueAtTime(0.0001, now + 0.6);
    setTimeout(() => g.disconnect(), 3500);
  };

  // ---------- Little sounds ----------
  function beep() { if (ready()) tone(988, ctx.currentTime + 0.01, 0.13, { type: "square", gain: 0.045, lowpass: 3500 }); }
  function ping() {
    if (!ready()) return;
    const t = ctx.currentTime + 0.01;
    tone(hz(88), t, 0.2, { gain: 0.06 }); tone(hz(95), t + 0.07, 0.3, { gain: 0.05 });
  }
  function blip() {
    if (!ready()) return;
    const t = ctx.currentTime + 0.01;
    tone(hz(72), t, 0.06, { type: "square", gain: 0.022, lowpass: 3000 }); tone(hz(79), t + 0.05, 0.08, { type: "square", gain: 0.022, lowpass: 3000 });
  }
  function slam() {
    if (!ready()) return;
    const t = ctx.currentTime;
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.type = "square"; o.frequency.setValueAtTime(120, t); o.frequency.exponentialRampToValueAtTime(38, t + 0.18);
    g.gain.setValueAtTime(0.3, t); g.gain.exponentialRampToValueAtTime(0.001, t + 0.25);
    o.connect(g).connect(out); o.start(t); o.stop(t + 0.26);
    noiseHit(t, 0.14, { type: "bandpass", freq: 900, q: 0.9, gain: 0.22 });
    crowd(t + 0.05, 1.2);
  }

  return {
    attach(c, destination) { ctx = c; out = destination; },
    hold, beep, open, close, whoosh: () => ready() && whoosh(ctx.currentTime, true), ping, blip, slam,
  };
})();
