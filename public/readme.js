(function () {
  const HASH = "#readme";

  function root() {
    return window.cl_shadowRootElement || document;
  }

  function q(sel) {
    return root().querySelector(sel);
  }

  function openReadme() {
    const btn = q("#readme-button");
    if (btn) btn.click();
  }

  function syncHash(open) {
    const base = window.location.pathname + window.location.search;
    if (open && window.location.hash !== HASH) {
      history.replaceState(null, "", base + HASH);
    } else if (!open && window.location.hash === HASH) {
      history.replaceState(null, "", base);
    }
  }

  function wireButton() {
    const btn = q("#readme-button");
    if (!btn || btn.dataset.readmeWired) return;
    btn.dataset.readmeWired = "1";
    btn.addEventListener("click", () => syncHash(true));
  }

  function watchReadme() {
    const app = root();
    if (!app || app.dataset.readmeWatch) return;
    app.dataset.readmeWatch = "1";

    new MutationObserver(() => {
      wireButton();
      const btn = q("#readme-button");
      if (!btn) return;
      syncHash(btn.getAttribute("data-state") === "open");
    }).observe(app, {
      subtree: true,
      attributes: true,
      attributeFilter: ["data-state"],
    });
  }

  function init() {
    wireButton();
    watchReadme();
    if (window.location.hash === HASH) {
      setTimeout(openReadme, 400);
    }
  }

  window.addEventListener("hashchange", () => {
    if (window.location.hash === HASH) openReadme();
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
