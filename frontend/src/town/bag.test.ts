import { describe, expect, it } from "vitest";
import { adding, type BoothOffer, lines, nudge, readBag, saved, shortBy, total, writeBag } from "./bag";

const seed = (slug: string, price: number) => ({
  slug,
  name: slug.toUpperCase(),
  price,
  hook: "",
  product: [],
});
const booths: BoothOffer[] = [
  { slug: "pals", name: "Pals", color: "#000000", bundle: 32, seeds: [seed("ci", 24), seed("stack", 16)] },
  {
    slug: "polish",
    name: "Polish",
    color: "#000000",
    bundle: 28,
    seeds: [seed("score", 28), seed("git", 8)],
  },
];

describe("the bag", () => {
  it("prices a complete stand at its bundle and the rest seed by seed", () => {
    const bag = new Set(["ci", "stack", "git"]);

    expect(lines(booths, bag).map((line) => [line.booth.slug, line.cost, line.complete])).toEqual([
      ["pals", 32, true],
      ["polish", 8, false],
    ]);
    expect(total(booths, bag)).toBe(40);
    expect(saved(booths, bag)).toBe(8);
  });

  it("nudges toward the stand one seed short, only when you can afford it", () => {
    expect(nudge(booths, new Set(["git"]), 100)).toMatchObject({ missing: { slug: "score" }, saving: 8 });
    expect(nudge(booths, new Set(["git"]), 20)).toBeUndefined();
    expect(nudge(booths, new Set(), 100)).toBeUndefined();
  });

  it("refuses what you cannot pay for, counting the stand deal", () => {
    expect(adding(booths, new Set(["ci"]), ["score"], 50)).toBeUndefined();
    expect(adding(booths, new Set(["ci"]), ["stack"], 32)).toEqual(new Set(["ci", "stack"]));
    expect(shortBy(booths, new Set(["ci"]), ["score"], 50)).toBe(2);
  });

  it("keeps only seeds still on sale and survives broken or blocked storage", () => {
    const stored = new Map([["town-bag", JSON.stringify(["ci", "gone"])]]);
    const storage = { getItem: (key: string) => stored.get(key) ?? null, setItem: () => {} };

    expect(readBag(storage, booths)).toEqual(new Set(["ci"]));
    expect(readBag({ getItem: () => "{oops", setItem: () => {} }, booths)).toEqual(new Set());
    expect(readBag(undefined, booths)).toEqual(new Set());
    const blocked = {
      getItem: () => null,
      setItem: () => {
        throw new Error("blocked");
      },
    };
    expect(() => writeBag(blocked, new Set(["ci"]))).not.toThrow();
  });
});
