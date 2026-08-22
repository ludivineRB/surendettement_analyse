(() => {
  const shell = document.querySelector("[data-app-shell]");
  if (!shell) return;

  const toggle = document.querySelector("[data-nav-toggle]");
  const compact = document.querySelector("[data-nav-compact]");
  const close = document.querySelector("[data-nav-close]");

  const setNavOpen = (open) => {
    shell.classList.toggle("is-nav-open", open);
    toggle?.setAttribute("aria-expanded", String(open));
    document.body.style.overflow = open ? "hidden" : "";
  };

  toggle?.addEventListener("click", () => {
    setNavOpen(!shell.classList.contains("is-nav-open"));
  });
  close?.addEventListener("click", () => setNavOpen(false));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setNavOpen(false);
  });

  compact?.addEventListener("click", () => {
    const isCompact = shell.classList.toggle("is-compact");
    compact.setAttribute("aria-pressed", String(isCompact));
    compact.setAttribute(
      "aria-label",
      isCompact ? "Déployer la navigation" : "Réduire la navigation",
    );
    try { localStorage.setItem("navigation-compact", String(isCompact)); } catch (_) {}
  });

  try {
    if (localStorage.getItem("navigation-compact") === "true") {
      shell.classList.add("is-compact");
      compact?.setAttribute("aria-pressed", "true");
    }
  } catch (_) {}
})();
