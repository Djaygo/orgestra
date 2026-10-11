// The bag: which seeds you took. Everything else (total, coins left, stand deals) is derived from it.

export interface SeedOffer {
  slug: string;
  name: string;
  price: number;
  hook: string;
  /** The skills it grew into. */
  product: string[];
}

export interface BoothOffer {
  slug: string;
  name: string;
  color: string;
  /** What the whole stand costs; src/orgestra/town/expo.py `bundle_price`. */
  bundle: number;
  seeds: SeedOffer[];
}

export interface Line {
  booth: BoothOffer;
  seeds: SeedOffer[];
  /** What these seeds cost: the bundle price when the stand is complete. */
  cost: number;
  complete: boolean;
}

/** What the stand deals in the bag saved, against buying every seed on its own. */
export function saved(booths: BoothOffer[], bag: ReadonlySet<string>): number {
  return lines(booths, bag).reduce((saving, line) => saving + sum(line.seeds) - line.cost, 0);
}

/** How many coins short you are of adding `slugs`; 0 when you can afford them. */
export function shortBy(
  booths: BoothOffer[],
  bag: ReadonlySet<string>,
  slugs: string[],
  budget: number,
): number {
  return Math.max(0, total(booths, new Set([...bag, ...slugs])) - budget);
}

/** One seed short of a complete stand, and what completing it would save. */
export interface Nudge {
  booth: BoothOffer;
  missing: SeedOffer;
  saving: number;
}

const sum = (seeds: SeedOffer[]) => seeds.reduce((total, seed) => total + seed.price, 0);

export function lines(booths: BoothOffer[], bag: ReadonlySet<string>): Line[] {
  return booths.flatMap((booth) => {
    const seeds = booth.seeds.filter((seed) => bag.has(seed.slug));
    if (!seeds.length) {
      return [];
    }
    const complete = seeds.length === booth.seeds.length;
    return [{ booth, seeds, cost: complete ? booth.bundle : sum(seeds), complete }];
  });
}

export function total(booths: BoothOffer[], bag: ReadonlySet<string>): number {
  return lines(booths, bag).reduce((spent, line) => spent + line.cost, 0);
}

/** The cheapest seed that completes a stand you started, when you can afford it. */
export function nudge(booths: BoothOffer[], bag: ReadonlySet<string>, budget: number): Nudge | undefined {
  const spent = total(booths, bag);
  const nudges = lines(booths, bag)
    .filter((line) => line.booth.seeds.length - line.seeds.length === 1)
    .map((line) => {
      const missing = line.booth.seeds.find((seed) => !bag.has(seed.slug)) as SeedOffer;
      const saving = sum(line.booth.seeds) - line.booth.bundle;
      return { booth: line.booth, missing, saving, extra: line.booth.bundle - line.cost };
    })
    .filter((candidate) => spent + candidate.extra <= budget)
    .sort((first, second) => first.extra - second.extra);
  const [best] = nudges;
  return best && { booth: best.booth, missing: best.missing, saving: best.saving };
}

/** The bag with `slugs` added, or undefined when that would cost more than the budget. */
export function adding(
  booths: BoothOffer[],
  bag: ReadonlySet<string>,
  slugs: string[],
  budget: number,
): Set<string> | undefined {
  return shortBy(booths, bag, slugs, budget) ? undefined : new Set([...bag, ...slugs]);
}

export interface BagStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

const BAG_KEY = "town-bag";

/** The stored bag, keeping only seeds the expo still sells. */
export function readBag(storage: BagStorage | undefined, booths: BoothOffer[]): Set<string> {
  const known = new Set(booths.flatMap((booth) => booth.seeds.map((seed) => seed.slug)));
  try {
    const stored: unknown = JSON.parse(storage?.getItem(BAG_KEY) ?? "[]");
    return new Set(Array.isArray(stored) ? stored.filter((slug) => known.has(slug)) : []);
  } catch {
    return new Set();
  }
}

export function writeBag(storage: BagStorage | undefined, bag: ReadonlySet<string>): void {
  try {
    storage?.setItem(BAG_KEY, JSON.stringify([...bag]));
  } catch {
    // Blocked storage: the bag lives for this page only.
  }
}
