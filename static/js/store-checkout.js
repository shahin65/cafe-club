(function () {
  var root = document.querySelector("[data-store-checkout]");
  if (!root) return;

  var sku = root.getAttribute("data-sku") || "";
  var payload = root.getAttribute("data-payload") || "";
  var verifyUrl = root.getAttribute("data-verify-url") || "";
  var csrf = root.getAttribute("data-csrf") || "";
  var statusEl = root.querySelector("[data-checkout-status]");
  var retryBtn = root.querySelector("[data-checkout-retry]");

  function setStatus(text) {
    if (statusEl) statusEl.textContent = text;
  }

  function nativeBridge() {
    try {
      if (window.CafeClub && CafeClub.purchase) return window.CafeClub;
    } catch (err) {}
    return null;
  }

  function verify(token) {
    setStatus("در حال تایید خرید…");
    var body = new URLSearchParams();
    body.set("sku", sku);
    body.set("purchase_token", token);
    fetch(verifyUrl, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrf,
        "X-Requested-With": "XMLHttpRequest",
        Accept: "application/json",
      },
      credentials: "same-origin",
      body: body,
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { okHttp: res.ok, data: data || {} };
        });
      })
      .then(function (out) {
        if (out.data.ok) {
          var bridge = nativeBridge();
          if (bridge && typeof bridge.consume === "function") {
            bridge.consume(token);
          }
          window.location.href = out.data.next || "/";
          return;
        }
        setStatus(out.data.error || "تایید خرید ناموفق بود.");
      })
      .catch(function () {
        setStatus("ارتباط با سرور برقرار نشد.");
      });
  }

  window.CafeClubOnPurchase = function (token, error) {
    if (token) {
      verify(token);
      return;
    }
    if (error === "canceled") {
      setStatus("خرید لغو شد. برای باز کردن دوباره درگاه، تلاش دوباره را بزنید.");
      return;
    }
    setStatus(error || "اتصال به درگاه فروشگاه برقرار نشد.");
  };

  function start() {
    var bridge = nativeBridge();
    if (bridge) {
      setStatus("در حال باز کردن درگاه فروشگاه…");
      bridge.purchase(sku, payload || "");
      return;
    }
    setStatus("این پرداخت باید داخل اپلیکیشن فروشگاه انجام شود تا درگاه با قیمت محصول باز شود.");
  }

  if (retryBtn) {
    retryBtn.addEventListener("click", start);
  }
  start();
})();
