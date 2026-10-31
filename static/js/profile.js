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

  var passwordSignup = root.querySelector("[data-password-signup]");
  var openPassword = root.querySelector("[data-open-password-signup]");
  if (openPassword && passwordSignup) {
    openPassword.addEventListener("click", function () {
      passwordSignup.hidden = false;
      var field = passwordSignup.querySelector("[data-username-check]");
      if (field) field.focus();
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

  root.querySelectorAll("[data-toggle-password]").forEach(function (button) {
    button.addEventListener("click", function () {
      var wrap = button.closest(".password-field");
      var input = wrap && wrap.querySelector("input");
      if (!input) return;
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      var openIcon = button.querySelector(".eye-open");
      var offIcon = button.querySelector(".eye-off");
      if (openIcon) openIcon.hidden = show;
      if (offIcon) offIcon.hidden = !show;
    });
  });

  var usernameInput = root.querySelector("[data-username-check]");
  var tick = root.querySelector("[data-username-tick]");
  var hint = root.querySelector("[data-username-hint]");
  var timer = 0;
  function setUsernameState(ok, message) {
    if (tick) tick.hidden = !ok;
    if (usernameInput) usernameInput.classList.toggle("is-unique", !!ok);
    if (hint) hint.textContent = message || "";
  }
  function checkUsername() {
    if (!usernameInput) return;
    var value = (usernameInput.value || "").trim();
    if (!value) {
      setUsernameState(false, "");
      return;
    }
    fetch("/account/username/available/?username=" + encodeURIComponent(value), {
      headers: { Accept: "application/json" },
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        if (data.available) {
          setUsernameState(true, "");
        } else if (data.reason === "taken") {
          setUsernameState(false, "این نام کاربری قبلاً گرفته شده است.");
        } else {
          setUsernameState(false, "");
        }
      })
      .catch(function () {
        setUsernameState(false, "");
      });
  }
  if (usernameInput) {
    usernameInput.addEventListener("input", function () {
      window.clearTimeout(timer);
      timer = window.setTimeout(checkUsername, 280);
    });
  }
})();
