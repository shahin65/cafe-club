(function () {
  var RADIUS = 42;
  var LAP = 2 * Math.PI * RADIUS;
  var MIN_SECONDS = 5;
  var MAX_SECONDS = 180;
  var STORAGE_KEY = "cafe-club-turn-timers";
  var RING_GAP = 900;
  var audioCtx = null;

  function readStore() {
    try {
      return JSON.parse(sessionStorage.getItem(STORAGE_KEY)) || {};
    } catch (error) {
      return {};
    }
  }

  function writeStore(store) {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(store));
  }

  function audio() {
    var Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    if (!audioCtx) audioCtx = new Ctx();
    if (audioCtx.state === "suspended") audioCtx.resume();
    return audioCtx;
  }

  function stopNodes(nodes) {
    nodes.forEach(function (node) {
      try {
        node.stop();
      } catch (error) {
        /* already finished */
      }
    });
    nodes.length = 0;
  }

  function scheduleBell(ctx, at, nodes) {
    var master = ctx.createGain();
    master.gain.setValueAtTime(0.0001, at);
    master.gain.exponentialRampToValueAtTime(0.95, at + 0.008);
    master.gain.exponentialRampToValueAtTime(0.22, at + 0.18);
    master.gain.exponentialRampToValueAtTime(0.0001, at + 1.65);
    master.connect(ctx.destination);

    var clickLength = Math.max(1, Math.floor(ctx.sampleRate * 0.018));
    var clickBuffer = ctx.createBuffer(1, clickLength, ctx.sampleRate);
    var clickData = clickBuffer.getChannelData(0);
    for (var i = 0; i < clickData.length; i++) {
      clickData[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / clickData.length, 5);
    }
    var click = ctx.createBufferSource();
    var clickFilter = ctx.createBiquadFilter();
    var clickGain = ctx.createGain();
    click.buffer = clickBuffer;
    clickFilter.type = "bandpass";
    clickFilter.frequency.setValueAtTime(2400, at);
    clickFilter.Q.setValueAtTime(0.9, at);
    clickGain.gain.setValueAtTime(0.7, at);
    clickGain.gain.exponentialRampToValueAtTime(0.0001, at + 0.05);
    click.connect(clickFilter);
    clickFilter.connect(clickGain);
    clickGain.connect(master);
    click.start(at);
    click.stop(at + 0.06);
    nodes.push(click);

    var pitch = 880;
    var carrier = ctx.createOscillator();
    var modulator = ctx.createOscillator();
    var modGain = ctx.createGain();
    var clang = ctx.createGain();
    carrier.type = "sine";
    modulator.type = "sine";
    carrier.frequency.setValueAtTime(pitch, at);
    modulator.frequency.setValueAtTime(pitch * 2.4, at);
    modGain.gain.setValueAtTime(pitch * 3.2, at);
    modGain.gain.exponentialRampToValueAtTime(18, at + 0.28);
    clang.gain.setValueAtTime(0.42, at);
    clang.gain.exponentialRampToValueAtTime(0.0001, at + 0.55);
    modulator.connect(modGain);
    modGain.connect(carrier.frequency);
    carrier.connect(clang);
    clang.connect(master);
    carrier.start(at);
    modulator.start(at);
    carrier.stop(at + 0.6);
    modulator.stop(at + 0.6);
    nodes.push(carrier, modulator);

    var partials = [
      [0.5, 0.18, 1.35],
      [1, 0.62, 1.6],
      [2, 0.28, 1.05],
      [2.76, 0.36, 1.2],
      [4.07, 0.16, 0.7],
      [5.4, 0.1, 0.48]
    ];
    partials.forEach(function (part) {
      var osc = ctx.createOscillator();
      var gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(pitch * part[0], at);
      osc.frequency.exponentialRampToValueAtTime(pitch * part[0] * 0.985, at + part[2]);
      gain.gain.setValueAtTime(part[1], at);
      gain.gain.exponentialRampToValueAtTime(0.0001, at + part[2]);
      osc.connect(gain);
      gain.connect(master);
      osc.start(at);
      osc.stop(at + part[2] + 0.02);
      nodes.push(osc);
    });
  }

  function ringNow(nodes) {
    var ctx = audio();
    if (!ctx) return;
    if (nodes.length > 30) stopNodes(nodes);
    scheduleBell(ctx, ctx.currentTime, nodes);
  }

  function paint(card, total, remaining) {
    var elapsed = Math.min(total, Math.max(0, total - remaining));
    var fill = card.querySelector(".timer-fill");
    fill.style.strokeDasharray = String(LAP);
    fill.style.strokeDashoffset = String(LAP * (1 - elapsed / total));
    var shown = remaining <= 0 ? 0 : Math.ceil(remaining - 1e-6);
    card.querySelector(".timer-count").textContent = String(shown);
  }

  function setup(card, store) {
    var key = card.dataset.timer;
    var saved = store[key] || {};
    var total = saved.total || Number(card.dataset.seconds);
    var endsAt = saved.endsAt || null;
    var alarmOn = store.alarm !== false;
    var bells = [];
    var lastRing = 0;

    function persist() {
      store[key] = {total: total, endsAt: endsAt};
      store.alarm = alarmOn;
      writeStore(store);
    }

    function remaining() {
      if (!endsAt) return total;
      return Math.max(0, (endsAt - Date.now()) / 1000);
    }

    function running() {
      return Boolean(endsAt) && remaining() > 0;
    }

    function expired() {
      return Boolean(endsAt) && remaining() <= 0;
    }

    function render() {
      paint(card, total, endsAt ? remaining() : total);
      var run = card.querySelector(".timer-run");
      run.textContent = endsAt ? run.dataset.end : run.dataset.start;
      card.querySelectorAll(".timer-step").forEach(function (button) {
        button.disabled = Boolean(endsAt);
      });
      card.classList.toggle("is-running", running());
      card.classList.toggle("is-expired", expired());
    }

    function hush() {
      lastRing = 0;
      stopNodes(bells);
    }

    function ringWhileExpired() {
      if (!expired() || !alarmOn) return;
      var now = Date.now();
      if (lastRing && now - lastRing < RING_GAP) return;
      lastRing = now;
      ringNow(bells);
    }

    card.querySelectorAll(".timer-step").forEach(function (button) {
      button.addEventListener("click", function () {
        if (endsAt) return;
        total = Math.min(MAX_SECONDS, Math.max(MIN_SECONDS, total + Number(button.dataset.step)));
        persist();
        render();
      });
    });

    card.querySelector(".timer-run").addEventListener("click", function () {
      if (endsAt) {
        endsAt = null;
        hush();
        persist();
        render();
        return;
      }
      audio();
      hush();
      endsAt = Date.now() + total * 1000;
      persist();
      render();
    });

    render();
    ringWhileExpired();
    return {
      tick: function () {
        if (!endsAt) return;
        render();
        ringWhileExpired();
      },
      setAlarm: function (enabled) {
        alarmOn = enabled;
        if (!enabled) hush();
        persist();
        ringWhileExpired();
      }
    };
  }

  var root = document.querySelector(".turn-timers");
  if (!root) return;
  var store = readStore();
  var timers = [];
  root.querySelectorAll(".turn-timer").forEach(function (card) {
    timers.push(setup(card, store));
  });
  var alarmButton = root.querySelector(".alarm-toggle");
  function paintAlarm() {
    var on = store.alarm !== false;
    alarmButton.setAttribute("aria-pressed", on ? "true" : "false");
    alarmButton.classList.toggle("is-off", !on);
  }
  paintAlarm();
  alarmButton.addEventListener("click", function () {
    store.alarm = store.alarm === false;
    paintAlarm();
    writeStore(store);
    timers.forEach(function (timer) {
      timer.setAlarm(store.alarm !== false);
    });
  });
  window.setInterval(function () {
    timers.forEach(function (timer) {
      timer.tick();
    });
  }, 100);
})();
