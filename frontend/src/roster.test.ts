import { describe, expect, it } from "vitest";
import { ambientSlots, capacityFor, chooseRoster, frontSlots, MAX_FRONT, plazaFor } from "./roster";

const cast = Array.from({ length: 65 }, (_, index) => `s${index}`);
const first = () => 0;

describe("plaza size", () => {
  it("shrinks the plaza and the cast on a narrow screen", () => {
    const phone = plazaFor(390 / 150);
    const desktop = plazaFor(1280 / 260);

    expect(phone.halfWidth).toBeLessThan(desktop.halfWidth);
    expect(capacityFor(phone)).toBeLessThan(capacityFor(desktop));
    expect(capacityFor(desktop)).toBeGreaterThanOrEqual(10);
    expect(capacityFor(plazaFor(8))).toBe(12);
    expect(capacityFor(plazaFor(0.5))).toBeGreaterThanOrEqual(5);
  });
});

describe("chooseRoster", () => {
  it("fills the plaza to capacity from a large cast", () => {
    const roster = chooseRoster(cast, [], [], 12);

    expect(roster.front).toEqual([]);
    expect(roster.ambient).toHaveLength(12);
    expect(new Set(roster.ambient).size).toBe(12);
  });

  it("puts spotlit speakers in front, ignoring strangers and duplicates, and keeps the rest of the cast", () => {
    const roster = chooseRoster(cast, ["s5", "nobody", "s5", "s9"], ["s1", "s5", "s2"], 12, first);

    expect(roster.front).toEqual(["s5", "s9"]);
    expect(roster.ambient.slice(0, 2)).toEqual(["s1", "s2"]);
    expect(roster.ambient).toHaveLength(10);
    expect(roster.ambient).not.toContain("s5");
  });

  it("caps the front row and always leaves room for others", () => {
    const many = cast.slice(0, 30);

    expect(chooseRoster(cast, many, [], 12).front).toHaveLength(MAX_FRONT);
    expect(chooseRoster(cast, many, [], 6).front).toHaveLength(4);
  });

  it("copes with a cast smaller than the capacity", () => {
    const roster = chooseRoster(["a", "b", "c"], ["a"], [], 12);

    expect(roster.front).toEqual(["a"]);
    expect(roster.ambient.sort()).toEqual(["b", "c"]);
  });
});

describe("slots", () => {
  const bounds = plazaFor(5);

  it("centres the front row with room between characters", () => {
    const slots = frontSlots(4, bounds);

    expect(slots.reduce((sum, slot) => sum + slot.x, 0)).toBeCloseTo(0);
    for (let index = 1; index < slots.length; index += 1) {
      expect((slots[index]?.x ?? 0) - (slots[index - 1]?.x ?? 0)).toBeGreaterThanOrEqual(1.4);
    }
    expect(Math.min(...slots.map((slot) => slot.z))).toBeGreaterThan(0);
  });

  it("spreads the others over the width, behind the front row, inside the plaza", () => {
    const slots = ambientSlots(12, bounds);

    for (const slot of slots) {
      expect(Math.abs(slot.x)).toBeLessThanOrEqual(bounds.halfWidth * 0.8);
      expect(slot.z).toBeLessThan(0.2 * bounds.halfDepth);
    }
    const xs = slots.map((slot) => slot.x);
    expect(xs).toEqual([...xs].sort((a, b) => a - b));
  });
});
