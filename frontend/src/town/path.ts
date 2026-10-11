// Walking on the grid: the shortest path between two tiles, four directions, breadth first.
import type { Tile } from "./map";

const STEPS: Tile[] = [
  { x: 0, y: -1 },
  { x: 1, y: 0 },
  { x: 0, y: 1 },
  { x: -1, y: 0 },
];

/** The tiles from `from` (excluded) to `to` (included); empty when `to` cannot be reached. */
export function findPath(
  from: Tile,
  to: Tile,
  width: number,
  height: number,
  open: (x: number, y: number) => boolean,
): Tile[] {
  const key = (tile: Tile) => tile.y * width + tile.x;
  if (!open(to.x, to.y)) {
    return [];
  }
  const cameFrom = new Map<number, Tile | null>([[key(from), null]]);
  const queue: Tile[] = [from];
  for (let head = 0; head < queue.length; head++) {
    const tile = queue[head] as Tile;
    if (tile.x === to.x && tile.y === to.y) {
      const path: Tile[] = [];
      for (
        let step: Tile | null | undefined = tile;
        step && key(step) !== key(from);
        step = cameFrom.get(key(step))
      ) {
        path.unshift(step);
      }
      return path;
    }
    for (const step of STEPS) {
      const next = { x: tile.x + step.x, y: tile.y + step.y };
      const inside = next.x >= 0 && next.y >= 0 && next.x < width && next.y < height;
      if (inside && !cameFrom.has(key(next)) && open(next.x, next.y)) {
        cameFrom.set(key(next), tile);
        queue.push(next);
      }
    }
  }
  return [];
}
