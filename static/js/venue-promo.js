(function () {
  var form = document.querySelector("[data-venue-promo]");
  if (!form) return;
  var existingBox = form.querySelector("[data-existing-venue]");
  var newBox = form.querySelector("[data-new-venue]");
  var label = form.querySelector("[data-promo-submit-label]");

  function selectedPlan() {
    return form.querySelector('input[name="promo_plan"]:checked');
  }

  function selectedMode() {
    return form.querySelector('input[name="venue_mode"]:checked');
  }

  function sync() {
    form.querySelectorAll(".ad-plan-card").forEach(function (card) {
      var input = card.querySelector("input[type='radio']");
      card.classList.toggle("is-selected", Boolean(input && input.checked));
    });
    var mode = selectedMode();
    var isNew = mode && mode.value === "new";
    if (existingBox) existingBox.hidden = isNew;
    if (newBox) newBox.hidden = !isNew;
    var plan = selectedPlan();
    if (label && plan) {
      label.textContent = "پرداخت هزینه — " + (plan.getAttribute("data-price") || "");
    }
    if (isNew) {
      window.setTimeout(function () {
        window.dispatchEvent(new Event("resize"));
        try {
          document.dispatchEvent(new CustomEvent("cc:mounted"));
        } catch (err) {}
      }, 220);
    }
  }

  form.querySelectorAll("input[type='radio']").forEach(function (input) {
    input.addEventListener("change", sync);
  });
  sync();
})();
