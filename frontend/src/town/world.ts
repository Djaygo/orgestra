// The town: draws the hall and everyone in it, moves you by keys or clicks, and runs the townsfolk.
import { type CastMember, onStageEvent, SAY } from "../events";
import { prefersReducedMotion } from "../motion";
import { drawHall, FACINGS, hslHex, lookFor, SPRITE_HEIGHT, SPRITE_WIDTH, spriteSheet, TILE } from "./art";
import type { BoothOffer } from "./bag";
import { at, HALL, parseMap, type Tile, walkable } from "./map";
import { findPath } from "./path";
import { PLAYER_SPEED, TOWNSFOLK_SPEED, Walker } from "./walker";

export interface TownData {
  budget: number;
  booths: BoothOffer[];
  rooms: { name: string; showing: string }[];
}

/** A place you can visit: a booth by its sponsor's slug, or a room by its number (1-based). */
export type Visit = { kind: "booth"; slug: string } | { kind: "room"; number: number };

export interface Town {
  /** Walk you to a booth or room; `onVisit` fires when you get there. */
  visit(place: Visit): void;
  /** The staff of a booth says something. */
  staffSay(slug: string, text: string): void;
  /** Screen pixels covered on the right (the open panel): the camera centres you in the rest. */
  coverRight(pixels: number): void;
  destroy(): void;
}

const MAX_TOWNSFOLK = 10;
const MAX_GUESTS = 4; // extra speakers who walk in for a conversation
const WANDER_CHANCE_PER_SECOND = 0.25;
const WANDER_RADIUS = 7;
const HOOK_DISTANCE = 5; // tiles from a booth's staff at which they call out to you
const HOOK_COOLDOWN_MS = 14_000;
const BUBBLE_SECONDS = 3.4;
const MAX_BUBBLE_CHARS = 120;
const MAX_STEP_SECONDS = 0.1;
const MIN_SCALE = 2;
const MAX_SCALE = 4;
const PLAYER_LOOK = { hair: "#1f1b24", skin: "#e8b48f", shirt: "#fbbc05", pants: "#2f3a56" };
const KEYS: Record<string, Tile> = {
  ArrowUp: { x: 0, y: -1 },
  ArrowDown: { x: 0, y: 1 },
  ArrowLeft: { x: -1, y: 0 },
  ArrowRight: { x: 1, y: 0 },
  w: { x: 0, y: -1 },
  s: { x: 0, y: 1 },
  a: { x: -1, y: 0 },
  d: { x: 1, y: 0 },
};

/** How many screen pixels per art pixel: as large as fits 15 tiles high and 20 wide, at least 2. */
export function scaleFor(width: number, height: number): number {
  const fit = Math.floor(Math.min(height / (TILE * 15), width / (TILE * 20)));
  return Math.max(MIN_SCALE, Math.min(MAX_SCALE, fit));
}

/** The left (or top) edge of the view, in screen pixels: centred on `focus`, kept inside the map. */
export function cameraEdge(focus: number, view: number, world: number): number {
  if (world <= view) {
    return -(view - world) / 2;
  }
  return Math.min(Math.max(focus - view / 2, 0), world - view);
}

/** Long abstracts are cut in the bubble; the transcript keeps the whole line. */
function clip(text: string): string {
  return text.length > MAX_BUBBLE_CHARS ? `${text.slice(0, MAX_BUBBLE_CHARS).trimEnd()}…` : text;
}

function same(first: Tile, second: Tile): boolean {
  return first.x === second.x && first.y === second.y;
}

export function mountTown(
  container: HTMLElement,
  data: TownData,
  cast: CastMember[],
  events: EventTarget,
  onVisit: (place: Visit) => void,
): Town {
  const document = container.ownerDocument;
  const map = parseMap(HALL);
  const hall = drawHall(
    map,
    data.booths.map((booth) => booth.color),
    document,
  );
  const still = prefersReducedMotion(window.matchMedia?.bind(window));

  const canvas = document.createElement("canvas");
  canvas.className = "town-canvas";
  const overlay = document.createElement("div");
  overlay.className = "town-overlay";
  const layer = document.createElement("div");
  layer.className = "town-layer";
  overlay.append(layer);
  container.append(canvas, overlay);
  const ctx = canvas.getContext("2d") as CanvasRenderingContext2D;

  // ---- People ----
  const player = new Walker("You", spriteSheet(PLAYER_LOOK, document), map.start, PLAYER_SPEED);
  player.facing = "up";
  const staff = map.booths.slice(0, data.booths.length).map((place, index) => {
    const booth = data.booths[index] as BoothOffer;
    const look = { ...lookFor(index * 97 + 31), shirt: booth.color };
    const walker = new Walker(booth.name, spriteSheet(look, document), place.staff, 0);
    return { walker, booth, place, lastHook: Number.NEGATIVE_INFINITY, nextHook: 0 };
  });
  const hallTiles: Tile[] = [];
  for (let y = 0; y < map.height; y++) {
    for (let x = 0; x < map.width; x++) {
      if (at(map, x, y) === ".") {
        hallTiles.push({ x, y });
      }
    }
  }
  const randomHallTile = (near?: Tile): Tile => {
    const options = near
      ? hallTiles.filter((tile) => Math.abs(tile.x - near.x) + Math.abs(tile.y - near.y) <= WANDER_RADIUS)
      : hallTiles;
    return options[Math.floor(Math.random() * options.length)] ?? map.start;
  };
  const doorstep: Tile = { x: map.exit.x, y: map.exit.y - 1 };
  const people = new Map<string, Walker>();
  const guests: string[] = [];
  const bySlug = new Map(cast.map((member) => [member.slug, member]));
  const resident = (member: CastMember, start: Tile) => {
    const walker = new Walker(
      member.name.split(" ")[0] ?? member.name,
      spriteSheet(lookFor(member.hue), document),
      start,
      TOWNSFOLK_SPEED,
    );
    walker.facing = FACINGS[Math.floor(Math.random() * FACINGS.length)] ?? "down";
    people.set(member.slug, walker);
    return walker;
  };
  for (const member of [...cast].sort(() => Math.random() - 0.5).slice(0, MAX_TOWNSFOLK)) {
    resident(member, randomHallTile());
  }
  /** Until when someone is busy talking and does not wander off. */
  const busyUntil = new Map<Walker, number>();

  const open = (x: number, y: number) => walkable(map, x, y);
  const pathTo = (walker: Walker, to: Tile) => findPath(walker.tile, to, map.width, map.height, open);

  // ---- You ----
  let zone: string | undefined;
  const zoneKey = (place: Visit) => (place.kind === "booth" ? `booth:${place.slug}` : `room:${place.number}`);
  const placeAt = (tile: Tile): Visit | undefined => {
    for (const { booth, place } of staff) {
      if (tile.y === place.y + place.height && tile.x >= place.x && tile.x < place.x + place.width) {
        return { kind: "booth", slug: booth.slug };
      }
    }
    for (const [index, room] of map.rooms.slice(0, data.rooms.length).entries()) {
      const { rope } = room;
      if (tile.y === rope.y + 1 && tile.x >= rope.x && tile.x < rope.x + rope.width) {
        return { kind: "room", number: index + 1 };
      }
    }
    return undefined;
  };
  const arriveAt = (place: Visit | undefined, force = false) => {
    const key = place && zoneKey(place);
    if (place && (force || key !== zone)) {
      player.facing = "up";
      onVisit(place);
    }
    zone = key;
  };
  // Only where you stop counts: walking past a booth on the way somewhere else opens nothing. A visit
  // opens its own place when it arrives (`visit`).
  player.onStep = (tile) => {
    container.dataset.walked = `${tile.x},${tile.y}`;
    if (!player.moving && !player.onArrive) {
      arriveAt(placeAt(tile));
    }
  };

  const frontOf = (place: Visit): Tile | undefined => {
    if (place.kind === "booth") {
      return staff.find((entry) => entry.booth.slug === place.slug)?.place.front;
    }
    return map.rooms[place.number - 1]?.front;
  };
  const visit = (place: Visit) => {
    const front = frontOf(place);
    if (!front) {
      return;
    }
    if (same(player.tile, front) && !player.moving) {
      arriveAt(place, true);
      return;
    }
    player.walk(pathTo(player, front), () => arriveAt(place, true));
  };

  const held: Tile[] = [];
  const stepHeld = () => {
    const direction = held.at(-1);
    if (!direction || player.moving) {
      return;
    }
    const next = { x: player.tile.x + direction.x, y: player.tile.y + direction.y };
    if (open(next.x, next.y)) {
      player.walk([next]);
      return;
    }
    player.face(next);
    // Walking into a rope: the room tells you why it is closed.
    if (at(map, next.x, next.y) === "R") {
      arriveAt(placeAt(player.tile), true);
    }
  };
  const typing = (target: EventTarget | null) =>
    target instanceof HTMLElement &&
    (target.isContentEditable ||
      /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName) ||
      !!target.closest("#town-panel"));
  const onKeyDown = (event: KeyboardEvent) => {
    const direction = KEYS[event.key.length === 1 ? event.key.toLowerCase() : event.key];
    if (!direction || typing(event.target) || event.metaKey || event.ctrlKey || event.altKey) {
      return;
    }
    event.preventDefault();
    if (!held.includes(direction)) {
      held.push(direction);
    }
    stepHeld();
  };
  const onKeyUp = (event: KeyboardEvent) => {
    const direction = KEYS[event.key.length === 1 ? event.key.toLowerCase() : event.key];
    const index = direction ? held.indexOf(direction) : -1;
    if (index >= 0) {
      held.splice(index, 1);
    }
  };
  const onBlur = () => {
    held.length = 0;
  };
  window.addEventListener("keydown", onKeyDown);
  window.addEventListener("keyup", onKeyUp);
  window.addEventListener("blur", onBlur);

  // ---- Camera and size ----
  let scale = MIN_SCALE;
  let view = { width: 0, height: 0 };
  let camera = { x: 0, y: 0 };
  let covered = 0;
  const resize = () => {
    view = { width: container.clientWidth, height: container.clientHeight };
    scale = scaleFor(view.width, view.height);
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(view.width * ratio);
    canvas.height = Math.round(view.height * ratio);
    canvas.style.width = `${view.width}px`;
    canvas.style.height = `${view.height}px`;
    container.style.setProperty("--town-scale", String(scale));
    placeSigns();
  };
  const tileAtPoint = (clientX: number, clientY: number): Tile => {
    const box = canvas.getBoundingClientRect();
    return {
      x: Math.floor((clientX - box.left + camera.x) / (TILE * scale)),
      y: Math.floor((clientY - box.top + camera.y) / (TILE * scale)),
    };
  };

  // ---- Signs over the booths and rooms, and bubbles over heads (DOM, so text stays crisp) ----
  const signs: { element: HTMLElement; tile: Tile; width: number; height: number }[] = [];
  const addSign = (label: string, place: Visit, tile: Tile, width: number, className: string, height = 1) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `town-sign ${className}`;
    button.textContent = label;
    button.tabIndex = -1; // the directory next to the town is the keyboard's way in
    button.addEventListener("click", () => visit(place));
    layer.append(button);
    signs.push({ element: button, tile, width, height });
    return button;
  };
  for (const { booth, place } of staff) {
    const sign = addSign(
      booth.name,
      { kind: "booth", slug: booth.slug },
      { x: place.x, y: place.y },
      place.width,
      "town-sign-booth",
    );
    sign.style.setProperty("--booth", booth.color);
  }
  for (const [index, room] of data.rooms.entries()) {
    const door = map.rooms[index];
    if (door) {
      const { rope } = door;
      addSign(
        `${room.name} · doors closed`,
        { kind: "room", number: index + 1 },
        { x: rope.x - 3, y: rope.y },
        rope.width + 6,
        "town-sign-room",
      );
    }
    const screen = map.screens[index];
    if (screen && room.showing) {
      const place: Visit = { kind: "room", number: index + 1 };
      const sign = addSign(room.showing, place, screen, screen.width, "town-sign-screen", screen.height);
      sign.prepend(Object.assign(document.createElement("small"), { textContent: "Next up" }));
    }
  }
  const exit = document.createElement("a");
  exit.href = "/";
  exit.className = "town-sign town-sign-exit";
  exit.textContent = "Exit to search";
  exit.tabIndex = -1;
  layer.append(exit);
  signs.push({
    element: exit,
    tile: { x: map.exit.x - 2, y: map.exit.y },
    width: map.exit.width + 4,
    height: 1,
  });
  function placeSigns() {
    const unit = TILE * scale;
    for (const sign of signs) {
      sign.element.style.left = `${sign.tile.x * unit}px`;
      sign.element.style.top = `${sign.tile.y * unit}px`;
      sign.element.style.width = `${sign.width * unit}px`;
      sign.element.style.height = `${sign.height * unit}px`;
    }
  }

  const bubbles = new Map<Walker, HTMLElement>();
  const nameTag = document.createElement("div");
  nameTag.className = "town-name";
  nameTag.hidden = true;
  layer.append(nameTag);
  const everyone = () => [player, ...staff.map((entry) => entry.walker), ...people.values()];
  const drawBubbles = (now: number) => {
    const unit = TILE * scale;
    for (const walker of everyone()) {
      let element = bubbles.get(walker);
      if (!walker.bubble) {
        element?.remove();
        bubbles.delete(walker);
        continue;
      }
      if (!element) {
        element = document.createElement("div");
        element.className = "town-bubble";
        layer.append(element);
        bubbles.set(walker, element);
      }
      const text = `${walker.name}: ${walker.bubble.text}`;
      if (element.textContent !== text) {
        element.replaceChildren();
        const who = document.createElement("b");
        who.textContent = walker.name;
        element.append(who, ` ${clip(walker.bubble.text)}`);
        element.dataset.text = text;
      }
      // Keep the bubble on screen: its centre stays half a bubble away from the view's edges.
      const visible = view.width - covered;
      const half = Math.min(element.offsetWidth / 2 || 110, visible / 2);
      const centre = (walker.x + 0.5) * unit;
      const left = Math.min(Math.max(centre, camera.x + half + 4), camera.x + visible - half - 4);
      element.style.left = `${left}px`;
      element.style.top = `${(walker.y - 0.35) * unit}px`;
      element.classList.toggle("town-bubble-fading", walker.bubble.until - now < 400);
    }
  };

  // ---- Clicks and hover ----
  const onClick = (event: MouseEvent) => {
    const tile = tileAtPoint(event.clientX, event.clientY);
    const char = at(map, tile.x, tile.y);
    const booth = staff.find(
      ({ place }) =>
        tile.x >= place.x &&
        tile.x < place.x + place.width &&
        tile.y >= place.y &&
        tile.y < place.y + place.height,
    );
    if (booth) {
      visit({ kind: "booth", slug: booth.booth.slug });
      return;
    }
    const room = map.rooms.findIndex(
      ({ rope }) =>
        tile.y <= rope.y && tile.x >= rope.x - 6 && tile.x < rope.x + rope.width + 6 && char !== "#",
    );
    if (room >= 0 && room < data.rooms.length) {
      visit({ kind: "room", number: room + 1 });
      return;
    }
    if (open(tile.x, tile.y)) {
      player.walk(pathTo(player, tile));
    }
  };
  const onMove = (event: MouseEvent) => {
    const tile = tileAtPoint(event.clientX, event.clientY);
    const person = [...people.values()].find(
      (walker) =>
        Math.round(walker.x) === tile.x &&
        (Math.round(walker.y) === tile.y || Math.round(walker.y) - 1 === tile.y),
    );
    nameTag.hidden = !person;
    if (person) {
      const member = [...people.entries()].find(([, walker]) => walker === person)?.[0];
      nameTag.textContent = member
        ? `${bySlug.get(member)?.name} · ${bySlug.get(member)?.title}`
        : person.name;
      nameTag.style.left = `${(person.x + 0.5) * TILE * scale}px`;
      nameTag.style.top = `${(person.y + 1) * TILE * scale}px`;
    }
    const char = at(map, tile.x, tile.y);
    canvas.style.cursor = open(tile.x, tile.y) || /[A-Dda-dR,hT]/.test(char) ? "pointer" : "default";
  };
  canvas.addEventListener("click", onClick);
  canvas.addEventListener("mousemove", onMove);

  // ---- Conversations from the server ----
  const stopSay = onStageEvent(events, SAY, ({ speaker, listener, text }) => {
    if (still) {
      return;
    }
    const now = performance.now();
    const arrive = (slug: string) => {
      const existing = people.get(slug);
      const member = bySlug.get(slug);
      if (existing || !member) {
        return existing;
      }
      // Someone off the floor walks in through the doors for the conversation.
      const walker = resident(member, doorstep);
      guests.push(slug);
      if (guests.length > MAX_GUESTS) {
        const leaving = guests.shift() as string;
        const gone = people.get(leaving);
        gone?.walk(pathTo(gone, doorstep), () => people.delete(leaving));
      }
      return walker;
    };
    const from = arrive(speaker);
    const to = arrive(listener);
    if (!from) {
      return;
    }
    from.say(text, now, BUBBLE_SECONDS);
    busyUntil.set(from, now + 9000);
    if (!to) {
      return;
    }
    busyUntil.set(to, now + 9000);
    to.walk([]);
    to.face(from.tile);
    const beside = [
      { x: to.tile.x - 1, y: to.tile.y },
      { x: to.tile.x + 1, y: to.tile.y },
      { x: to.tile.x, y: to.tile.y + 1 },
      { x: to.tile.x, y: to.tile.y - 1 },
    ].find((tile) => open(tile.x, tile.y));
    if (beside && !same(from.tile, beside)) {
      from.walk(pathTo(from, beside), () => {
        from.face(to.tile);
        to.face(from.tile);
      });
    } else {
      from.face(to.tile);
    }
  });

  // ---- The loop ----
  let last = performance.now();
  let frame = 0;
  const draw = (now: number) => {
    const seconds = Math.min((now - last) / 1000, MAX_STEP_SECONDS);
    last = now;
    stepHeld();
    player.update(seconds, now, still);
    for (const walker of people.values()) {
      const idle = !walker.moving && (busyUntil.get(walker) ?? 0) < now;
      if (!still && idle && Math.random() < WANDER_CHANCE_PER_SECOND * seconds) {
        walker.walk(pathTo(walker, randomHallTile(walker.tile)));
      }
      walker.update(seconds, now);
    }
    for (const entry of staff) {
      const distance = Math.abs(entry.place.front.x - player.x) + Math.abs(entry.place.front.y - player.y);
      const here = zone === `booth:${entry.booth.slug}`;
      if (!still && !here && distance <= HOOK_DISTANCE && now - entry.lastHook > HOOK_COOLDOWN_MS) {
        const seed = entry.booth.seeds[entry.nextHook % entry.booth.seeds.length];
        entry.nextHook += 1;
        entry.lastHook = now;
        if (seed) {
          entry.walker.say(seed.hook, now, BUBBLE_SECONDS + 1);
        }
      }
      entry.walker.update(seconds, now);
    }

    const unit = TILE * scale;
    camera = {
      x: Math.round(cameraEdge((player.x + 0.5) * unit, view.width - covered, map.width * unit)),
      y: Math.round(cameraEdge((player.y + 0.5) * unit, view.height, map.height * unit)),
    };
    layer.style.transform = `translate(${-camera.x}px, ${-camera.y}px)`;
    const ratio = canvas.width / Math.max(view.width, 1);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = "#2b2233";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.imageSmoothingEnabled = false;
    ctx.setTransform(scale * ratio, 0, 0, scale * ratio, -camera.x * ratio, -camera.y * ratio);
    ctx.drawImage(hall, 0, 0);
    // Front to back by feet, so whoever stands lower on the screen is drawn over the one behind.
    for (const walker of everyone().sort((a, b) => a.y - b.y)) {
      const left = Math.round(walker.x * TILE);
      const top = Math.round(walker.y * TILE) + TILE - SPRITE_HEIGHT + 1;
      ctx.fillStyle = "rgba(43, 34, 51, 0.25)";
      ctx.fillRect(left + 3, top + SPRITE_HEIGHT - 3, SPRITE_WIDTH - 6, 2);
      const row = FACINGS.indexOf(walker.facing);
      ctx.drawImage(
        walker.sheet,
        walker.frame * SPRITE_WIDTH,
        row * SPRITE_HEIGHT,
        SPRITE_WIDTH,
        SPRITE_HEIGHT,
        left,
        top,
        SPRITE_WIDTH,
        SPRITE_HEIGHT,
      );
    }
    // A marker over your head, so you find yourself among the townsfolk.
    const bob = still ? 0 : Math.round(Math.sin(now / 220));
    const markerX = Math.round(player.x * TILE) + 5;
    const markerY = Math.round(player.y * TILE) + TILE - SPRITE_HEIGHT - 6 + bob;
    ctx.fillStyle = hslHex(45, 0.95, 0.5);
    ctx.fillRect(markerX, markerY, 6, 2);
    ctx.fillRect(markerX + 1, markerY + 2, 4, 1);
    ctx.fillRect(markerX + 2, markerY + 3, 2, 1);
    drawBubbles(now);
    frame = requestAnimationFrame(draw);
  };

  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(container);
  resize();
  frame = requestAnimationFrame(draw);

  return {
    visit,
    coverRight(pixels) {
      covered = pixels;
    },
    staffSay(slug, text) {
      staff.find((entry) => entry.booth.slug === slug)?.walker.say(text, performance.now(), BUBBLE_SECONDS);
    },
    destroy() {
      cancelAnimationFrame(frame);
      stopSay();
      resizeObserver.disconnect();
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
      window.removeEventListener("blur", onBlur);
      canvas.remove();
      overlay.remove();
    },
  };
}
