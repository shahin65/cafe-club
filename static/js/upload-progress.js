(function () {
  function overlay() {
    var node = document.getElementById("cc-upload-busy");
    if (node) return node;
    node = document.createElement("div");
    node.id = "cc-upload-busy";
    node.hidden = true;
    node.innerHTML =
      '<div class="cc-upload-busy-card">' +
      '<span class="cc-upload-spinner" aria-hidden="true"></span>' +
      "<p>در حال ذخیره…</p>" +
      '<div class="cc-upload-bar"><i></i></div>' +
      "</div>";
    document.body.appendChild(node);
    return node;
  }

  function showBusy(label) {
    var node = overlay();
    var text = node.querySelector("p");
    if (text) text.textContent = label || "در حال ذخیره…";
    node.hidden = false;
    document.documentElement.classList.add("is-cc-busy");
  }

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!form || !form.matches || !form.matches("[data-upload-busy]")) return;
    if (event.defaultPrevented) return;
    var hasFile = false;
    var files = form.querySelectorAll('input[type="file"]');
    for (var i = 0; i < files.length; i += 1) {
      if (files[i].files && files[i].files.length) {
        hasFile = true;
        break;
      }
    }
    showBusy(hasFile ? "در حال آپلود و ذخیره…" : "در حال ذخیره…");
  });
})();
