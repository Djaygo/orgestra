// Who is on stage and where they stand. Pure functions on plain points, tested without WebGL.
import type { Bounds, Point } from "./wander";

/** Speakers of the current page that stand in the front row, each with their name and talk. */
export const MAX_FRONT = 6;
const MIN_CAPACITY = 5;
const MAX_CAPACITY = 12;
/** World units between neighbours in the front row, at most. */
export const FRONT_SPACING = 2.6;
const FRONT_DEPTH = 0.7;
const BUBBLE_HALF_WIDTH_PX = 96;
const MAX_HALF_WIDTH = 11;
const MIN_HALF_WIDTH = 3.5;
const HALF_WIDTH_PER_ASPECT = 1.9;
const CHARACTERS_PER_HALF_WIDTH = 1.15;

export interface Roster {
  front: string[];
  ambient: string[];
}

/** The plaza is as wide as the viewport lets characters stay large enough to read. */
export function plazaFor(aspect: number): Bounds {
  const halfWidth = Math.min(MAX_HALF_WIDTH, Math.max(MIN_HALF_WIDTH, aspect * HALF_WIDTH_PER_ASPECT));
  return { halfWidth, halfDepth: 2.2 };
}

export function capacityFor(bounds: Bounds): number {
  const fit = Math.round(bounds.halfWidth * CHARACTERS_PER_HALF_WIDTH);
  return Math.min(MAX_CAPACITY, Math.max(MIN_CAPACITY, fit));
}

/**
 * The cast on duty: the spotlit speakers first (they know the page), then those already on stage so
 * nobody walks off for nothing, then random others until the plaza is full.
 */
export function chooseRoster(
  cast: string[],
  spotlight: string[],
  current: string[],
  capacity: number,
  random: () => number = Math.random,
): Roster {
  const known = new Set(cast);
  const front = [...new Set(spotlight)]
    .filter((slug) => known.has(slug))
    .slice(0, Math.min(MAX_FRONT, capacity - 2));
  const taken = new Set(front);
  const ambient = current
    .filter((slug) => known.has(slug) && !taken.has(slug))
    .slice(0, capacity - front.length);
  for (const slug of ambient) {
    taken.add(slug);
  }
  const others = cast.filter((slug) => !taken.has(slug));
  while (ambient.length < capacity - front.length && others.length > 0) {
    ambient.push(others.splice(Math.floor(random() * others.length), 1)[0] as string);
  }
  return { front, ambient };
}

/** The share of the plaza's half width the cast may use: a bubble is `unit` pixels per world unit wide. */
export function usableShare(halfWidth: number, unit: number): number {
  return Math.min(0.85, Math.max(0.4, 1 - BUBBLE_HALF_WIDTH_PX / unit / halfWidth));
}

/** The front row: centred, evenly spaced, nearest to the camera. */
export function frontSlots(count: number, bounds: Bounds): Point[] {
  const step = Math.min(FRONT_SPACING, (bounds.halfWidth * 1.6) / Math.max(count, 1));
  return Array.from({ length: count }, (_, index) => ({
    x: (index - (count - 1) / 2) * step,
    z: bounds.halfDepth * FRONT_DEPTH,
  }));
}

/** Everyone else: spread across the width with a little jitter, behind the front row. */
export function ambientSlots(count: number, bounds: Bounds, random: () => number = Math.random): Point[] {
  const { halfWidth } = bounds;
  const step = (halfWidth * 2) / Math.max(count, 1);
  return Array.from({ length: count }, (_, index) => ({
    x: -halfWidth + (index + 0.5) * step + (random() - 0.5) * step * 0.5,
    z: -bounds.halfDepth + random() * bounds.halfDepth * 1.1,
  }));
}
