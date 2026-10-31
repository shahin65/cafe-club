document.addEventListener("DOMContentLoaded", function () {
  if (!window.tinymce) return;
  tinymce.baseURL = "https://cdn.jsdelivr.net/npm/tinymce@7.6.1";

  function initEditor(field) {
    if (!field || field.disabled || (field.id && tinymce.get(field.id))) return;
    var details = field.closest("details");
    if (details && !details.open) return;
    var english = field.getAttribute("data-editor-language") === "en";
    var csrf = document.querySelector("[name=csrfmiddlewaretoken]");
    var uploadUrl = field.getAttribute("data-upload-url");
    tinymce.init({
      target: field,
      license_key: "gpl",
      menubar: false,
      branding: false,
      height: 340,
      directionality: english ? "ltr" : "rtl",
      language: english ? "en" : undefined,
      plugins: "lists link image autolink directionality",
      toolbar_mode: "wrap",
      toolbar: "blocks bold italic underline | alignleft aligncenter alignright | bullist numlist | link image undo redo",
      convert_urls: false,
      relative_urls: false,
      images_upload_handler: function (blobInfo) {
        var data = new FormData();
        data.append("upload", blobInfo.blob(), blobInfo.filename());
        var headers = {};
        if (csrf) headers["X-CSRFToken"] = csrf.value;
        return fetch(uploadUrl, {
          method: "POST",
          headers: headers,
          body: data,
          credentials: "same-origin"
        }).then(function (response) {
          return response.json().then(function (payload) {
            if (!response.ok || !payload.uploaded) {
              throw new Error((payload.error && payload.error.message) || "upload");
            }
            return payload.url;
          });
        });
      }
    });
  }

  function initVisibleEditors() {
    document.querySelectorAll("textarea.page-html-editor").forEach(initEditor);
  }

  initVisibleEditors();
  document.querySelectorAll("details").forEach(function (box) {
    box.addEventListener("toggle", function () {
      if (box.open) initVisibleEditors();
    });
  });
  document.querySelectorAll("form").forEach(function (form) {
    form.addEventListener("submit", function () {
      if (window.tinymce) tinymce.triggerSave();
    });
  });
});
