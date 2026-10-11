import { describe, expect, it } from "vitest";
import { BOOTH_LETTERS, HALL, parseMap, walkable } from "./map";
import { findPath } from "./path";

const hall = parseMap(HALL);
const open = (x: number, y: number) => walkable(hall, x, y);

describe("the hall", () => {
  it("has a booth per letter, three roped rooms with a screen each, and a start on the floor", () => {
    expect(hall.booths).toHaveLength(BOOTH_LETTERS.length);
    expect(hall.rooms).toHaveLength(3);
    expect(hall.screens).toHaveLength(3);
    expect(hall.screens[0]).toMatchObject({ width: 6, height: 2 });
    expect(open(hall.start.x, hall.start.y)).toBe(true);
    for (const place of [...hall.booths, ...hall.rooms]) {
      expect(open(place.front.x, place.front.y)).toBe(true);
    }
    expect(hall.booths.every((booth) => !open(booth.staff.x, booth.staff.y))).toBe(true);
  });

  it("rejects ragged rows", () => {
    expect(() => parseMap(["###", "##"])).toThrow();
  });
});

describe("findPath", () => {
  it("walks from the entrance to every booth and room front", () => {
    for (const place of [...hall.booths, ...hall.rooms]) {
      const path = findPath(hall.start, place.front, hall.width, hall.height, open);

      expect(path.at(-1)).toEqual(place.front);
      for (const [index, step] of path.entries()) {
        const previous = index ? path[index - 1] : hall.start;
        expect(Math.abs(step.x - (previous?.x ?? 0)) + Math.abs(step.y - (previous?.y ?? 0))).toBe(1);
        expect(open(step.x, step.y)).toBe(true);
      }
    }
  });

  it("never passes a rope: the rooms are closed", () => {
    const seat = { x: 2, y: 3 };

    expect(findPath(hall.start, seat, hall.width, hall.height, open)).toEqual([]);
  });

  it("is empty when the goal is a wall and when you are already there", () => {
    expect(findPath(hall.start, { x: 0, y: 0 }, hall.width, hall.height, open)).toEqual([]);
    expect(findPath(hall.start, hall.start, hall.width, hall.height, open)).toEqual([]);
  });
});
