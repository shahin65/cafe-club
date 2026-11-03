(function () {
  var sheet = document.querySelector("[data-call-sheet]");
  var display = document.querySelector("[data-call-display]");
  var confirmBtn = document.querySelector("[data-call-confirm]");
  var pending = "";
  var digits = "0123456789";
  var persian = "۰۱۲۳۴۵۶۷۸۹";
  var arabic = "٠١٢٣٤٥٦٧٨٩";

  function toTel(value) {
    var out = "";
    String(value || "").split("").forEach(function (ch) {
      var index = persian.indexOf(ch);
      if (index < 0) index = arabic.indexOf(ch);
      if (index >= 0) ch = digits.charAt(index);
      if (ch === "+" && !out) out = "+";
      else if (digits.indexOf(ch) >= 0) out += ch;
    });
    return out;
  }

  function openCall(number) {
    pending = toTel(number);
    if (!pending || !sheet) return;
    if (display) {
      var shown = pending;
      if ((document.documentElement.lang || "").indexOf("fa") === 0) {
        shown = pending.replace(/\d/g, function (digit) {
          return persian.charAt(Number(digit));
        });
      }
      display.textContent = shown;
    }
    if (typeof sheet.showModal === "function") sheet.showModal();
  }

  document.addEventListener(
    "click",
    function (event) {
      var trigger = event.target.closest("[data-call]");
      if (!trigger) return;
      event.preventDefault();
      event.stopPropagation();
      openCall(trigger.getAttribute("data-call"));
    },
    true
  );

  if (confirmBtn) {
    confirmBtn.addEventListener("click", function () {
      if (sheet && sheet.open) sheet.close();
      if (!pending) return;
      var tel = "tel:" + pending;
      try {
        if (window.CafeClub && CafeClub.openExternal) {
          CafeClub.openExternal(tel);
          return;
        }
      } catch (err) {}
      window.location.href = tel;
    });
  }
})();
