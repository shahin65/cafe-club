(function () {
  var root = document.querySelector("[data-profile]");
  if (!root) return;

  var methods = root.querySelector("[data-auth-methods]");
  var openMethods = root.querySelector("[data-open-auth-methods]");
  if (openMethods && methods) {
    openMethods.addEventListener("click", function () {
      methods.hidden = false;
      methods.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
  }

  var displayForm = root.querySelector("[data-display-form]");
  var editName = root.querySelector("[data-toggle-display-form]");
  if (editName && displayForm) {
    editName.addEventListener("click", function () {
      displayForm.classList.remove("is-collapsed");
      var field = displayForm.querySelector("input[name='display_name']");
      if (field) field.focus();
    });
  }

  var tickHint = root.querySelector("[data-blue-tick-hint]");
  var tickSheet = root.querySelector("[data-blue-tick-sheet]");
  var tickClose = root.querySelector("[data-blue-tick-close]");
  if (tickHint && tickSheet) {
    tickHint.addEventListener("click", function () {
      if (typeof tickSheet.showModal === "function") tickSheet.showModal();
      else tickSheet.setAttribute("open", "");
    });
  }
  if (tickClose && tickSheet) {
    tickClose.addEventListener("click", function () {
      if (typeof tickSheet.close === "function") tickSheet.close();
      else tickSheet.removeAttribute("open");
    });
  }

  bindMessengerAuth();

  function csrfToken() {
    var node = document.querySelector("[name=csrfmiddlewaretoken]");
    return node ? node.value : "";
  }

  function bindMessengerAuth() {
    var timerTick = 0;
    var lastStart = { btn: null, url: "", label: "", ttl: 180 };

    document.addEventListener("click", function (event) {
      var node = event.target;
      if (!node || typeof node.closest !== "function") return;
      var check = node.closest("[data-messenger-check]");
      if (check) {
        event.preventDefault();
        checkMessengerLink(check);
        return;
      }
      var btn = node.closest("[data-messenger-start]");
      if (!btn || btn.disabled) return;
      event.preventDefault();
      var label = btn.getAttribute("data-messenger-label") || "پیام‌رسان";
      var popup = null;
      try {
        popup = window.open("about:blank", "cafeclub-" + (btn.id || label));
      } catch (err) {
        popup = null;
      }
      btn.disabled = true;
      showMessengerStatus(btn, "در حال اتصال به " + label + "…", false);
      fetch(btn.getAttribute("data-messenger-start"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken(),
          "X-Requested-With": "XMLHttpRequest",
        },
        body: "{}",
        credentials: "same-origin",
      })
        .then(function (response) {
          return response.json().then(function (data) {
            data.status = response.status;
            return data;
          });
        })
        .then(function (data) {
          if (!data || !data.success || !data.url) {
            closeMessengerPopup(popup);
            btn.disabled = false;
            showMessengerStatus(
              btn,
              (data && data.message) || "اتصال به " + label + " ناموفق بود.",
              true
            );
            return;
          }
          lastStart = { btn: btn, url: data.url, label: label, ttl: Number(data.ttl || 180) };
          openMessengerWindow(data.url, popup, btn, label);
          showMessengerStatus(btn, data.message || ("در " + label + " استارت را بزن."), false, data.url, label);
          if (data.mode === "link") {
            btn.disabled = false;
            showLinkCheck(btn);
            return;
          }
          showMessengerCode(data.url, label, Number(data.ttl || 180));
          btn.disabled = false;
        })
        .catch(function () {
          closeMessengerPopup(popup);
          btn.disabled = false;
          showMessengerStatus(btn, "ارتباط با سرور برقرار نشد.", true);
        });
    });

    document.addEventListener("submit", function (event) {
      var form = event.target;
      if (!form || form.id !== "messenger-code-form") return;
      event.preventDefault();
      submitMessengerCode();
    });

    function closeMessengerPopup(popup) {
      if (popup && !popup.closed) popup.close();
    }

    function openMessengerWindow(url, popup, btn, label) {
      if (popup && !popup.closed) {
        popup.location.replace(url);
        try {
          popup.focus();
        } catch (err) {}
        return;
      }
      var jump = window.open(url, "cafeclub-" + (btn.id || label));
      if (!jump) {
        showMessengerStatus(btn, "بازوی " + label + " باز نشد. از لینک زیر وارد شو.", true, url, label);
      }
    }

    function showLinkCheck(btn) {
      var check = document.getElementById("messenger-link-check");
      if (!check) return;
      check.hidden = false;
      check.disabled = false;
      check.setAttribute("data-messenger-status", btn.getAttribute("data-messenger-status") || "");
      check.setAttribute("data-messenger-label", btn.getAttribute("data-messenger-label") || "");
    }

    function checkMessengerLink(check) {
      var statusUrl = check.getAttribute("data-messenger-status");
      var label = check.getAttribute("data-messenger-label") || "پیام‌رسان";
      if (!statusUrl) return;
      check.disabled = true;
      fetch(statusUrl, {
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest" },
      })
        .then(function (response) {
          return response.json();
        })
        .then(function (data) {
          check.disabled = false;
          if (!data || !data.success) {
            showMessengerStatus(check, (data && data.message) || "هنوز متصل نشده.", true);
            return;
          }
          showMessengerStatus(check, data.message || (label + " متصل شد."), false);
          check.hidden = true;
          var btn = lastStart.btn;
          if (btn) {
            btn.classList.add("is-on");
            btn.disabled = true;
            var caption = btn.querySelector("span");
            if (caption) caption.textContent = label + " متصل است";
          }
        })
        .catch(function () {
          check.disabled = false;
          showMessengerStatus(check, "ارتباط با سرور برقرار نشد.", true);
        });
    }

    function showMessengerCode(url, label, ttl) {
      var form = document.getElementById("messenger-code-form");
      var reopen = document.getElementById("messenger-code-reopen");
      var input = document.getElementById("messenger-code");
      if (!form) return;
      form.hidden = false;
      if (reopen) {
        reopen.href = url || "#";
        reopen.textContent = "باز کردن مجدد بات " + (label || "");
      }
      if (input) {
        input.value = "";
        input.focus();
      }
      startCodeTimer(ttl);
    }

    function startCodeTimer(ttl) {
      window.clearInterval(timerTick);
      var node = document.getElementById("messenger-code-timer");
      var left = Math.max(1, Number(ttl || 180));
      function paint() {
        if (!node) return;
        var mins = Math.floor(left / 60);
        var secs = left % 60;
        node.textContent = String(mins).padStart(2, "0") + ":" + String(secs).padStart(2, "0");
      }
      paint();
      timerTick = window.setInterval(function () {
        left -= 1;
        if (left <= 0) {
          window.clearInterval(timerTick);
          left = 0;
          paint();
          showMessengerStatus(lastStart.btn, "اعتبار کد تمام شد. دوباره بات را باز کن.", true, lastStart.url, lastStart.label);
          return;
        }
        paint();
      }, 1000);
    }

    function submitMessengerCode() {
      var form = document.getElementById("messenger-code-form");
      var input = document.getElementById("messenger-code");
      var submit = document.getElementById("messenger-code-btn");
      var panel = root.querySelector("[data-messenger-verify]");
      var url = (panel && panel.getAttribute("data-messenger-verify")) || "/account/messenger/verify-code/";
      var code = input ? String(input.value || "").trim() : "";
      if (!code) {
        showMessengerStatus(lastStart.btn, "کد تایید را وارد کن.", true);
        return;
      }
      if (submit) submit.disabled = true;
      fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken(),
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({ code: code }),
        credentials: "same-origin",
      })
        .then(function (response) {
          return response.json().then(function (data) {
            data.status = response.status;
            return data;
          });
        })
        .then(function (data) {
          if (submit) submit.disabled = false;
          if (!data || !data.success) {
            showMessengerStatus(lastStart.btn, (data && data.message) || "کد تایید نادرست است.", true);
            return;
          }
          window.clearInterval(timerTick);
          showMessengerStatus(lastStart.btn, data.message || "ثبت‌نام شما انجام شد.", false);
          if (form) form.hidden = true;
          if (data.redirect) window.location.assign(data.redirect);
        })
        .catch(function () {
          if (submit) submit.disabled = false;
          showMessengerStatus(lastStart.btn, "ارتباط با سرور برقرار نشد.", true);
        });
    }

    function showMessengerStatus(btn, message, isError, url, label) {
      var status = document.getElementById("auth-status") || document.getElementById("messenger-link-status");
      if (!status) return;
      status.hidden = !message;
      status.classList.toggle("is-error", !!isError);
      status.textContent = message || "";
      if (url && isError) {
        var link = document.createElement("a");
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = " باز کردن " + (label || "بات");
        status.appendChild(link);
      }
    }
  }
})();
