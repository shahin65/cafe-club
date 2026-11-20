(function (win, doc) {
  if (win.__ccNav) {
    return;
  }
  win.__ccNav = true;
  if (doc.body && (doc.body.getAttribute("data-deal-play") || doc.body.getAttribute("data-deal-active"))) {
    return;
  }

  var busy = false;
  var pending = null;
  var current = null;
  var inflight = null;
  var panelMap = new Map();
  var gets = new Map();
  var CACHE_MAX = 12;
  var PINNED = {
    "/": 1,
    "/ads": 1,
    "/location": 1,
    "/account/profile": 1,
  };

  function absUrl(href) {
    try {
      return new URL(href, win.location.href);
    } catch (err) {
      return null;
    }
  }

  function pathOf(url) {
    return String((url && url.pathname) || "/").replace(/\/+$/, "") || "/";
  }

  function searchOf(url) {
    var search = String((url && url.search) || "");
    return search === "?" ? "" : search;
  }

  function hereKey() {
    return pathOf(win.location) + searchOf(win.location);
  }

  function destKey(url) {
    return pathOf(url) + searchOf(url);
  }

  function isHere(url) {
    return !!url && destKey(url) === hereKey();
  }

  function canSwap(url) {
    var path = pathOf(url);
    if (path.indexOf("/admin") === 0) return false;
    if (path.indexOf("/deal") === 0) return false;
    if (path.indexOf("/large") === 0) return false;
    if (path.indexOf("/pay") === 0) return false;
    if (path.indexOf("/downloads") === 0) return false;
    if (path.indexOf("/account/login") === 0) return false;
    if (path.indexOf("/account/logout") === 0) return false;
    if (path.indexOf("/account/register") === 0) return false;
    if (path.indexOf("/account/telegram") === 0) return false;
    if (path.indexOf("/account/bale") === 0) return false;
    if (path.indexOf("/assistant") === 0) return false;
    return true;
  }

  function looksLikeWaf(html) {
    var snippet = String(html || "").slice(0, 4000).toLowerCase();
    return (
      snippet.indexOf("bitninja") >= 0 ||
      snippet.indexOf("webserver unreachable") >= 0 ||
      snippet.indexOf("waf pro") >= 0
    );
  }

  function showSoftOffline() {
    var screen = doc.querySelector("[data-offline-screen]");
    if (screen) screen.hidden = false;
  }

  function hardGo(url) {
    try {
      win.location.assign(url.href);
    } catch (err) {}
  }

  function liveHit(url) {
    var hit = panelMap.get(destKey(url));
    if (hit && hit.shell && !hit.shell.isConnected) {
      return hit;
    }
    return null;
  }

  function evictPanels(keep) {
    if (panelMap.size <= CACHE_MAX) return;
    function drop(force) {
      panelMap.forEach(function (panel, key) {
        if (panelMap.size <= CACHE_MAX) return;
        if (keep && key === keep) return;
        if (!force && PINNED[key]) return;
        if (panel && panel.shell && panel.shell.isConnected) return;
        panelMap.delete(key);
      });
    }
    drop(false);
    if (panelMap.size > CACHE_MAX) drop(true);
  }

  function captureLive() {
    var shell = doc.getElementById("cc-shell");
    if (!shell) return null;
    return {
      shell: shell,
      top: doc.getElementById("cc-chrome-top"),
      dock: doc.getElementById("cc-chrome-dock"),
      title: doc.title,
      dealPlay: doc.body.getAttribute("data-deal-play") || "",
      dealActive: doc.body.getAttribute("data-deal-active") || "",
      dealCancel: doc.body.getAttribute("data-deal-cancel") || "",
      scroll: win.pageYOffset || doc.documentElement.scrollTop || 0,
    };
  }

  function stashLive() {
    var panel = captureLive();
    if (!panel) return;
    var key = hereKey();
    panelMap.forEach(function (row, stored) {
      if (row && row.shell === panel.shell && stored !== key) {
        panelMap.delete(stored);
      }
    });
    panelMap.set(key, panel);
  }

  function panelFromHtml(html) {
    var parsed = new DOMParser().parseFromString(html, "text/html");
    var shell = parsed.getElementById("cc-shell");
    if (!shell) return null;
    return {
      shell: shell,
      top: parsed.getElementById("cc-chrome-top"),
      dock: parsed.getElementById("cc-chrome-dock"),
      title: parsed.title || "",
      dealPlay: parsed.body ? parsed.body.getAttribute("data-deal-play") || "" : "",
      dealActive: parsed.body ? parsed.body.getAttribute("data-deal-active") || "" : "",
      dealCancel: parsed.body ? parsed.body.getAttribute("data-deal-cancel") || "" : "",
      scroll: 0,
    };
  }

  function markDock(url) {
    var path = pathOf(url);
    var items = doc.querySelectorAll(".tab-bar a.tab");
    for (var i = 0; i < items.length; i += 1) {
      var href = items[i].getAttribute("href") || "";
      var itemUrl = absUrl(href);
      var itemPath = pathOf(itemUrl);
      var on = itemPath === path;
      if (itemPath !== "/" && path.indexOf(itemPath + "/") === 0) {
        on = true;
      }
      items[i].classList.toggle("is-active", on);
      if (on) items[i].setAttribute("aria-current", "page");
      else items[i].removeAttribute("aria-current");
    }
  }

  function runScripts(root) {
    if (!root) return;
    if (root.getAttribute("data-cc-bound") === "1") return;
    root.setAttribute("data-cc-bound", "1");
    var scripts = root.querySelectorAll("script");
    for (var i = 0; i < scripts.length; i += 1) {
      var old = scripts[i];
      var fresh = doc.createElement("script");
      if (old.src) {
        fresh.src = old.src;
      } else {
        fresh.textContent = old.textContent;
      }
      old.parentNode.replaceChild(fresh, old);
    }
  }

  function applyBodyFlags(panel) {
    if (panel.dealPlay) doc.body.setAttribute("data-deal-play", panel.dealPlay);
    else doc.body.removeAttribute("data-deal-play");
    if (panel.dealActive) doc.body.setAttribute("data-deal-active", panel.dealActive);
    else doc.body.removeAttribute("data-deal-active");
    if (panel.dealCancel) doc.body.setAttribute("data-deal-cancel", panel.dealCancel);
    else doc.body.removeAttribute("data-deal-cancel");
  }

  function mountPanel(panel, url, push) {
    var shell = doc.getElementById("cc-shell");
    var top = doc.getElementById("cc-chrome-top");
    var dock = doc.getElementById("cc-chrome-dock");
    if (!panel || !panel.shell || !shell) {
      hardGo(url);
      return;
    }
    if (panel.dealPlay || panel.dealActive) {
      hardGo(url);
      return;
    }
    if (destKey(url) !== hereKey()) {
      stashLive();
      shell = doc.getElementById("cc-shell");
      top = doc.getElementById("cc-chrome-top");
      dock = doc.getElementById("cc-chrome-dock");
    }
    if (panel.top && top && panel.top !== top) {
      top.replaceWith(panel.top);
    }
    if (panel.dock && dock && panel.dock !== dock) {
      dock.replaceWith(panel.dock);
    }
    if (panel.shell !== shell) {
      shell.replaceWith(panel.shell);
    }
    doc.title = panel.title || doc.title;
    applyBodyFlags(panel);
    markDock(url);
    win.scrollTo(0, panel.scroll || 0);
    if (push) {
      if (!win.__ccHist) {
        win.history.replaceState({ ccNav: 1 }, "", win.location.href);
        win.__ccHist = true;
      }
      win.history.pushState({ ccNav: 1 }, "", url.href);
    }
    runScripts(doc.getElementById("cc-shell"));
  }

  function fetchShell(url, signal) {
    var hit = liveHit(url);
    if (hit) return Promise.resolve({ panel: hit, url: url });
    var stored = panelMap.get(destKey(url));
    if (stored && stored.shell) return Promise.resolve({ panel: stored, url: url });
    var key = destKey(url);
    if (gets.has(key)) return gets.get(key);
    var req = fetch(url.href, {
      credentials: "same-origin",
      headers: {
        Accept: "text/html",
      },
      signal: signal,
    })
      .then(function (res) {
        if (!res.ok) throw new Error("nav");
        var finalUrl = absUrl(res.url) || url;
        return res.text().then(function (html) {
          if (looksLikeWaf(html)) throw new Error("waf");
          var panel = panelFromHtml(html);
          if (!panel) throw new Error("nav");
          if (panel.dealPlay || panel.dealActive) throw new Error("deal");
          panelMap.set(destKey(finalUrl), panel);
          evictPanels(destKey(finalUrl));
          return { panel: panel, url: finalUrl };
        });
      })
      .finally(function () {
        gets.delete(key);
      });
    gets.set(key, req);
    return req;
  }

  function pump() {
    if (!pending) {
      busy = false;
      inflight = null;
      current = null;
      doc.documentElement.classList.remove("is-cc-busy");
      return;
    }
    var job = pending;
    pending = null;
    current = job;
    busy = true;
    doc.documentElement.classList.add("is-cc-busy");
    markDock(job.url);
    var ctrl = new AbortController();
    inflight = ctrl;
    fetchShell(job.url, ctrl.signal)
      .then(function (payload) {
        if (pending) return;
        mountPanel(payload.panel, payload.url, job.push);
      })
      .catch(function (err) {
        if (err && err.name === "AbortError") return;
        if (!pending) {
          markDock(win.location);
          showSoftOffline();
        }
      })
      .then(function () {
        inflight = null;
        if (pending) {
          pump();
          return;
        }
        busy = false;
        doc.documentElement.classList.remove("is-cc-busy");
      });
  }

  function loadShell(url, push) {
    var key = destKey(url);
    var hit = liveHit(url);
    if (hit) {
      if (inflight) {
        try {
          inflight.abort();
        } catch (err) {}
        inflight = null;
      }
      pending = null;
      current = null;
      busy = false;
      doc.documentElement.classList.remove("is-cc-busy");
      markDock(url);
      mountPanel(hit, url, push);
      return true;
    }
    if (current && destKey(current.url) === key && !pending) {
      current.push = current.push || push;
      return true;
    }
    if (pending && destKey(pending.url) === key) {
      pending.push = pending.push || push;
      return true;
    }
    pending = { url: url, push: push };
    doc.documentElement.classList.add("is-cc-busy");
    if (inflight && current && destKey(current.url) !== key) {
      try {
        inflight.abort();
      } catch (err) {}
      inflight = null;
    }
    if (busy) return true;
    pump();
    return true;
  }

  function prefetch(href) {
    var url = absUrl(href);
    if (!url || url.origin !== win.location.origin || isHere(url) || !canSwap(url)) return;
    if (liveHit(url) || panelMap.has(destKey(url))) return;
    fetchShell(url).catch(function () {});
  }

  function prefetchWarm() {
    if (navigator.connection && navigator.connection.saveData) return;
    var extras = ["/", "/ads/", "/location/"];
    var index = 0;
    function next() {
      if (index >= extras.length) return;
      prefetch(extras[index]);
      index += 1;
      win.setTimeout(next, 700);
    }
    next();
  }

  function warmSoon() {
    if (win.requestIdleCallback) {
      win.requestIdleCallback(prefetchWarm, { timeout: 2500 });
    } else {
      win.setTimeout(prefetchWarm, 1200);
    }
  }

  function forceGo(href) {
    var url = absUrl(href);
    if (!url || url.origin !== win.location.origin) return false;
    if (url.protocol !== "http:" && url.protocol !== "https:") return false;
    if (isHere(url)) return false;
    if (!canSwap(url)) {
      hardGo(url);
      return true;
    }
    return loadShell(url, true);
  }

  function closestControl(node) {
    if (!node || typeof node.closest !== "function") return null;
    return node.closest(
      "button, label, input, textarea, select, summary, dialog, [download], [data-deal-home], [data-deal-refresh]"
    );
  }

  function hrefFrom(node) {
    if (!node || typeof node.closest !== "function") return "";
    if (closestControl(node)) return "";
    var nav = node.closest("a[href]");
    if (!nav || nav.hasAttribute("download")) return "";
    if (nav.target && nav.target !== "_self") return "";
    if (nav.classList.contains("deal-next") || nav.classList.contains("deal-host")) return "";
    var href = nav.getAttribute("href") || "";
    if (!href || href === "#" || href.charAt(0) === "#" || href.indexOf("javascript:") === 0) return "";
    return href;
  }

  function onActivate(event) {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (typeof event.button === "number" && event.button !== 0) return;
    var node = event.target;
    if (node && node.nodeType !== 1) node = node.parentElement;
    if (closestControl(node)) return;
    var href = hrefFrom(node);
    if (!href) return;
    var url = absUrl(href);
    if (!url || url.origin !== win.location.origin) return;
    event.preventDefault();
    event.stopPropagation();
    if (isHere(url)) return;
    forceGo(href);
  }

  function onHint(event) {
    var href = hrefFrom(event.target);
    if (href) prefetch(href);
  }

  win.__ccGo = forceGo;
  win.addEventListener("popstate", function () {
    var url = absUrl(win.location.href);
    if (!url || !canSwap(url)) return;
    loadShell(url, false);
  });
  doc.addEventListener("click", onActivate, true);
  doc.addEventListener("pointerenter", onHint, true);
  doc.addEventListener("pointerdown", onHint, true);
  doc.addEventListener("touchstart", onHint, { capture: true, passive: true });
  var liveShell = doc.getElementById("cc-shell");
  if (liveShell) liveShell.setAttribute("data-cc-bound", "1");
  warmSoon();
})(window, document);
