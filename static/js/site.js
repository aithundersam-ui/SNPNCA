// Small progressive enhancements. Every page works without JavaScript.
(function () {
  // Q&A: show a "searching the documents" note and block double submits.
  var chatForm = document.querySelector("[data-chat-form]");
  if (chatForm) {
    var textarea = chatForm.querySelector("textarea");
    chatForm.addEventListener("submit", function () {
      chatForm.classList.add("is-busy");
      var button = chatForm.querySelector("button[type=submit]");
      if (button) button.disabled = true;
    });
    if (textarea) {
      textarea.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
          e.preventDefault();
          if (textarea.value.trim().length >= 3) chatForm.requestSubmit();
        }
      });
    }
    var latest = document.getElementById("latest");
    if (latest) latest.scrollIntoView({ block: "end" });
  }

  // Mobile menu.
  var toggle = document.querySelector("[data-menu-toggle]");
  if (toggle) {
    var menu = document.getElementById(toggle.getAttribute("aria-controls"));
    toggle.addEventListener("click", function () {
      var open = menu.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  // Show/hide password on the login page.
  document.querySelectorAll("[data-password-toggle]").forEach(function (btn) {
    var input = btn.parentNode.querySelector("input");
    if (!input) return;
    btn.hidden = false;
    btn.addEventListener("click", function () {
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.setAttribute("aria-pressed", show ? "true" : "false");
      btn.setAttribute("aria-label", btn.getAttribute(show ? "data-hide" : "data-show"));
    });
  });

  // "Go back" on error pages.
  document.querySelectorAll("[data-back]").forEach(function (link) {
    link.addEventListener("click", function (e) {
      if (window.history.length > 1) { e.preventDefault(); window.history.back(); }
    });
  });

  // Admin "Start meeting": go straight to WhatsApp with the member's chat.
  var waLink = document.querySelector("[data-auto-open]");
  if (waLink) window.location.href = waLink.href;

  // Home page membership pop-up for visitors: shown once per browser session,
  // and again whenever "Become a member" is pressed.
  var signup = document.querySelector("[data-signup-dialog]");
  if (signup && typeof signup.showModal === "function") {
    var seenKey = "signupPopupSeen";
    var seen = false;
    try { seen = window.sessionStorage.getItem(seenKey) === "1"; } catch (e) { seen = false; }
    var openSignup = function () {
      if (!signup.open) signup.showModal();
      try { window.sessionStorage.setItem(seenKey, "1"); } catch (e) { /* storage blocked */ }
    };
    signup.querySelectorAll("[data-signup-close]").forEach(function (el) {
      el.addEventListener("click", function () { signup.close(); });
    });
    signup.addEventListener("click", function (e) { if (e.target === signup) signup.close(); });
    document.querySelectorAll("[data-signup-open]").forEach(function (el) {
      el.addEventListener("click", function (e) { e.preventDefault(); openSignup(); });
    });
    if (!seen) window.setTimeout(openSignup, 1500);
  }

  // Urgent alert banner: members can hide it; it stays hidden for that alert only.
  var banner = document.querySelector("[data-alert-banner]");
  if (banner) {
    var alertKey = "alertHidden" + banner.getAttribute("data-alert-banner");
    try { if (window.localStorage.getItem(alertKey) === "1") banner.hidden = true; } catch (e) { /* storage blocked */ }
    var hideBtn = banner.querySelector("[data-alert-dismiss]");
    if (hideBtn) hideBtn.addEventListener("click", function () {
      banner.hidden = true;
      try { window.localStorage.setItem(alertKey, "1"); } catch (e) { /* storage blocked */ }
    });
  }

  // Confirmation for destructive buttons that aren't on their own confirm page.
  document.querySelectorAll("[data-confirm]").forEach(function (el) {
    el.addEventListener("click", function (e) {
      if (!window.confirm(el.getAttribute("data-confirm"))) e.preventDefault();
    });
  });
})();
