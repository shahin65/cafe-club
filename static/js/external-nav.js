(function () {
  function isIOS() {
    return /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  }

  function openExternal(url) {
    if (!url) return;
    try {
      if (window.CafeClub && CafeClub.openExternal) {
        CafeClub.openExternal(url);
        return;
      }
    } catch (err) {}
    window.open(url, "_blank", "noopener,noreferrer");
  }

  document.addEventListener(
    "click",
    function (event) {
      var link = event.target.closest("a[data-nav-external]");
      if (!link) return;
      var href = link.getAttribute("href") || "";
      var iosHref = link.getAttribute("data-ios-href") || "";
      if (iosHref && isIOS()) href = iosHref;
      if (!href || href.charAt(0) === "#") return;
      event.preventDefault();
      event.stopPropagation();
      openExternal(href);
    },
    true
  );
})();
