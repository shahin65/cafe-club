(function () {
  var allowed = { fa: true, en: true, ar: true, tr: true, ru: true, es: true };
  var protectSelector = [
    "select",
    "option",
    "optgroup",
    "nav",
    "summary",
    "dialog",
    "[role='menu']",
    "[role='listbox']",
    "[role='tablist']",
    "[role='combobox']",
    ".tab-bar",
    ".app-bar",
    ".lang-btn",
    ".lang-grid",
    ".settings-downloads",
    ".settings-socials",
  ].join(",");

  function readLang() {
    var match = document.cookie.match(/(?:^|; )googtrans=\/fa\/([^;]+)/);
    if (match && allowed[match[1]]) {
      return match[1];
    }
    try {
      var stored = localStorage.getItem("cc-lang") || "fa";
      return allowed[stored] ? stored : "fa";
    } catch (err) {
      return "fa";
    }
  }

  function writeCookie(value) {
    document.cookie = value + "; path=/";
  }

  function setLang(code) {
    if (!allowed[code]) {
      return;
    }
    try {
      localStorage.setItem("cc-lang", code);
    } catch (err) {
      /* ignore */
    }
    if (code === "fa") {
      writeCookie("googtrans=; Max-Age=0");
    } else {
      writeCookie("googtrans=/fa/" + code);
    }
    window.location.reload();
  }

  function lockControls(root) {
    var scope = root && root.querySelectorAll ? root : document;
    var nodes = scope.querySelectorAll ? scope.querySelectorAll(protectSelector) : [];
    Array.prototype.forEach.call(nodes, function (el) {
      el.classList.add("notranslate");
      el.setAttribute("translate", "no");
    });
    if (root && root.matches && root.matches(protectSelector)) {
      root.classList.add("notranslate");
      root.setAttribute("translate", "no");
    }
  }

  window.googleTranslateElementInit = function () {
    if (!window.google || !google.translate) {
      return;
    }
    lockControls(document);
    new google.translate.TranslateElement(
      {
        pageLanguage: "fa",
        includedLanguages: "en,ar,tr,ru,es",
        autoDisplay: false,
      },
      "google_translate_element"
    );
    lockControls(document);
  };

  document.addEventListener("click", function (event) {
    var node = event.target;
    if (!node || typeof node.closest !== "function") {
      return;
    }
    var btn = node.closest("button[data-lang], .lang-btn");
    if (!btn) {
      return;
    }
    event.preventDefault();
    setLang(btn.getAttribute("data-lang"));
  });

  document.addEventListener("DOMContentLoaded", function () {
    var current = readLang();
    document.documentElement.setAttribute("data-lang", current);
    document.documentElement.setAttribute("lang", current === "fa" ? "fa" : current);
    document.documentElement.setAttribute("dir", "rtl");
    document.querySelectorAll("[data-lang]").forEach(function (btn) {
      btn.classList.toggle("is-active", btn.getAttribute("data-lang") === current);
    });
    lockControls(document);
    if (window.MutationObserver) {
      var observer = new MutationObserver(function (records) {
        records.forEach(function (record) {
          Array.prototype.forEach.call(record.addedNodes || [], function (node) {
            if (node.nodeType === 1) {
              lockControls(node);
            }
          });
        });
      });
      observer.observe(document.body, { childList: true, subtree: true });
    }
    if (current === "fa") {
      return;
    }
    var script = document.createElement("script");
    script.src = "https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit";
    document.head.appendChild(script);
  });
})();
