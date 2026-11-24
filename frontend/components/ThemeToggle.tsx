"use client";

export function ThemeToggle() {
  function toggle() {
    const root = document.documentElement;
    const current = root.dataset.theme;
    const next = current === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    try {
      window.localStorage.setItem("simuliga-theme", next);
    } catch {
      // Storage can be unavailable in private mode; the theme still applies.
    }
  }

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={toggle}
      aria-label="Cambiar entre tema claro y oscuro"
      title="Cambiar tema"
    >
      <span aria-hidden="true">◐</span>
    </button>
  );
}
