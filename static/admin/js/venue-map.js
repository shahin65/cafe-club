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
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap",
    }).addTo(map);

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
