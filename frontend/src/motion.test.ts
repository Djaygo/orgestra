import { describe, expect, it } from "vitest";
import { prefersReducedMotion } from "./motion";

describe("prefersReducedMotion", () => {
  it("asks the reduce query and follows the answer", () => {
    const asked: string[] = [];
    const matcher = (query: string) => {
      asked.push(query);
      return { matches: true };
    };

    expect(prefersReducedMotion(matcher)).toBe(true);
    expect(asked).toEqual(["(prefers-reduced-motion: reduce)"]);
    expect(prefersReducedMotion(() => ({ matches: false }))).toBe(false);
  });

  it("assumes motion is fine when the browser cannot say", () => {
    expect(prefersReducedMotion(undefined)).toBe(false);
  });
});
