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

  var offlineScreen = document.querySelector("[data-offline-screen]");
  var retryButton = document.querySelector("[data-offline-retry]");
  function showOffline() {
    if (offlineScreen) offlineScreen.hidden = false;
  }
  function hideOffline() {
    if (offlineScreen) offlineScreen.hidden = true;
  }
  if (offlineScreen) {
    var offlineTimer;
    window.addEventListener("offline", function () {
      clearTimeout(offlineTimer);
      offlineTimer = setTimeout(function () {
        if (!navigator.onLine) showOffline();
      }, 600);
    });
    window.addEventListener("online", function () {
      clearTimeout(offlineTimer);
      hideOffline();
    });
    if (!navigator.onLine) showOffline();
  }
  if (retryButton) {
    retryButton.addEventListener("click", function () {
      if (window.CafeClub && CafeClub.retry) {
        CafeClub.retry();
        return;
      }
      hideOffline();
      if (navigator.onLine) {
        window.location.reload();
        return;
      }
      showOffline();
    });
  }
})();
