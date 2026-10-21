(function () {
  var RADIUS = 42;
  var LAP = 2 * Math.PI * RADIUS;
  var MIN_SECONDS = 5;
  var MAX_SECONDS = 180;
  var STORAGE_KEY = "cafe-club-turn-timers";
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
    nodes.forEach(function (osc) {
      try {
        osc.stop();
      } catch (error) {
        /* already finished */
      }
    });
    nodes.length = 0;
  }

  function scheduleBell(ctx, at, nodes) {
    var master = ctx.createGain();
    master.gain.setValueAtTime(0.0001, at);
    master.gain.exponentialRampToValueAtTime(0.9, at + 0.006);
    master.gain.exponentialRampToValueAtTime(0.0001, at + 2.1);
    master.connect(ctx.destination);

    var clickLength = Math.floor(ctx.sampleRate * 0.02);
    var clickBuffer = ctx.createBuffer(1, Math.max(clickLength, 1), ctx.sampleRate);
    var clickData = clickBuffer.getChannelData(0);
    for (var i = 0; i < clickData.length; i++) {
      clickData[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / clickData.length, 4);
    }
    var click = ctx.createBufferSource();
    var clickFilter = ctx.createBiquadFilter();
    var clickGain = ctx.createGain();
    click.buffer = clickBuffer;
    clickFilter.type = "highpass";
    clickFilter.frequency.setValueAtTime(1400, at);
    clickGain.gain.setValueAtTime(0.55, at);
    clickGain.gain.exponentialRampToValueAtTime(0.0001, at + 0.04);
    click.connect(clickFilter);
    clickFilter.connect(clickGain);
    clickGain.connect(master);
    click.start(at);
    click.stop(at + 0.05);
    nodes.push(click);

    var partials = [
      [1, 0.55, 2.0],
      [2, 0.38, 1.45],
      [2.76, 0.32, 1.05],
      [3.4, 0.2, 0.75],
      [4.52, 0.14, 0.5],
      [5.68, 0.08, 0.35]
    ];
    var pitch = 740;
    partials.forEach(function (part) {
      var osc = ctx.createOscillator();
      var gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(pitch * part[0], at);
      gain.gain.setValueAtTime(part[1], at);
      gain.gain.exponentialRampToValueAtTime(0.0001, at + part[2]);
      osc.connect(gain);
      gain.connect(master);
      osc.start(at);
      osc.stop(at + part[2] + 0.02);
      nodes.push(osc);
    });
  }

  function scheduleAlarm(endsAt, nodes) {
    var ctx = audio();
    if (!ctx) return;
    var now = ctx.currentTime;
    var elapsed = (Date.now() - endsAt) / 1000;
    [5, 10].forEach(function (mark) {
      if (mark > elapsed) scheduleBell(ctx, now + (mark - elapsed), nodes);
    });
    if (15 > elapsed) {
      var triple = now + (15 - elapsed);
      scheduleBell(ctx, triple, nodes);
      scheduleBell(ctx, triple + 0.72, nodes);
      scheduleBell(ctx, triple + 1.44, nodes);
    }
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
        delete card.dataset.alarmed;
        stopNodes(bells);
        persist();
        render();
        return;
      }
      audio();
      delete card.dataset.alarmed;
      endsAt = Date.now() + total * 1000;
      persist();
      render();
    });

    render();
    if (expired() && alarmOn) {
      card.dataset.alarmed = "1";
      scheduleAlarm(endsAt, bells);
    }
    return {
      tick: function () {
        if (!endsAt) return;
        var left = remaining();
        render();
        if (left <= 0 && alarmOn && !card.dataset.alarmed) {
          card.dataset.alarmed = "1";
          scheduleAlarm(endsAt, bells);
        }
      },
      setAlarm: function (enabled) {
        alarmOn = enabled;
        if (!enabled) {
          stopNodes(bells);
          delete card.dataset.alarmed;
        } else if (expired() && !card.dataset.alarmed) {
          card.dataset.alarmed = "1";
          scheduleAlarm(endsAt, bells);
        }
        persist();
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
