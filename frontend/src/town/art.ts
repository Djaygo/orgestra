// The town's pixel art, drawn in code at 16 px per tile: the hall once into a canvas, and a sprite
// sheet per character. The town scales both up with smoothing off, ai-town style.
import { at, BOOTH_LETTERS, type TownMap } from "./map";

export const TILE = 16;
export const SPRITE_WIDTH = 16;
export const SPRITE_HEIGHT = 20;

export type Facing = "down" | "up" | "left" | "right";
export const FACINGS: Facing[] = ["down", "up", "left", "right"];
/** Standing, then the two steps of the walk. */
export const FRAMES = 3;

type Paint = (x: number, y: number, width: number, height: number, color: string) => void;

const INK = "#2b2233";

function painter(ctx: CanvasRenderingContext2D, originX: number, originY: number): Paint {
  return (x, y, width, height, color) => {
    ctx.fillStyle = color;
    ctx.fillRect(originX + x, originY + y, width, height);
  };
}

/** A colour lighter (amount > 0) or darker (amount < 0) by mixing with white or black. */
export function shade(hex: string, amount: number): string {
  const value = Number.parseInt(hex.slice(1), 16);
  const channels = [(value >> 16) & 255, (value >> 8) & 255, value & 255];
  const target = amount > 0 ? 255 : 0;
  const mixed = channels.map((channel) => Math.round(channel + (target - channel) * Math.abs(amount)));
  return `#${mixed.map((channel) => channel.toString(16).padStart(2, "0")).join("")}`;
}

// ---- Characters -------------------------------------------------------------------------------

export interface Look {
  hair: string;
  skin: string;
  shirt: string;
  pants: string;
}

const SKINS = ["#f6d3b3", "#e8b48f", "#c68863", "#8d5a3b"];
const HAIRS = ["#3b2a20", "#6b4226", "#c9a04a", "#1f1b24", "#a8462c", "#d8d0c4"];

/** A look derived from a hue (a speaker's persona hue), so the same speaker always looks the same. */
export function lookFor(hue: number): Look {
  return {
    hair: HAIRS[hue % HAIRS.length] as string,
    skin: SKINS[Math.floor(hue / 7) % SKINS.length] as string,
    shirt: hslHex(hue, 0.55, 0.52),
    pants: hslHex((hue + 200) % 360, 0.25, 0.3),
  };
}

export function hslHex(hue: number, saturation: number, lightness: number): string {
  const k = (n: number) => (n + hue / 30) % 12;
  const a = saturation * Math.min(lightness, 1 - lightness);
  const f = (n: number) => lightness - a * Math.max(-1, Math.min(k(n) - 3, 9 - k(n), 1));
  return `#${[f(0), f(8), f(4)]
    .map((channel) =>
      Math.round(channel * 255)
        .toString(16)
        .padStart(2, "0"),
    )
    .join("")}`;
}

// Rows of one 16 x 20 frame. o ink, h hair, H hair shade, s skin, S skin shade, e eye, c shirt,
// C shirt shade, p pants, f shoes; the legs (rows 16-19) are added per frame.
const HEAD_FRONT = [
  "................",
  "....oooooooo....",
  "...ohhhhhhhho...",
  "..ohhhhhhhhhho..",
  "..ohhhhhhhhhho..",
  "..ohhhsssshhho..",
  "..ohssssssssho..",
  "..ossessssesso..",
  "..ossessssesso..",
  "..osssssssssso..",
  "...osssSSssso...",
];
const HEAD_BACK = [
  "................",
  "....oooooooo....",
  "...ohhhhhhhho...",
  "..ohhhhhhhhhho..",
  "..ohhhhhhhhhho..",
  "..ohhhhhhhhhho..",
  "..ohhhhhhhhhho..",
  "..ohhhhhhhhhho..",
  "..oHhhhhhhhhHo..",
  "..oHHhhhhhhHHo..",
  "...oHHHHHHHHo...",
];
const HEAD_SIDE = [
  "................",
  "....oooooooo....",
  "...ohhhhhhhho...",
  "..ohhhhhhhhhho..",
  "..ohhhhhhhhhho..",
  "..osssshhhhhho..",
  "..ossssshhhhho..",
  "..oessssshhhho..",
  "..oessssshhhho..",
  "..osssssssshho..",
  "...osssssssso...",
];
const BODY = [
  "...occcccccco...",
  "..occcccccccco..",
  "..ocCccccccCco..",
  "..osCccccccCso..",
  "...oppppppppo...",
];
const BODY_SIDE = [
  "....occcccco....",
  "....occcccco....",
  "....occCCcco....",
  "....occsscco....",
  "....oppppppo....",
];
const LEGS_FRONT = [
  ["...opppoopppo...", "...opppoopppo...", "...offo..offo...", "................"],
  ["...opppoopppo...", "...opppo.offo...", "...offo.........", "................"],
  ["...opppoopppo...", "...offo.opppo...", ".........offo...", "................"],
];
const LEGS_SIDE = [
  ["....oppppppo....", "....opp..ppo....", "....off..ffo....", "................"],
  ["...opppo.oppo...", "..oppo....oppo..", "..offo....offo..", "................"],
  ["....oppppppo....", ".....opppo......", ".....offfo......", "................"],
];

function frameRows(facing: Facing, step: number): string[] {
  if (facing === "left" || facing === "right") {
    return [...HEAD_SIDE, ...BODY_SIDE, ...(LEGS_SIDE[step] as string[])];
  }
  const head = facing === "up" ? HEAD_BACK : HEAD_FRONT;
  return [...head, ...BODY, ...(LEGS_FRONT[step] as string[])];
}

function palette(look: Look): Record<string, string> {
  return {
    o: INK,
    h: look.hair,
    H: shade(look.hair, -0.25),
    s: look.skin,
    S: shade(look.skin, -0.15),
    e: INK,
    c: look.shirt,
    C: shade(look.shirt, -0.2),
    p: look.pants,
    f: "#3a2f2a",
  };
}

/** One canvas with every frame: a row per facing (FACINGS order), a column per frame. */
export function spriteSheet(look: Look, document: Document): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = SPRITE_WIDTH * FRAMES;
  canvas.height = SPRITE_HEIGHT * FACINGS.length;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return canvas;
  }
  const colors = palette(look);
  for (const [row, facing] of FACINGS.entries()) {
    for (let step = 0; step < FRAMES; step++) {
      const paint = painter(ctx, step * SPRITE_WIDTH, row * SPRITE_HEIGHT);
      for (const [y, line] of frameRows(facing, step).entries()) {
        for (const [x, key] of [...line].entries()) {
          const color = colors[key];
          if (!color) {
            continue;
          }
          // Profiles are drawn facing left; facing right is the mirror image.
          paint(facing === "right" ? SPRITE_WIDTH - 1 - x : x, y, 1, 1, color);
        }
      }
    }
  }
  return canvas;
}

// ---- The hall ---------------------------------------------------------------------------------

const FLOOR = "#e3dccb";
const FLOOR_LINE = "#d2c9b3";
const WOOD = "#b98552";
const WOOD_LINE = "#9f6d3f";
const WALL_TOP = "#4a4058";
const WALL_FACE = "#8d82a3";
const WALL_FACE_DARK = "#73688a";
const BRASS = "#d9a93c";
const ROPE = "#b3263b";
const CARPET = "#9e2f3f";

function floor(paint: Paint, x: number, y: number): void {
  paint(0, 0, TILE, TILE, FLOOR);
  paint(0, 0, TILE, 1, FLOOR_LINE);
  paint(0, 0, 1, TILE, FLOOR_LINE);
  if ((x + y) % 2 === 0) {
    paint(5, 6, 2, 1, FLOOR_LINE);
  }
}

function carpet(paint: Paint, map: TownMap, x: number, y: number): void {
  const isCarpet = (char: string) => char === "=" || char === "S";
  paint(0, 0, TILE, TILE, CARPET);
  if ((x + y) % 2 === 0) {
    paint(7, 7, 2, 2, shade(CARPET, 0.15));
  }
  if (!isCarpet(at(map, x - 1, y))) {
    paint(0, 0, 2, TILE, BRASS);
  }
  if (!isCarpet(at(map, x + 1, y))) {
    paint(TILE - 2, 0, 2, TILE, BRASS);
  }
  if (!isCarpet(at(map, x, y - 1)) && at(map, x, y - 1) !== "R") {
    paint(0, 0, TILE, 2, BRASS);
  }
  if (!isCarpet(at(map, x, y + 1)) && at(map, x, y + 1) !== "E") {
    paint(0, TILE - 2, TILE, 2, BRASS);
  }
}

function wood(paint: Paint, x: number, y: number): void {
  paint(0, 0, TILE, TILE, WOOD);
  for (const row of [3, 7, 11, 15]) {
    paint(0, row, TILE, 1, WOOD_LINE);
  }
  const seam = (x * 5 + y * 3) % TILE;
  paint(seam, 0, 1, 4, WOOD_LINE);
  paint((seam + 8) % TILE, 8, 1, 4, WOOD_LINE);
}

function wall(paint: Paint, map: TownMap, x: number, y: number): void {
  paint(0, 0, TILE, TILE, WALL_TOP);
  const below = at(map, x, y + 1);
  if (below !== "#" && below !== "T") {
    // The face of the wall, seen from the south.
    paint(0, 6, TILE, 10, WALL_FACE);
    paint(0, 6, TILE, 1, shade(WALL_FACE, 0.25));
    paint(0, 14, TILE, 2, WALL_FACE_DARK);
  }
}

function screen(paint: Paint, map: TownMap, x: number, y: number): void {
  const left = at(map, x - 1, y) !== "T";
  const right = at(map, x + 1, y) !== "T";
  const top = at(map, x, y - 1) !== "T";
  const bottom = at(map, x, y + 1) !== "T";
  paint(0, 0, TILE, TILE, WALL_TOP);
  paint(0, top ? 1 : 0, TILE, TILE - (top ? 1 : 0) - (bottom ? 1 : 0), "#1c1a24");
  const inset = { left: left ? 2 : 0, right: right ? 2 : 0, top: top ? 3 : 0, bottom: bottom ? 3 : 0 };
  paint(inset.left, inset.top, TILE - inset.left - inset.right, TILE - inset.top - inset.bottom, "#2f5f93");
  if (top) {
    paint(inset.left, inset.top, TILE - inset.left - inset.right, 1, "#4a80bb");
  }
}

function chair(paint: Paint, x: number, y: number): void {
  wood(paint, x, y);
  paint(3, 3, 10, 4, "#7a2433");
  paint(3, 7, 10, 6, "#b23a48");
  paint(3, 12, 10, 1, "#7a2433");
}

function plant(paint: Paint): void {
  paint(0, 0, TILE, TILE, FLOOR);
  paint(4, 10, 8, 5, "#a0522d");
  paint(4, 10, 8, 1, "#c46a3c");
  paint(3, 3, 10, 7, "#3f8f4a");
  paint(5, 1, 6, 4, "#5fb35f");
  paint(2, 6, 3, 3, "#5fb35f");
  paint(11, 5, 3, 3, "#2f7038");
}

function rope(paint: Paint, map: TownMap, x: number, y: number): void {
  wood(paint, x, y);
  const left = at(map, x - 1, y) !== "R";
  const right = at(map, x + 1, y) !== "R";
  paint(0, 7, TILE, 2, ROPE);
  paint(0, 9, TILE, 1, shade(ROPE, -0.3));
  for (const post of [left ? 1 : -1, right ? TILE - 4 : -1]) {
    if (post >= 0) {
      paint(post, 3, 3, 11, BRASS);
      paint(post, 3, 3, 1, shade(BRASS, 0.4));
      paint(post - 1, 13, 5, 2, shade(BRASS, -0.3));
    }
  }
}

function door(paint: Paint, map: TownMap, x: number, y: number): void {
  paint(0, 0, TILE, TILE, WALL_TOP);
  paint(0, 0, TILE, 16, "#6d6578");
  const left = at(map, x - 1, y) !== "E";
  paint(left ? 2 : 0, 2, TILE - 2, 14, "#9ccbe8");
  paint(left ? 2 : 0, 2, TILE - 2, 2, "#d7eefa");
  paint(left ? TILE - 3 : 1, 8, 2, 2, BRASS);
}

function booth(paint: Paint, map: TownMap, x: number, y: number, color: string): void {
  const letter = at(map, x, y).toUpperCase();
  const top = at(map, x, y - 1).toUpperCase() !== letter;
  const bottom = at(map, x, y + 1).toUpperCase() !== letter;
  const left = at(map, x - 1, y).toUpperCase() !== letter;
  const right = at(map, x + 1, y).toUpperCase() !== letter;
  if (top) {
    // The backdrop with the sponsor's banner.
    paint(0, 0, TILE, TILE, shade(color, -0.35));
    paint(0, 3, TILE, 10, color);
    paint(0, 3, TILE, 1, shade(color, 0.35));
    paint(0, 12, TILE, 1, shade(color, -0.2));
    if (left || right) {
      paint(left ? 0 : TILE - 2, 0, 2, TILE, shade(color, -0.55));
    }
    return;
  }
  if (bottom) {
    // The counter: a white top over a front panel in the sponsor's colour.
    paint(0, 0, TILE, 5, "#f4f1ea");
    paint(0, 4, TILE, 1, "#cfc8b8");
    paint(0, 5, TILE, 11, color);
    paint(0, 5, TILE, 1, shade(color, 0.3));
    paint(0, 14, TILE, 2, shade(color, -0.35));
    if ((x + y) % 3 === 0) {
      // A small pile of seed packets on the counter.
      paint(5, 0, 4, 3, shade(color, 0.5));
      paint(6, 1, 2, 1, color);
    }
    return;
  }
  paint(0, 0, TILE, TILE, shade(color, 0.72));
  paint(0, 0, TILE, 1, shade(color, 0.6));
  if (left || right) {
    paint(left ? 0 : TILE - 2, 0, 2, TILE, shade(color, -0.55));
  }
}

/** The whole hall at one pixel per art pixel; booth colours in BOOTH_LETTERS order. */
export function drawHall(map: TownMap, boothColors: string[], document: Document): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = map.width * TILE;
  canvas.height = map.height * TILE;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return canvas;
  }
  for (let y = 0; y < map.height; y++) {
    for (let x = 0; x < map.width; x++) {
      const paint = painter(ctx, x * TILE, y * TILE);
      const char = at(map, x, y);
      const boothIndex = BOOTH_LETTERS.indexOf(char.toUpperCase());
      if (boothIndex >= 0) {
        booth(paint, map, x, y, boothColors[boothIndex] ?? "#888888");
      } else if (char === "#") {
        wall(paint, map, x, y);
      } else if (char === "=" || char === "S") {
        carpet(paint, map, x, y);
      } else if (char === ",") {
        wood(paint, x, y);
      } else if (char === "T") {
        screen(paint, map, x, y);
      } else if (char === "h") {
        chair(paint, x, y);
      } else if (char === "p") {
        plant(paint);
      } else if (char === "R") {
        rope(paint, map, x, y);
      } else if (char === "E") {
        door(paint, map, x, y);
      } else {
        floor(paint, x, y);
      }
    }
  }
  return canvas;
}
