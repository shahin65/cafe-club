(function () {
  var LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
  var LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
  var waiters = [];

  function ensureCss() {
    if (document.querySelector('link[data-cc-leaflet], link[href*="leaflet"]')) return;
    var link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = LEAFLET_CSS;
    link.setAttribute("data-cc-leaflet", "1");
    document.head.appendChild(link);
  }

  function flushLeaflet() {
    if (!(window.L && window.L.map)) return;
    var queue = waiters.slice();
    waiters = [];
    queue.forEach(function (fn) {
      fn();
    });
  }

  function whenLeaflet(done) {
    if (window.L && window.L.map) {
      done();
      return;
    }
    waiters.push(done);
    if (document.querySelector("script[data-cc-leaflet-boot]")) {
      window.setTimeout(flushLeaflet, 0);
      return;
    }
    var script = document.querySelector('script[src*="leaflet"]');
    if (!script) {
      script = document.createElement("script");
      script.src = LEAFLET_JS;
      script.async = false;
      document.head.appendChild(script);
    }
    script.setAttribute("data-cc-leaflet-boot", "1");
    script.addEventListener("load", flushLeaflet);
    window.setTimeout(flushLeaflet, 0);
  }

  function writePoint(latInput, lngInput, status, position) {
    latInput.value = position.lat.toFixed(6);
    lngInput.value = position.lng.toFixed(6);
    if (status) {
      status.hidden = false;
      status.textContent = position.lat.toFixed(5) + ", " + position.lng.toFixed(5);
    }
  }

  function bindMap() {
    var mapEl = document.getElementById("venue-map");
    var latInput = document.getElementById("id_latitude");
    var lngInput = document.getElementById("id_longitude");
    if (!mapEl || !latInput || !lngInput || !window.L) return;

    mapEl.setAttribute("dir", "ltr");
    if (mapEl._ccMap) {
      try {
        mapEl._ccMap.remove();
      } catch (err) {}
      mapEl._ccMap = null;
    }

    var status = mapEl.parentNode && mapEl.parentNode.querySelector("[data-map-point]");
    var defaultLat = parseFloat(mapEl.dataset.defaultLat) || 35.6892;
    var defaultLng = parseFloat(mapEl.dataset.defaultLng) || 51.389;
    var lat = parseFloat(latInput.value);
    var lng = parseFloat(lngInput.value);
    var hasPoint = Number.isFinite(lat) && Number.isFinite(lng);
    var start = hasPoint ? [lat, lng] : [defaultLat, defaultLng];
    var map = L.map(mapEl, { tap: true }).setView(start, hasPoint ? 16 : 12);
    mapEl._ccMap = map;

    var tiles = L.tileLayer("https://tile.openstreetmap.de/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap",
    });
    var fallback = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
      {
        maxZoom: 19,
        attribution: "Tiles &copy; Esri",
      }
    );
    var failedTiles = 0;
    tiles.on("tileerror", function () {
      failedTiles += 1;
      if (failedTiles < 4 || map.hasLayer(fallback)) return;
      map.removeLayer(tiles);
      fallback.addTo(map);
    });
    tiles.addTo(map);

    var marker = L.marker(start, { draggable: true, autoPan: true }).addTo(map);

    function apply(position) {
      writePoint(latInput, lngInput, status, position);
    }

    if (hasPoint) apply(marker.getLatLng());

    marker.on("dragend", function () {
      apply(marker.getLatLng());
    });
    map.on("click", function (event) {
      marker.setLatLng(event.latlng);
      apply(event.latlng);
    });

    function resize() {
      map.invalidateSize();
    }
    [80, 250, 600].forEach(function (ms) {
      window.setTimeout(resize, ms);
    });
  }

  function boot() {
    if (!document.getElementById("venue-map")) return;
    ensureCss();
    whenLeaflet(bindMap);
  }

  document.addEventListener("cc:mounted", boot);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
