(function () {
  var root = document.querySelector(".catalog-sheet");
  if (!root) return;

  var confirmDialog = root.querySelector("[data-pin-confirm]");
  var removeDialog = root.querySelector("[data-pin-remove]");
  var replaceDialog = root.querySelector("[data-pin-replace]");
  var postForm = root.querySelector("[data-pin-post]");
  var pendingButton = null;
  var homeFull = root.dataset.homeFull === "1";

  function postPin(url) {
    if (!postForm || !url) return;
    postForm.action = url;
    postForm.submit();
  }

  root.querySelectorAll(".catalog-pin-btn").forEach(function (button) {
    button.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      pendingButton = button;
      if (button.dataset.pinned === "1") {
        if (removeDialog && removeDialog.showModal) removeDialog.showModal();
        return;
      }
      if (confirmDialog && confirmDialog.showModal) confirmDialog.showModal();
    });
  });

  if (confirmDialog) {
    confirmDialog.addEventListener("close", function () {
      if (confirmDialog.returnValue !== "yes" || !pendingButton) return;
      if (homeFull && replaceDialog && replaceDialog.showModal) {
        var addField = replaceDialog.querySelector("[name=add_id]");
        if (addField) addField.value = pendingButton.dataset.addId || "";
        replaceDialog.showModal();
        return;
      }
      postPin(pendingButton.dataset.pinUrl);
    });
  }

  if (removeDialog) {
    removeDialog.addEventListener("close", function () {
      if (removeDialog.returnValue !== "yes" || !pendingButton) return;
      postPin(pendingButton.dataset.pinUrl);
    });
  }

  if (replaceDialog) {
    var cancel = replaceDialog.querySelector("[data-close-dialog]");
    if (cancel) {
      cancel.addEventListener("click", function () {
        replaceDialog.close();
      });
    }
  }
})();
