(function () {
  var form = document.querySelector("[data-ad-create]");
  if (!form) return;
  var extras = form.querySelector("[data-plan-extras]");
  var label = form.querySelector("[data-ad-submit-label]");
  var freeLabel = (label && label.textContent) || "";

  function selected() {
    return form.querySelector('input[name="promo_plan"]:checked');
  }

  function syncCards() {
    var current = selected();
    form.querySelectorAll(".ad-plan-card").forEach(function (card) {
      var input = card.querySelector('input[name="promo_plan"]');
      card.classList.toggle("is-selected", Boolean(input && input.checked));
    });
    var paid = current && current.getAttribute("data-paid") === "1";
    var needsExtras = current && current.getAttribute("data-extras") === "1";
    if (extras) extras.hidden = !needsExtras;
    if (label) {
      label.textContent = paid && current
        ? "پرداخت هزینه — " + (current.getAttribute("data-price") || "")
        : freeLabel;
    }
    if (needsExtras && extras) {
      window.setTimeout(function () {
        extras.querySelectorAll(".leaflet-container").forEach(function () {
          window.dispatchEvent(new Event("resize"));
        });
        try {
          document.dispatchEvent(new CustomEvent("cc:mounted"));
        } catch (err) {}
      }, 220);
    }
  }

  form.querySelectorAll('input[name="promo_plan"]').forEach(function (input) {
    input.addEventListener("change", syncCards);
  });
  syncCards();
})();
