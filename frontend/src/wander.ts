// Where characters walk. Pure functions on plain points, so they are tested without WebGL.

export interface Point {
  x: number;
  z: number;
}

export interface Bounds {
  halfWidth: number;
  halfDepth: number;
}

/** How close two characters stand while talking. */
export const TALK_DISTANCE = 1.4;

export function distance(a: Point, b: Point): number {
  return Math.hypot(b.x - a.x, b.z - a.z);
}

export function randomPoint(bounds: Bounds, random: () => number = Math.random): Point {
  return {
    x: (random() * 2 - 1) * bounds.halfWidth,
    z: (random() * 2 - 1) * bounds.halfDepth,
  };
}

/** Move from `from` toward `to` by at most `maxStep`, never overshooting. */
export function stepToward(from: Point, to: Point, maxStep: number): Point {
  const gap = distance(from, to);
  if (gap <= maxStep || gap === 0) {
    return { ...to };
  }
  const ratio = maxStep / gap;
  return { x: from.x + (to.x - from.x) * ratio, z: from.z + (to.z - from.z) * ratio };
}

/** The spot next to `partner`, on the side facing `from`, where a speaker stops to talk. */
export function meetingPoint(from: Point, partner: Point): Point {
  const gap = distance(from, partner);
  if (gap <= TALK_DISTANCE) {
    return { ...from };
  }
  const ratio = TALK_DISTANCE / gap;
  return { x: partner.x + (from.x - partner.x) * ratio, z: partner.z + (from.z - partner.z) * ratio };
}

/** Yaw (rotation around y) that makes a character at `from` look at `to`. */
export function headingTo(from: Point, to: Point): number {
  return Math.atan2(to.x - from.x, to.z - from.z);
}

const FULL_TURN = Math.PI * 2;

/** Turn `current` toward `target` by at most `maxTurn` radians, the short way round. */
export function turnToward(current: number, target: number, maxTurn: number): number {
  const delta = ((((target - current + Math.PI) % FULL_TURN) + FULL_TURN) % FULL_TURN) - Math.PI;
  return Math.abs(delta) <= maxTurn ? target : current + Math.sign(delta) * maxTurn;
}
