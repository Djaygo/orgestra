// The small script behind the interface: theme today, then shortcuts, predictions, copy link and list
// filtering. Each behaviour is a pure function over narrow interfaces, so it is tested without a DOM.

export const THEMES = ["system", "light", "dark"] as const;
export type Theme = (typeof THEMES)[number];

const THEME_KEY = "theme";

export interface ThemeStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export interface ThemeRoot {
  setTheme(theme: "light" | "dark"): void;
  clearTheme(): void;
}

export function nextTheme(current: Theme): Theme {
  return THEMES[(THEMES.indexOf(current) + 1) % THEMES.length] ?? "system";
}

/** The stored theme; anything but the two explicit choices (or a blocked storage) means "system". */
export function readTheme(storage: ThemeStorage): Theme {
  try {
    const value = storage.getItem(THEME_KEY);
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}

export function applyTheme(root: ThemeRoot, theme: Theme): void {
  if (theme === "system") {
    root.clearTheme();
  } else {
    root.setTheme(theme);
  }
}

/** Move to the next theme, apply it and remember it (system is remembered as nothing). */
export function toggleTheme(root: ThemeRoot, storage: ThemeStorage, current: Theme): Theme {
  const theme = nextTheme(current);
  applyTheme(root, theme);
  try {
    if (theme === "system") {
      storage.removeItem(THEME_KEY);
    } else {
      storage.setItem(THEME_KEY, theme);
    }
  } catch {
    // The choice still applies to this page; it just is not remembered.
  }
  return theme;
}

const SWITCH_TO: Record<Theme, string> = { system: "light", light: "dark", dark: "follow your system" };
const CURRENT: Record<Theme, string> = { system: "follows your system", light: "light", dark: "dark" };

export function describeTheme(theme: Theme): { label: string; pressed: boolean } {
  return { label: `Theme: ${CURRENT[theme]}. Switch to ${SWITCH_TO[theme]}`, pressed: theme !== "system" };
}

function documentRoot(root: HTMLElement): ThemeRoot {
  return {
    setTheme: (theme) => {
      root.dataset.theme = theme;
    },
    clearTheme: () => {
      delete root.dataset.theme;
    },
  };
}

function syncThemeButtons(theme: Theme): void {
  const { label, pressed } = describeTheme(theme);
  for (const button of document.querySelectorAll<HTMLElement>("[data-theme-toggle]")) {
    button.setAttribute("aria-label", label);
    button.setAttribute("aria-pressed", String(pressed));
    button.title = label;
  }
}

function boot(): void {
  const root = documentRoot(document.documentElement);
  let theme = readTheme(localStorage);
  syncThemeButtons(theme);
  // Delegated, because boosted navigation replaces the app bar and its button.
  document.addEventListener("click", (event) => {
    if ((event.target as Element).closest("[data-theme-toggle]")) {
      theme = toggleTheme(root, localStorage, theme);
      syncThemeButtons(theme);
    }
  });
  document.addEventListener("htmx:load", () => syncThemeButtons(theme));
}

if (typeof document !== "undefined") {
  boot();
}
