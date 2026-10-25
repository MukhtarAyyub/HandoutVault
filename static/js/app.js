/*
 * HandoutVault - tiny UI helpers. No libraries, and no inline code anywhere
 * in the templates, so it works under the site's strict Content-Security-Policy.
 *
 * Loaded in <head> on purpose: the theme is applied before the first paint,
 * so a dark-mode phone never flashes white.
 *
 *   1. Theme        light / dark. Follows the phone until the user taps the
 *                   toggle; then their choice is remembered on this device.
 *   2. Auto-submit  <form data-autosubmit>: changing a <select> applies the
 *                   filters straight away. (Without JavaScript the search
 *                   button applies them - the form works either way.)
 *   3. Dismiss      the x on a message banner removes it.
 *   4. Tidy URLs    empty filters aren't sent, so a filtered link reads ?level=200
 *                   instead of ?q=&faculty=&department=&course=&level=200&...
 */
(function () {
  "use strict";

  var root = document.documentElement;
  var KEY = "hv-theme";
  var LIGHT_COLOUR = "#d8ecf8";
  var DARK_COLOUR = "#050a17";

  function stored() {
    try { return window.localStorage.getItem(KEY); } catch (e) { return null; }
  }
  function remember(theme) {
    try { window.localStorage.setItem(KEY, theme); } catch (e) { /* private mode: just don't persist */ }
  }
  function systemTheme() {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  function current() {
    return root.getAttribute("data-theme") || systemTheme();
  }
  function apply(theme) {
    root.setAttribute("data-theme", theme);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) { meta.setAttribute("content", theme === "dark" ? DARK_COLOUR : LIGHT_COLOUR); }
    var toggles = document.querySelectorAll("[data-theme-toggle]");
    for (var i = 0; i < toggles.length; i++) {
      toggles[i].setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
    }
  }

  root.classList.add("js");
  apply(stored() || systemTheme());

  // Follow the phone's setting live, unless the user has picked a theme themselves.
  if (window.matchMedia) {
    var query = window.matchMedia("(prefers-color-scheme: dark)");
    var follow = function (e) { if (!stored()) { apply(e.matches ? "dark" : "light"); } };
    if (query.addEventListener) { query.addEventListener("change", follow); }
    else if (query.addListener) { query.addListener(follow); }
  }

  // The toggle buttons don't exist yet while this runs in <head>; sync them once they do.
  document.addEventListener("DOMContentLoaded", function () { apply(current()); });

  document.addEventListener("click", function (event) {
    var target = event.target;
    if (!target || !target.closest) { return; }

    if (target.closest("[data-theme-toggle]")) {
      var next = current() === "dark" ? "light" : "dark";
      remember(next);
      apply(next);
      return;
    }
    var dismiss = target.closest("[data-dismiss]");
    if (dismiss) {
      var banner = dismiss.closest(".flash");
      if (banner && banner.parentNode) { banner.parentNode.removeChild(banner); }
    }
  });

  // Disable empty fields just before submitting so they are left out of the URL...
  function stripEmpty(form) {
    for (var i = 0; i < form.elements.length; i++) {
      var el = form.elements[i];
      if (el.name && !el.disabled && el.value === "") { el.setAttribute("data-was-empty", ""); el.disabled = true; }
    }
  }
  // ...and switch them back on if the page is restored from the Back button (browsers keep the DOM as it was).
  function restoreEmpty() {
    var held = document.querySelectorAll("form[data-autosubmit] [data-was-empty]");
    for (var i = 0; i < held.length; i++) { held[i].removeAttribute("data-was-empty"); held[i].disabled = false; }
  }
  window.addEventListener("pageshow", restoreEmpty);

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (form && form.hasAttribute && form.hasAttribute("data-autosubmit")) { stripEmpty(form); }
  });

  document.addEventListener("change", function (event) {
    var field = event.target;
    var form = field && field.form;
    if (form && form.hasAttribute("data-autosubmit") && field.tagName === "SELECT") {
      stripEmpty(form);   // form.submit() doesn't fire the submit event above
      form.submit();
    }
  });
})();
