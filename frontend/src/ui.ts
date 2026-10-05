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

export interface ClipboardLike {
  writeText(text: string): Promise<void>;
}

/** Copy text to the clipboard; false when there is no clipboard (insecure page) or it refuses. */
export async function copyText(clipboard: ClipboardLike | undefined, text: string): Promise<boolean> {
  if (!clipboard) {
    return false;
  }
  try {
    await clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

export interface TypingTarget {
  tagName?: string;
  isContentEditable?: boolean;
}

export interface KeyLike {
  key: string;
  ctrlKey: boolean;
  metaKey: boolean;
  altKey: boolean;
  shiftKey: boolean;
  target: TypingTarget | null;
}

const TYPING_TAGS = new Set(["INPUT", "TEXTAREA", "SELECT"]);

export function isTypingTarget(target: TypingTarget | null): boolean {
  return target !== null && (TYPING_TAGS.has(target.tagName ?? "") || target.isContentEditable === true);
}

/** `/` or Ctrl/Cmd+K focuses the search box, unless the visitor is already typing somewhere. */
export function wantsSearchFocus(event: KeyLike): boolean {
  if (isTypingTarget(event.target) || event.altKey) {
    return false;
  }
  const modifier = event.ctrlKey || event.metaKey;
  if (event.key === "/") {
    return !modifier && !event.shiftKey;
  }
  return event.key.toLowerCase() === "k" && modifier && !event.shiftKey;
}

/** The index selected after a key in a list of `count` options; -1 means none. Arrows wrap around. */
export function nextOption(index: number, count: number, key: string): number {
  if (count === 0) {
    return -1;
  }
  if (key === "ArrowDown") {
    return (index + 1) % count;
  }
  if (key === "ArrowUp") {
    return index <= 0 ? count - 1 : index - 1;
  }
  return index;
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

const SELECTED = '[role="option"][aria-selected="true"]';

function searchInput(): HTMLInputElement | null {
  return document.getElementById("q") as HTMLInputElement | null;
}

function suggestionList(): HTMLElement | null {
  return document.getElementById("suggestions");
}

function closeSuggestions(): void {
  const list = suggestionList();
  const input = searchInput();
  if (list) {
    list.hidden = true;
  }
  input?.setAttribute("aria-expanded", "false");
  input?.removeAttribute("aria-activedescendant");
  for (const option of list?.querySelectorAll(SELECTED) ?? []) {
    option.setAttribute("aria-selected", "false");
  }
}

/** Show the list the server just swapped in, or hide it when it came back empty. */
function syncSuggestions(): void {
  const list = suggestionList();
  const hasOptions = (list?.querySelectorAll('[role="option"]').length ?? 0) > 0;
  if (list && hasOptions && document.activeElement === searchInput()) {
    list.hidden = false;
    searchInput()?.setAttribute("aria-expanded", "true");
  } else {
    closeSuggestions();
  }
}

function moveSelection(key: string): void {
  const input = searchInput();
  const options = [...(suggestionList()?.querySelectorAll<HTMLElement>('[role="option"]') ?? [])];
  const current = options.findIndex((option) => option.getAttribute("aria-selected") === "true");
  const index = nextOption(current, options.length, key);
  for (const [position, option] of options.entries()) {
    option.setAttribute("aria-selected", String(position === index));
  }
  const selected = options[index];
  if (selected && input) {
    input.setAttribute("aria-activedescendant", selected.id);
    selected.scrollIntoView({ block: "nearest" });
  }
}

function onKeydown(event: KeyboardEvent): void {
  if (wantsSearchFocus({ ...event, key: event.key, target: event.target as TypingTarget | null })) {
    event.preventDefault();
    searchInput()?.focus();
    searchInput()?.select();
    return;
  }
  if (event.target !== searchInput() || suggestionList()?.hidden !== false) {
    return;
  }
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    moveSelection(event.key);
  } else if (event.key === "Escape") {
    event.preventDefault();
    closeSuggestions();
  } else if (event.key === "Enter") {
    const link = suggestionList()?.querySelector<HTMLElement>(`${SELECTED} a`);
    if (link) {
      event.preventDefault();
      closeSuggestions();
      link.click();
    }
  }
}

function bootSearch(): void {
  document.addEventListener("keydown", onKeydown);
  document.addEventListener("htmx:afterSwap", (event) => {
    if ((event.target as Element | null)?.id === "suggestions") {
      syncSuggestions();
    }
  });
  document.addEventListener("input", (event) => {
    if (event.target === searchInput() && (searchInput()?.value.trim().length ?? 0) < 2) {
      closeSuggestions();
    }
  });
  document.addEventListener("focusout", () => {
    setTimeout(() => {
      if (!document.getElementById("search-form")?.contains(document.activeElement)) {
        closeSuggestions();
      }
    }, 120);
  });
}

let toastTimer: ReturnType<typeof setTimeout> | undefined;

function showToast(message: string): void {
  const toast = document.getElementById("toast");
  if (!toast) {
    return;
  }
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.hidden = true;
  }, 2400);
}

async function onCopyLink(): Promise<void> {
  const copied = await copyText(navigator.clipboard, window.location.href);
  showToast(copied ? "Link copied" : "Copy the link from the address bar");
}

function setResultsBusy(event: Event, busy: boolean): void {
  const target = (event as CustomEvent<{ target?: Element }>).detail?.target;
  if (target?.id === "results") {
    target.setAttribute("aria-busy", String(busy));
  }
}

function boot(): void {
  bootSearch();
  document.addEventListener("htmx:beforeRequest", (event) => setResultsBusy(event, true));
  document.addEventListener("htmx:afterRequest", (event) => setResultsBusy(event, false));
  const root = documentRoot(document.documentElement);
  let theme = readTheme(localStorage);
  syncThemeButtons(theme);
  // Delegated, because boosted navigation replaces the app bar and its button.
  document.addEventListener("click", (event) => {
    if ((event.target as Element).closest("[data-copy-link]")) {
      void onCopyLink();
    }
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
