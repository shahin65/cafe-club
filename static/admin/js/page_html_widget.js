document.addEventListener("DOMContentLoaded", function () {
  if (!window.tinymce) return;
  tinymce.baseURL = "https://cdn.jsdelivr.net/npm/tinymce@7.6.1";
  document.querySelectorAll("textarea.page-html-editor").forEach(function (field) {
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
  });
  document.querySelectorAll("form").forEach(function (form) {
    form.addEventListener("submit", function () {
      if (window.tinymce) tinymce.triggerSave();
    });
  });
});
