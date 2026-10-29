(function () {
  var root = document.querySelector("[data-places], [data-filter-bar], .venue-sheet");
  if (!root) return;

  var status = root.querySelector("[data-geo-status]");
  var sheet = root.querySelector("[data-nav-sheet]");
  var params = new URLSearchParams(window.location.search);

  function setStatus(text) {
    if (!status) return;
    status.hidden = !text;
    status.textContent = text || "";
  }

  function closePanels() {
    root.querySelectorAll("[data-panel]").forEach(function (panel) {
      panel.hidden = true;
    });
    root.querySelectorAll("[data-toggle-panel]").forEach(function (btn) {
      btn.setAttribute("aria-expanded", "false");
      btn.classList.remove("is-open");
    });
  }

  root.querySelectorAll("[data-toggle-panel]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var id = btn.getAttribute("data-toggle-panel");
      var panel = root.querySelector('[data-panel="' + id + '"]');
      if (!panel) return;
      var willOpen = panel.hidden;
      closePanels();
      if (willOpen) {
        panel.hidden = false;
        btn.setAttribute("aria-expanded", "true");
        btn.classList.add("is-open");
        var field = panel.querySelector("select, input[type=search], input[type=text]");
        if (field) field.focus();
      }
    });
  });

  function withCoords(callback) {
    if (!navigator.geolocation) {
      setStatus("مرورگر شما موقعیت مکانی را پشتیبانی نمی‌کند.");
      return;
    }
    setStatus("در حال دریافت موقعیت شما…");
    navigator.geolocation.getCurrentPosition(
      function (position) {
        setStatus("");
        callback(position.coords.latitude, position.coords.longitude);
      },
      function () {
        setStatus("برای پیشنهاد نزدیک‌ترین مکان، اجازه دسترسی به موقعیت را بدهید.");
      },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 30000 }
    );
  }

  function reloadWithPoint(lat, lng, openNav) {
    params.set("lat", lat.toFixed(6));
    params.set("lng", lng.toFixed(6));
    if (!params.get("sort") || params.get("sort") === "rating") params.set("sort", "distance");
    if (openNav) params.set("nav", "1");
    else params.delete("nav");
    window.location.search = params.toString();
  }

  var nearest = root.querySelector("[data-open-nearest]");
  if (nearest) {
    nearest.addEventListener("click", function () {
      closePanels();
      if (params.get("lat") && params.get("lng")) {
        if (sheet) sheet.showModal();
        return;
      }
      withCoords(function (lat, lng) {
        reloadWithPoint(lat, lng, true);
      });
    });
  }

  var openNav = root.querySelector("[data-open-nav]");
  if (openNav && sheet) {
    openNav.addEventListener("click", function () {
      sheet.showModal();
    });
  }

  if (root.hasAttribute("data-open-nav-on-load") && sheet && params.get("nav") === "1") {
    sheet.showModal();
  }

  if (root.hasAttribute("data-ask-geo") && !params.get("lat")) {
    withCoords(function (lat, lng) {
      reloadWithPoint(lat, lng, false);
    });
  }
})();
