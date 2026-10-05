import { describe, expect, it } from "vitest";
import {
  applyTheme,
  copyText,
  counterText,
  describeTheme,
  isTypingTarget,
  lengthOf,
  nextOption,
  nextTheme,
  readTheme,
  type ThemeRoot,
  type ThemeStorage,
  toggleTheme,
  wantsSearchFocus,
} from "./ui";

function memory(initial: Record<string, string> = {}): ThemeStorage & { data: Record<string, string> } {
  const data = { ...initial };
  return {
    data,
    getItem: (key) => data[key] ?? null,
    setItem: (key, value) => {
      data[key] = value;
    },
    removeItem: (key) => {
      delete data[key];
    },
  };
}

function root(): ThemeRoot & { theme: string | undefined } {
  const state: { theme: string | undefined } = { theme: undefined };
  return {
    get theme() {
      return state.theme;
    },
    setTheme: (value) => {
      state.theme = value;
    },
    clearTheme: () => {
      state.theme = undefined;
    },
  };
}

describe("theme", () => {
  it("cycles system, light, dark", () => {
    expect(nextTheme("system")).toBe("light");
    expect(nextTheme("light")).toBe("dark");
    expect(nextTheme("dark")).toBe("system");
  });

  it("reads only the two explicit themes and falls back to system", () => {
    expect(readTheme(memory({ theme: "dark" }))).toBe("dark");
    expect(readTheme(memory({ theme: "light" }))).toBe("light");
    expect(readTheme(memory())).toBe("system");
    expect(readTheme(memory({ theme: "<script>" }))).toBe("system");
    expect(readTheme(memory({ theme: "system" }))).toBe("system");
  });

  it("falls back to system when storage throws", () => {
    const blocked: ThemeStorage = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
      removeItem: () => {
        throw new Error("blocked");
      },
    };
    expect(readTheme(blocked)).toBe("system");
    expect(() => toggleTheme(root(), blocked, "system")).not.toThrow();
  });

  it("sets and clears the root's theme", () => {
    const target = root();
    applyTheme(target, "dark");
    expect(target.theme).toBe("dark");
    applyTheme(target, "system");
    expect(target.theme).toBeUndefined();
  });

  it("toggling applies the next theme and remembers it, forgetting system", () => {
    const target = root();
    const storage = memory();

    expect(toggleTheme(target, storage, "system")).toBe("light");
    expect(storage.data.theme).toBe("light");
    expect(toggleTheme(target, storage, "light")).toBe("dark");
    expect(target.theme).toBe("dark");
    expect(toggleTheme(target, storage, "dark")).toBe("system");
    expect(storage.data.theme).toBeUndefined();
    expect(target.theme).toBeUndefined();
  });

  it("describes the theme for the button", () => {
    expect(describeTheme("system")).toEqual({
      label: "Theme: follows your system. Switch to light",
      pressed: false,
    });
    expect(describeTheme("light")).toEqual({ label: "Theme: light. Switch to dark", pressed: true });
    expect(describeTheme("dark")).toEqual({
      label: "Theme: dark. Switch to follow your system",
      pressed: true,
    });
  });
});

const keys = { ctrlKey: false, metaKey: false, altKey: false, shiftKey: false, target: null };

describe("search shortcuts", () => {
  it("knows which elements take typing", () => {
    expect(isTypingTarget({ tagName: "INPUT" })).toBe(true);
    expect(isTypingTarget({ tagName: "TEXTAREA" })).toBe(true);
    expect(isTypingTarget({ tagName: "SELECT" })).toBe(true);
    expect(isTypingTarget({ tagName: "DIV", isContentEditable: true })).toBe(true);
    expect(isTypingTarget({ tagName: "A" })).toBe(false);
    expect(isTypingTarget(null)).toBe(false);
  });

  it("focuses search on / and on Ctrl or Cmd+K outside inputs", () => {
    expect(wantsSearchFocus({ ...keys, key: "/" })).toBe(true);
    expect(wantsSearchFocus({ ...keys, key: "k", ctrlKey: true })).toBe(true);
    expect(wantsSearchFocus({ ...keys, key: "K", metaKey: true })).toBe(true);
  });

  it("leaves typing and other shortcuts alone", () => {
    expect(wantsSearchFocus({ ...keys, key: "/", target: { tagName: "INPUT" } })).toBe(false);
    expect(wantsSearchFocus({ ...keys, key: "k", ctrlKey: true, target: { tagName: "TEXTAREA" } })).toBe(
      false,
    );
    expect(wantsSearchFocus({ ...keys, key: "/", ctrlKey: true })).toBe(false);
    expect(wantsSearchFocus({ ...keys, key: "k" })).toBe(false);
    expect(wantsSearchFocus({ ...keys, key: "k", ctrlKey: true, altKey: true })).toBe(false);
    expect(wantsSearchFocus({ ...keys, key: "a" })).toBe(false);
  });
});

describe("prediction list navigation", () => {
  it("moves down and wraps to the first option", () => {
    expect(nextOption(-1, 3, "ArrowDown")).toBe(0);
    expect(nextOption(0, 3, "ArrowDown")).toBe(1);
    expect(nextOption(2, 3, "ArrowDown")).toBe(0);
  });

  it("moves up and wraps to the last option", () => {
    expect(nextOption(-1, 3, "ArrowUp")).toBe(2);
    expect(nextOption(0, 3, "ArrowUp")).toBe(2);
    expect(nextOption(2, 3, "ArrowUp")).toBe(1);
  });

  it("has nothing to select without options and ignores other keys", () => {
    expect(nextOption(-1, 0, "ArrowDown")).toBe(-1);
    expect(nextOption(1, 3, "a")).toBe(1);
  });
});

describe("copy link", () => {
  it("writes the text to the clipboard and reports success", async () => {
    const written: string[] = [];
    const clipboard = {
      writeText: async (text: string) => {
        written.push(text);
      },
    };

    expect(await copyText(clipboard, "https://example.test/talk")).toBe(true);
    expect(written).toEqual(["https://example.test/talk"]);
  });

  it("reports failure without a clipboard or when writing is refused", async () => {
    expect(await copyText(undefined, "x")).toBe(false);
    const refusing = {
      writeText: async () => {
        throw new Error("denied");
      },
    };
    expect(await copyText(refusing, "x")).toBe(false);
  });
});

describe("character counter", () => {
  it("shows the length against the limit", () => {
    expect(counterText(0, 120)).toBe("0 / 120");
    expect(counterText(37, 5000)).toBe("37 / 5000");
  });

  it("counts a line break once, as the server does", () => {
    expect(counterText("a\r\nb".length, 10)).toBe("4 / 10");
    expect(counterText(lengthOf("a\r\nb"), 10)).toBe("3 / 10");
  });
});
