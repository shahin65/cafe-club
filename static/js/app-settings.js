(function () {
  var dialog = document.getElementById("app-settings");
  var openButton = document.querySelector("[data-open-app-settings]");
  if (!dialog || !openButton) return;

  function showPanel(name) {
    dialog.querySelectorAll("[data-panel]").forEach(function (panel) {
      panel.hidden = panel.dataset.panel !== name;
    });
  }

  openButton.addEventListener("click", function () {
    showPanel("menu");
    if (dialog.showModal) dialog.showModal();
    else dialog.setAttribute("open", "open");
  });

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
