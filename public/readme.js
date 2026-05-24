(function () {
  function scope() {
    return window.cl_shadowRootElement || null;
  }

  const HASH = "#readme";
  const MAX_INIT_TRIES = 40;
  const EMPTY_HINT = "Aucun fil de conversation trouvé";
  const LABEL_ADD = "Ajouter aux favoris";
  const LABEL_REMOVE = "Retirer des favoris";

  let readmeTries = 0;

  function q(sel) {
    const root = scope();
    return root ? root.querySelector(sel) : null;
  }

  function initReadme() {
    if (!scope()) {
      if (++readmeTries <= MAX_INIT_TRIES) {
        setTimeout(initReadme, 250);
      }
      return;
    }

    const wireButton = () => {
      const btn = q("#readme-button");
      if (!btn || btn.dataset.readmeWired) return;
      btn.dataset.readmeWired = "1";
      btn.addEventListener("click", () => {
        const base = window.location.pathname + window.location.search;
        if (window.location.hash !== HASH) {
          history.replaceState(null, "", base + HASH);
        }
      });
    };

    const syncHash = () => {
      const btn = q("#readme-button");
      if (!btn) return;
      const base = window.location.pathname + window.location.search;
      if (btn.getAttribute("data-state") === "open" && window.location.hash !== HASH) {
        history.replaceState(null, "", base + HASH);
      } else if (btn.getAttribute("data-state") !== "open" && window.location.hash === HASH) {
        history.replaceState(null, "", base);
      }
    };

    const app = scope();
    if (app && !app.dataset.readmeWatch) {
      app.dataset.readmeWatch = "1";
      new MutationObserver(() => {
        wireButton();
        syncHash();
      }).observe(app, {
        subtree: true,
        attributes: true,
        attributeFilter: ["data-state"],
        childList: true,
      });
    }

    wireButton();
    if (window.location.hash === HASH) {
      setTimeout(() => q("#readme-button")?.click(), 400);
    }
  }

  window.addEventListener("hashchange", () => {
    if (window.location.hash === HASH) q("#readme-button")?.click();
  });

  function currentThreadId() {
    const match = window.location.pathname.match(/\/thread\/([^/?#]+)/);
    return match ? match[1] : null;
  }

  function hasChatContent() {
    const root = scope();
    if (!root) return false;
    return !!(
      root.querySelector(".ai-message") ||
      root.querySelector(".user-message") ||
      root.querySelector('[data-step-type="user_message"]') ||
      root.querySelector('[data-step-type="assistant_message"]')
    );
  }

  function goHome() {
    if (window.location.pathname !== "/") {
      window.location.replace("/");
      return;
    }
    window.location.reload();
  }

  function maybeResetAfterDelete(deletedId) {
    if (deletedId && deletedId === currentThreadId()) {
      goHome();
      return;
    }
    setTimeout(() => {
      const root = scope();
      if (root && root.textContent.includes(EMPTY_HINT) && hasChatContent()) {
        goHome();
      }
    }, 350);
  }

  const origFetch = window.fetch;
  window.fetch = async function (input, init) {
    const url = typeof input === "string" ? input : input?.url || "";
    const method = (init?.method || "GET").toUpperCase();
    const res = await origFetch.call(this, input, init);

    if (method === "DELETE" && url.includes("/project/thread") && res.ok) {
      let deletedId = null;
      try {
        const body = init?.body;
        if (typeof body === "string") {
          deletedId = JSON.parse(body).threadId || null;
        }
      } catch (_) {}
      maybeResetAfterDelete(deletedId);
    }

    return res;
  };

  function wireFavoriteButtons() {
    const root = scope();
    if (!root) return;
    root.querySelectorAll(".favorite-message").forEach((btn) => {
      const label = btn.classList.contains("text-yellow-500") ? LABEL_REMOVE : LABEL_ADD;
      btn.title = label;
      btn.setAttribute("aria-label", label);
    });
  }

  function initFavorites() {
    const root = scope();
    if (!root) {
      setTimeout(initFavorites, 250);
      return;
    }
    wireFavoriteButtons();
    new MutationObserver(wireFavoriteButtons).observe(root, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ["class"],
    });
  }

  function boot() {
    initReadme();
    initFavorites();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
