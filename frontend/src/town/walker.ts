// Someone who walks the grid tile by tile: you, the townsfolk and the booth staff.
import type { Facing } from "./art";
import type { Tile } from "./map";

const STEPS_PER_SECOND = 6; // walk-cycle frames
export const PLAYER_SPEED = 5; // tiles per second
export const TOWNSFOLK_SPEED = 2.4;

export interface Bubble {
  text: string;
  /** performance.now() when it disappears. */
  until: number;
}

export class Walker {
  x: number;
  y: number;
  /** The tile it stands on, or is walking to. */
  tile: Tile;
  path: Tile[] = [];
  facing: Facing = "down";
  bubble: Bubble | undefined;
  /** Called once each time it arrives at the end of a path. */
  onArrive: (() => void) | undefined;
  /** Called after every tile it steps onto. */
  onStep: ((tile: Tile) => void) | undefined;
  private phase = 0;

  constructor(
    readonly name: string,
    readonly sheet: CanvasImageSource,
    start: Tile,
    readonly speed: number,
  ) {
    this.tile = { ...start };
    this.x = start.x;
    this.y = start.y;
  }

  get moving(): boolean {
    return this.path.length > 0;
  }

  /** Which walk-cycle frame to draw: 0 standing, 1 and 2 the steps. */
  get frame(): number {
    return this.moving ? 1 + (Math.floor(this.phase * STEPS_PER_SECOND) % 2) : 0;
  }

  walk(path: Tile[], onArrive?: () => void): void {
    this.path = path;
    this.onArrive = onArrive;
    if (!path.length) {
      onArrive?.();
    }
  }

  face(target: Tile): void {
    const dx = target.x - this.tile.x;
    const dy = target.y - this.tile.y;
    if (dx === 0 && dy === 0) {
      return;
    }
    this.facing = Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? "right" : "left") : dy > 0 ? "down" : "up";
  }

  say(text: string, now: number, seconds: number): void {
    this.bubble = { text, until: now + seconds * 1000 };
  }

  /** Advance by `seconds`; `instant` jumps straight to the next tile (reduced motion). */
  update(seconds: number, now: number, instant = false): void {
    if (this.bubble && now > this.bubble.until) {
      this.bubble = undefined;
    }
    let budget = instant ? Number.POSITIVE_INFINITY : seconds * this.speed;
    while (this.path.length && budget > 0) {
      const next = this.path[0] as Tile;
      this.face(next);
      this.tile = next;
      const dx = next.x - this.x;
      const dy = next.y - this.y;
      const distance = Math.hypot(dx, dy);
      if (distance > budget) {
        this.x += (dx / distance) * budget;
        this.y += (dy / distance) * budget;
        break;
      }
      budget -= distance;
      this.x = next.x;
      this.y = next.y;
      this.path.shift();
      this.onStep?.(next);
      if (!this.path.length) {
        const arrive = this.onArrive;
        this.onArrive = undefined;
        arrive?.();
      }
      if (instant) {
        break;
      }
    }
    this.phase = this.moving ? this.phase + seconds : 0;
  }
}
