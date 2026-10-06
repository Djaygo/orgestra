// The three.js world: a plaza where the cast on duty stands, strolls and walks up to each other to talk.
import { DirectionalLight, HemisphereLight, PerspectiveCamera, Scene, Timer, WebGLRenderer } from "three";
import { CSS2DRenderer } from "three/addons/renderers/CSS2DRenderer.js";
import { Character, createSharedParts, disposeSharedParts } from "./character";
import { type CastMember, onStageEvent, readSpotlight, SAY, SPOTLIGHT } from "./events";
import { prefersReducedMotion } from "./motion";
import {
  ambientSlots,
  capacityFor,
  chooseRoster,
  FRONT_SPACING,
  frontSlots,
  plazaFor,
  type Roster,
  usableShare,
} from "./roster";
import { type Bounds, type Point, randomPointNear } from "./wander";

const MAX_PIXEL_RATIO = 2;
const MAX_STEP_SECONDS = 0.1;
const WANDER_CHANCE_PER_SECOND = 0.35;
// A backlog delivered at once (a tab coming back to the foreground) shows only its first line.
const MIN_SAY_GAP_MS = 250;

export function pixelRatio(deviceRatio: number): number {
  return Math.min(deviceRatio, MAX_PIXEL_RATIO);
}

const CAMERA_ELEVATION = 0.22; // radians above the horizon
const LOOK_HEIGHT = 0.8;

/** How far the camera stands back so the plaza's full width fits a viewport of this aspect. */
export function cameraDistance(bounds: Bounds, verticalFovDeg: number, aspect: number): number {
  const halfVertical = (verticalFovDeg * Math.PI) / 360;
  const halfHorizontal = Math.atan(Math.tan(halfVertical) * aspect);
  return (bounds.halfWidth * 1.05) / Math.tan(halfHorizontal) + bounds.halfDepth;
}

/** Mount the world in `container`; returns the function that tears it down and frees the GPU. */
export function mountWorld(container: HTMLElement, cast: CastMember[], events: EventTarget): () => void {
  let bounds = plazaFor(container.clientWidth / Math.max(container.clientHeight, 1));
  // No background and no floor: the canvas is transparent so the characters walk on the page itself.
  const scene = new Scene();
  const camera = new PerspectiveCamera(30, 1, 0.1, 200);

  const renderer = new WebGLRenderer({ antialias: true, alpha: true });
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(pixelRatio(window.devicePixelRatio));
  const labels = new CSS2DRenderer();
  labels.domElement.className = "stage-labels";
  container.append(renderer.domElement, labels.domElement);
  // The label layer adds each tag to the page only once its character is on stage: let htmx boost it then.
  const boostTags = new MutationObserver((records) => {
    const htmx = (window as { htmx?: { process(element: Element): void } }).htmx;
    for (const added of records.flatMap((record) => [...record.addedNodes])) {
      if (added instanceof Element) {
        htmx?.process(added);
      }
    }
  });
  boostTags.observe(labels.domElement, { childList: true });

  scene.add(new HemisphereLight("#ffffff", "#b8c4d6", 1.7));
  const sun = new DirectionalLight("#ffffff", 1.4);
  sun.position.set(4, 10, 6);
  scene.add(sun);

  const parts = createSharedParts();
  const characters = new Map(
    cast.map((member) => [member.slug, new Character(member, parts, { x: 0, z: 0 })] as const),
  );
  for (const character of characters.values()) {
    // Walk off toward the nearer side, past the edge of what the camera sees.
    character.plaza = () => inner();
    character.exit = (from) => ({ x: Math.sign(from.x || 1) * (bounds.halfWidth + 2), z: from.z });
    scene.add(character.root);
  }
  const slugs = cast.map((member) => member.slug);
  let spotlight = readSpotlight(document);
  let roster: Roster = { front: [], ambient: [] };

  // Under reduced motion the plaza is one still frame: nobody walks, no bubbles, no loop.
  const still = prefersReducedMotion(window.matchMedia?.bind(window));

  let unit = 60;
  /** How much of the width the cast uses, so a speech bubble beside someone at the edge stays on screen. */
  let share = 0.8;
  const inner = (): Bounds => ({ halfWidth: bounds.halfWidth * share, halfDepth: bounds.halfDepth });
  let tagSpacing = FRONT_SPACING;
  /** A front-row plate may be as wide as the gap to its neighbour, so names never overlap. */
  const sizeTags = () =>
    container.style.setProperty("--tag-width", `${(tagSpacing * unit * 0.95).toFixed(0)}px`);

  /** Put the roster on stage: newcomers walk in from the side, the rest settle or walk off. */
  const arrange = (next: Roster, now: number) => {
    roster = next;
    const front = frontSlots(next.front.length, bounds);
    tagSpacing = front.length > 1 ? Math.abs((front[1] as Point).x - (front[0] as Point).x) : FRONT_SPACING;
    sizeTags();
    const ambient = ambientSlots(next.ambient.length, inner());
    const slots = new Map<string, { slot: Point; front: boolean }>();
    for (const [index, slug] of next.front.entries()) {
      slots.set(slug, { slot: front[index] as Point, front: true });
    }
    for (const [index, slug] of next.ambient.entries()) {
      slots.set(slug, { slot: ambient[index] as Point, front: false });
    }
    for (const [slug, character] of characters) {
      const place = slots.get(slug);
      if (place && character.active) {
        character.settle(place.slot, place.front, still);
      } else if (place) {
        const from = character.exit({ x: place.slot.x, z: place.slot.z });
        character.enter(place.slot, from, place.front, now, still);
      } else if (character.active) {
        character.leave(still);
      }
    }
    if (still) {
      renderFrame();
    }
  };
  const chooseFor = (capacity: number) =>
    chooseRoster(slugs, spotlight, [...roster.front, ...roster.ambient], capacity);

  const resize = () => {
    const { clientWidth: width, clientHeight: height } = container;
    if (width === 0 || height === 0) {
      return;
    }
    const resized = plazaFor(width / height);
    const plazaChanged = resized.halfWidth !== bounds.halfWidth;
    bounds = resized;
    camera.aspect = width / height;
    const distance = cameraDistance(bounds, camera.fov, camera.aspect);
    camera.position.set(
      0,
      LOOK_HEIGHT + Math.sin(CAMERA_ELEVATION) * distance,
      Math.cos(CAMERA_ELEVATION) * distance,
    );
    camera.lookAt(0, LOOK_HEIGHT, 0);
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
    labels.setSize(width, height);
    // Pixels per world unit at the plaza's middle: the CSS sizes each link's hit area from it.
    unit = height / (2 * Math.tan((camera.fov * Math.PI) / 360) * distance);
    container.style.setProperty("--unit", `${unit.toFixed(1)}px`);
    share = usableShare(bounds.halfWidth, unit);
    sizeTags();
    if (plazaChanged) {
      arrange(chooseFor(capacityFor(bounds)), performance.now());
    }
  };
  const renderFrame = () => {
    renderer.render(scene, camera);
    labels.render(scene, camera);
  };
  const resizeObserver = new ResizeObserver(() => {
    resize();
    if (still) {
      renderFrame();
    }
  });
  resizeObserver.observe(container);
  resize();

  let lastSayAt = Number.NEGATIVE_INFINITY;
  const stopSay = onStageEvent(events, SAY, ({ speaker, listener, text }) => {
    const now = performance.now();
    if (still || now - lastSayAt < MIN_SAY_GAP_MS) {
      return;
    }
    lastSayAt = now;
    const from = characters.get(speaker);
    const to = characters.get(listener);
    for (const guest of [from, to]) {
      if (guest && !guest.active) {
        guest.enter(guest.exit({ x: 0, z: 0 }), guest.exit({ x: 0, z: 0 }), false, now, true);
        guest.guest = true;
      }
    }
    from?.say(text, to, now);
    if (from && to) {
      to.listenTo(from, now);
    }
  });
  const stopSpotlight = onStageEvent(events, SPOTLIGHT, ({ speakers }) => {
    spotlight = speakers;
    arrange(chooseFor(capacityFor(bounds)), performance.now());
  });

  const timer = new Timer();
  arrange(chooseFor(capacityFor(bounds)), performance.now());
  if (still) {
    renderFrame();
  }
  renderer.setAnimationLoop(
    still
      ? null
      : (time) => {
          timer.update(time);
          const seconds = Math.min(timer.getDelta(), MAX_STEP_SECONDS);
          for (const character of characters.values()) {
            if (character.roaming && Math.random() < WANDER_CHANCE_PER_SECOND * seconds) {
              character.wanderTo(randomPointNear(character.strollPoint, character.strollRadius, inner()));
            }
            character.update(seconds, time);
          }
          renderFrame();
        },
  );

  return () => {
    renderer.setAnimationLoop(null);
    boostTags.disconnect();
    stopSay();
    stopSpotlight();
    resizeObserver.disconnect();
    for (const character of characters.values()) {
      character.dispose();
    }
    disposeSharedParts(parts);
    renderer.dispose();
    renderer.domElement.remove();
    labels.domElement.remove();
  };
}
