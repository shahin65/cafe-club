(function () {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(function () {});
  }

  function isStandalone() {
    return window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
  }

  if (isStandalone()) {
    document.querySelectorAll("[data-hide-when-installed]").forEach(function (node) {
      node.hidden = true;
    });
  }

  var iosButton = document.querySelector("[data-open-ios-guide]");
  var iosGuide = document.querySelector("[data-ios-guide]");
  if (iosButton && iosGuide) {
    iosButton.addEventListener("click", function () {
      iosGuide.hidden = false;
      iosGuide.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }
})();
