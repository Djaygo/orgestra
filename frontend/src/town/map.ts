// The expo hall as an ASCII grid: presentation rooms along the top, sponsor booths on the floor.

/**
 * `#` wall, `.` hall floor, `=` carpet, `,` room floor, `T` screen, `h` chair, `p` plant, `R` rope across a room's
 * door, `E` the entrance doors, `S` where you start. A booth is a block of one capital letter (`A` the
 * first sponsor, `B` the second, ...): its top row is the backdrop, its bottom row the counter, and the
 * small letter marks where its staff stands.
 */
export const HALL = [
  "########################################",
  "#,,,TTTTTT,,,#,,,TTTTTT,,,#,,,TTTTTT,,,#",
  "#,,,TTTTTT,,,#,,,TTTTTT,,,#,,,TTTTTT,,,#",
  "#,,,,,,,,,,,,#,,,,,,,,,,,,#,,,,,,,,,,,,#",
  "#,hhhh,,hhhh,#,hhhh,,hhhh,#,hhhh,,hhhh,#",
  "#,,,,,,,,,,,,#,,,,,,,,,,,,#,,,,,,,,,,,,#",
  "#,hhhh,,hhhh,#,hhhh,,hhhh,#,hhhh,,hhhh,#",
  "######RR###########RR###########RR######",
  "#p....==...........==...........==....p#",
  "#.....============================.....#",
  "#..................==..................#",
  "#...AAAAAAAA.......==......BBBBBBBB....#",
  "#...AAAaAAAA.......==......BBBbBBBB....#",
  "#...AAAAAAAA.......==......BBBBBBBB....#",
  "#..................==..................#",
  "#.............p....==....p.............#",
  "#..................==..................#",
  "#..................==..................#",
  "#...CCCCCCCC.......==......DDDDDDDD....#",
  "#...CCCcCCCC.......==......DDDdDDDD....#",
  "#...CCCCCCCC.......==......DDDDDDDD....#",
  "#..................==..................#",
  "#..................==..................#",
  "#..................==..................#",
  "#p.................==.................p#",
  "#..................S=..................#",
  "#..................==..................#",
  "###################EE###################",
];

export interface Tile {
  x: number;
  y: number;
}

export interface Block {
  /** Top left and size in tiles. */
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface BoothPlace extends Block {
  staff: Tile;
  /** The floor tile in front of the middle of the counter, where a visitor is served. */
  front: Tile;
}

export interface RoomPlace {
  /** The rope tiles across the door. */
  rope: Block;
  /** The floor tile just outside the rope. */
  front: Tile;
}

export interface TownMap {
  width: number;
  height: number;
  rows: string[];
  start: Tile;
  booths: BoothPlace[];
  rooms: RoomPlace[];
  /** The screens inside the rooms, left to right. */
  screens: Block[];
  exit: Block;
}

const WALKABLE = new Set([".", "=", ",", "S"]);
/** One letter per sponsor, in the order of the expo data; staff stand on the small letter. */
export const BOOTH_LETTERS = "ABCD";

export function at(map: TownMap, x: number, y: number): string {
  return map.rows[y]?.[x] ?? "#";
}

export function walkable(map: TownMap, x: number, y: number): boolean {
  return WALKABLE.has(at(map, x, y));
}

function find(rows: string[], char: string): Tile[] {
  return rows.flatMap((row, y) => [...row].flatMap((c, x) => (c === char ? [{ x, y }] : [])));
}

export function parseMap(rows: string[]): TownMap {
  const width = rows[0]?.length ?? 0;
  if (rows.some((row) => row.length !== width)) {
    throw new Error("every row of the map must be as wide as the first");
  }
  const booths = [...BOOTH_LETTERS].flatMap((letter) => {
    const tiles = [...find(rows, letter), ...find(rows, letter.toLowerCase())];
    if (!tiles.length) {
      return [];
    }
    const x = Math.min(...tiles.map((tile) => tile.x));
    const y = Math.min(...tiles.map((tile) => tile.y));
    const width = Math.max(...tiles.map((tile) => tile.x)) - x + 1;
    const height = Math.max(...tiles.map((tile) => tile.y)) - y + 1;
    const staff = find(rows, letter.toLowerCase())[0] ?? { x, y: y + 1 };
    return [{ x, y, width, height, staff, front: { x: x + Math.floor(width / 2), y: y + height } }];
  });
  return {
    width,
    height: rows.length,
    rows,
    start: find(rows, "S")[0] ?? { x: 1, y: 1 },
    booths,
    rooms: runs(find(rows, "R")).map((rope) => ({ rope, front: { x: rope.x, y: rope.y + 1 } })),
    screens: stacked(runs(find(rows, "T"))),
    exit: runs(find(rows, "E"))[0] ?? { x: 0, y: 0, width: 0, height: 0 },
  };
}

/** Runs of the same span on consecutive rows, merged into one block. */
function stacked(blocks: Block[]): Block[] {
  const found: Block[] = [];
  for (const block of blocks) {
    const above = found.find(
      (other) => other.x === block.x && other.width === block.width && other.y + other.height === block.y,
    );
    if (above) {
      above.height += 1;
    } else {
      found.push({ ...block });
    }
  }
  return found;
}

/** Horizontal runs of adjacent tiles, top to bottom and left to right. */
function runs(tiles: Tile[]): Block[] {
  const found: Block[] = [];
  for (const tile of [...tiles].sort((a, b) => a.y - b.y || a.x - b.x)) {
    const last = found.at(-1);
    if (last && last.y === tile.y && last.x + last.width === tile.x) {
      last.width += 1;
    } else {
      found.push({ x: tile.x, y: tile.y, width: 1, height: 1 });
    }
  }
  return found;
}
