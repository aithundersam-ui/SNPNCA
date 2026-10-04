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

  // Confirmation for destructive buttons that aren't on their own confirm page.
  document.querySelectorAll("[data-confirm]").forEach(function (el) {
    el.addEventListener("click", function (e) {
      if (!window.confirm(el.getAttribute("data-confirm"))) e.preventDefault();
    });
  });
})();
