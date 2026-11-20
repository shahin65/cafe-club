const CACHE = "cafe-club-pwa-v4";
const OFFLINE = "/static/offline.html";
const PRECACHE = ["/static/pwa-192.png", "/static/pwa-512.png", OFFLINE];

function looksLikeWaf(html) {
  var snippet = String(html || "").slice(0, 4000).toLowerCase();
  return (
    snippet.indexOf("bitninja") >= 0 ||
    snippet.indexOf("webserver unreachable") >= 0 ||
    snippet.indexOf("waf pro") >= 0
  );
}

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE).then(function (cache) {
      return cache.addAll(PRECACHE);
    }).then(function () {
      return self.skipWaiting();
    })
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (key) { return key !== CACHE; }).map(function (key) {
        return caches.delete(key);
      }));
    }).then(function () {
      return self.clients.claim();
    })
  );
});

self.addEventListener("fetch", function (event) {
  if (event.request.method !== "GET") return;
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request)
        .then(function (res) {
          if (res.status >= 500) {
            return caches.match(OFFLINE).then(function (offline) {
              return offline || res;
            });
          }
          var type = res.headers.get("content-type") || "";
          if (type.indexOf("text/html") === -1) return res;
          return res.clone().text().then(function (html) {
            if (looksLikeWaf(html)) {
              return caches.match(OFFLINE).then(function (offline) {
                return offline || res;
              });
            }
            return res;
          });
        })
        .catch(function () {
          return caches.match(OFFLINE);
        })
    );
    return;
  }
  event.respondWith(
    fetch(event.request).catch(function () {
      return caches.match(event.request);
    })
  );
});
