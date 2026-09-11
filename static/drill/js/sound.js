/* Theme-flavored answer sounds, synthesized with the Web Audio API.
 *
 * Why synth instead of audio files: zero external assets, zero licensing,
 * works offline, and trivially varies per theme. If you later want recorded
 * SFX, drop them in and call them from here — the play(kind, theme) contract
 * stays the same. (Good CC0 sources: freesound.org, mixkit.co, kenney.nl.)
 *
 * Respects window.MFSoundMuted (toggled by ui.js). The AudioContext is created
 * lazily on the first play, which always follows a tap/keypress — satisfying
 * browsers' autoplay gesture requirement.
 */
(function () {
  let ctx = null;

  // note: {freq, dur, type, gain, t (start offset), slide (glide-to freq)}
  const SPECS = {
    pirate: {
      correct: [{ freq: 392, dur: 0.12, type: 'square', gain: 0.14 },
                { t: 0.11, freq: 523, dur: 0.18, type: 'square', gain: 0.14 }],
      wrong:   [{ freq: 196, dur: 0.24, type: 'sine', gain: 0.2, slide: 147 }],
      goal:    [{ freq: 392, dur: 0.14, type: 'square', gain: 0.14 },
                { t: 0.13, freq: 523, dur: 0.14, type: 'square', gain: 0.14 },
                { t: 0.26, freq: 659, dur: 0.30, type: 'square', gain: 0.14 }],
    },
    hightech: {
      correct: [{ freq: 660, dur: 0.08, type: 'square', gain: 0.1, slide: 990 },
                { t: 0.07, freq: 990, dur: 0.12, type: 'square', gain: 0.1 }],
      wrong:   [{ freq: 300, dur: 0.2, type: 'sawtooth', gain: 0.1, slide: 150 }],
      goal:    [{ freq: 523, dur: 0.07, type: 'square', gain: 0.1 },
                { t: 0.07, freq: 659, dur: 0.07, type: 'square', gain: 0.1 },
                { t: 0.14, freq: 784, dur: 0.07, type: 'square', gain: 0.1 },
                { t: 0.21, freq: 1046, dur: 0.24, type: 'square', gain: 0.1 }],
    },
    princess: {
      correct: [{ freq: 784, dur: 0.1, type: 'triangle', gain: 0.18 },
                { t: 0.09, freq: 1046, dur: 0.18, type: 'triangle', gain: 0.16 }],
      wrong:   [{ freq: 392, dur: 0.24, type: 'sine', gain: 0.16, slide: 311 }],
      goal:    [{ freq: 784, dur: 0.1, type: 'triangle', gain: 0.16 },
                { t: 0.1, freq: 988, dur: 0.1, type: 'triangle', gain: 0.16 },
                { t: 0.2, freq: 1318, dur: 0.28, type: 'triangle', gain: 0.16 }],
    },
    dinosaur: {
      // low and chunky: a two-note stomp
      correct: [{ freq: 196, dur: 0.13, type: 'square', gain: 0.15 },
                { t: 0.12, freq: 294, dur: 0.20, type: 'square', gain: 0.15 }],
      wrong:   [{ freq: 165, dur: 0.28, type: 'sawtooth', gain: 0.16, slide: 98 }],
      goal:    [{ freq: 196, dur: 0.15, type: 'square', gain: 0.15 },
                { t: 0.14, freq: 262, dur: 0.15, type: 'square', gain: 0.15 },
                { t: 0.28, freq: 392, dur: 0.34, type: 'square', gain: 0.15 }],
    },
    deepsea: {
      // soft sine blips that rise like a bubble
      correct: [{ freq: 523, dur: 0.14, type: 'sine', gain: 0.18, slide: 784 },
                { t: 0.13, freq: 784, dur: 0.18, type: 'sine', gain: 0.14 }],
      wrong:   [{ freq: 330, dur: 0.30, type: 'sine', gain: 0.18, slide: 196 }],
      goal:    [{ freq: 523, dur: 0.12, type: 'sine', gain: 0.16, slide: 659 },
                { t: 0.12, freq: 659, dur: 0.12, type: 'sine', gain: 0.16, slide: 880 },
                { t: 0.24, freq: 880, dur: 0.34, type: 'sine', gain: 0.16 }],
    },
    space: {
      // bright synth arpeggio, warmer than hightech's square blips
      correct: [{ freq: 587, dur: 0.09, type: 'triangle', gain: 0.15 },
                { t: 0.08, freq: 880, dur: 0.09, type: 'triangle', gain: 0.15 },
                { t: 0.16, freq: 1175, dur: 0.16, type: 'triangle', gain: 0.13 }],
      wrong:   [{ freq: 440, dur: 0.26, type: 'sawtooth', gain: 0.11, slide: 220 }],
      goal:    [{ freq: 587, dur: 0.08, type: 'triangle', gain: 0.14 },
                { t: 0.08, freq: 740, dur: 0.08, type: 'triangle', gain: 0.14 },
                { t: 0.16, freq: 880, dur: 0.08, type: 'triangle', gain: 0.14 },
                { t: 0.24, freq: 1175, dur: 0.30, type: 'triangle', gain: 0.14 }],
    },
    bakery: {
      // a warm oven-timer ding
      correct: [{ freq: 698, dur: 0.13, type: 'triangle', gain: 0.17 },
                { t: 0.12, freq: 880, dur: 0.22, type: 'triangle', gain: 0.15 }],
      wrong:   [{ freq: 349, dur: 0.26, type: 'sine', gain: 0.17, slide: 262 }],
      goal:    [{ freq: 698, dur: 0.12, type: 'triangle', gain: 0.15 },
                { t: 0.12, freq: 880, dur: 0.12, type: 'triangle', gain: 0.15 },
                { t: 0.24, freq: 1046, dur: 0.32, type: 'triangle', gain: 0.15 }],
    },
    jungle: {
      // short wooden plucks, marimba-ish
      correct: [{ freq: 440, dur: 0.09, type: 'triangle', gain: 0.17 },
                { t: 0.08, freq: 660, dur: 0.14, type: 'triangle', gain: 0.15 }],
      wrong:   [{ freq: 262, dur: 0.24, type: 'triangle', gain: 0.17, slide: 175 }],
      goal:    [{ freq: 440, dur: 0.10, type: 'triangle', gain: 0.15 },
                { t: 0.10, freq: 587, dur: 0.10, type: 'triangle', gain: 0.15 },
                { t: 0.20, freq: 880, dur: 0.30, type: 'triangle', gain: 0.15 }],
    },
  };
  SPECS.default = SPECS.pirate;

  function audio() {
    if (!ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return null;
      ctx = new AC();
    }
    if (ctx.state === 'suspended') ctx.resume();
    return ctx;
  }

  function tone(c, t0, n) {
    const o = c.createOscillator(), g = c.createGain();
    o.type = n.type || 'sine';
    o.frequency.setValueAtTime(n.freq, t0);
    if (n.slide) o.frequency.exponentialRampToValueAtTime(n.slide, t0 + n.dur);
    const peak = n.gain || 0.15;
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(peak, t0 + 0.012);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + n.dur);
    o.connect(g).connect(c.destination);
    o.start(t0);
    o.stop(t0 + n.dur + 0.03);
  }

  function play(kind, theme) {
    if (window.MFSoundMuted) return;
    const set = SPECS[theme] || SPECS.default;
    const spec = set[kind];
    if (!spec) return;
    const c = audio();
    if (!c) return;
    const start = c.currentTime + 0.01;
    spec.forEach(n => tone(c, start + (n.t || 0), n));
  }

  window.MFSound = { play };
})();
