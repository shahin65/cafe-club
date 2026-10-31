(function () {
  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  ready(function () {
    var mapEl = document.getElementById("venue-map");
    var latInput = document.getElementById("id_latitude");
    var lngInput = document.getElementById("id_longitude");
    if (!mapEl || !latInput || !lngInput || !window.L) return;

    var defaultLat = parseFloat(mapEl.dataset.defaultLat) || 35.6892;
    var defaultLng = parseFloat(mapEl.dataset.defaultLng) || 51.389;
    var lat = parseFloat(latInput.value);
    var lng = parseFloat(lngInput.value);
    var hasPoint = Number.isFinite(lat) && Number.isFinite(lng);
    var start = hasPoint ? [lat, lng] : [defaultLat, defaultLng];
    var map = L.map(mapEl).setView(start, hasPoint ? 16 : 12);
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

    var marker = L.marker(start, { draggable: true }).addTo(map);

    function write(position) {
      latInput.value = position.lat.toFixed(6);
      lngInput.value = position.lng.toFixed(6);
    }

    if (hasPoint) write(marker.getLatLng());

    marker.on("dragend", function () {
      write(marker.getLatLng());
    });
    map.on("click", function (event) {
      marker.setLatLng(event.latlng);
      write(event.latlng);
    });
    setTimeout(function () {
      map.invalidateSize();
    }, 200);
  });
})();
