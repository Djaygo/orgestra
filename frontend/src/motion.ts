// Whether the visitor asked the system for less motion; the stage then draws one still frame.

export type MediaQueryMatcher = (query: string) => { matches: boolean };

export function prefersReducedMotion(matchMedia: MediaQueryMatcher | undefined): boolean {
  return matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
}
