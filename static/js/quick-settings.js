(function () {
  var dialog = document.getElementById("quick-settings");
  var openButton = document.querySelector("[data-open-settings]");
  if (!dialog || !openButton) return;

  function hydrateLogos() {
    dialog.querySelectorAll("img[data-src]").forEach(function (img) {
      if (!img.getAttribute("src")) {
        img.src = img.getAttribute("data-src");
      }
    });
  }

  function showPanel(name) {
    dialog.querySelectorAll("[data-panel]").forEach(function (panel) {
      panel.hidden = panel.dataset.panel !== name;
    });
    if (name === "logo") hydrateLogos();
  }

  function openSettings(panel) {
    showPanel(panel || "menu");
    if (dialog.showModal) dialog.showModal();
    else dialog.setAttribute("open", "open");
  }

  openButton.addEventListener("click", function () {
    openSettings("menu");
  });

  if (new URLSearchParams(window.location.search).get("logo") === "1") {
    openSettings("logo");
  }

  dialog.addEventListener("click", function (event) {
    if (event.target === dialog && dialog.close) dialog.close();
  });

  dialog.querySelectorAll("[data-close-settings]").forEach(function (button) {
    button.addEventListener("click", function () {
      if (dialog.close) dialog.close();
    });
  });

  dialog.querySelectorAll("[data-panel-target]").forEach(function (button) {
    button.addEventListener("click", function () {
      showPanel(button.dataset.panelTarget);
    });
  });
})();
