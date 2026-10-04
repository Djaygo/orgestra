// The three.js world: a plaza where the cast wanders and walks up to each other to talk.
import { DirectionalLight, HemisphereLight, PerspectiveCamera, Scene, Timer, WebGLRenderer } from "three";
import { CSS2DRenderer } from "three/addons/renderers/CSS2DRenderer.js";
import { Character, createSharedParts, disposeSharedParts } from "./character";
import { type CastMember, onStageEvent, SAY, SPOTLIGHT } from "./events";
import { type Bounds, randomPoint } from "./wander";

const MAX_PIXEL_RATIO = 2;
const MAX_STEP_SECONDS = 0.1;
const WANDER_CHANCE_PER_SECOND = 0.35;

export function pixelRatio(deviceRatio: number): number {
  return Math.min(deviceRatio, MAX_PIXEL_RATIO);
}

/** A wide, shallow strip that grows with the cast so a large edition does not turn into a crowd. */
export function plazaFor(castSize: number): Bounds {
  const halfWidth = Math.min(18, 5 + Math.sqrt(castSize) * 1.4);
  return { halfWidth, halfDepth: 2.2 };
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
  const bounds = plazaFor(cast.length);
  // No background and no floor: the canvas is transparent so the characters walk on the page itself.
  const scene = new Scene();
  const camera = new PerspectiveCamera(30, 1, 0.1, 200);

  const renderer = new WebGLRenderer({ antialias: true, alpha: true });
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(pixelRatio(window.devicePixelRatio));
  const labels = new CSS2DRenderer();
  labels.domElement.className = "stage-labels";
  container.append(renderer.domElement, labels.domElement);

  scene.add(new HemisphereLight("#ffffff", "#b8c4d6", 1.7));
  const sun = new DirectionalLight("#ffffff", 1.4);
  sun.position.set(4, 10, 6);
  scene.add(sun);

  const parts = createSharedParts();
  const characters = new Map(
    cast.map((member) => [member.slug, new Character(member, parts, randomPoint(bounds))] as const),
  );
  for (const character of characters.values()) {
    scene.add(character.root);
  }

  const resize = () => {
    const { clientWidth: width, clientHeight: height } = container;
    if (width === 0 || height === 0) {
      return;
    }
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
  };
  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(container);
  resize();

  const stopSay = onStageEvent(events, SAY, ({ speaker, listener, text }) => {
    const now = performance.now();
    const from = characters.get(speaker);
    const to = characters.get(listener);
    from?.say(text, to, now);
    if (from && to) {
      to.listenTo(from, now);
    }
  });
  const stopSpotlight = onStageEvent(events, SPOTLIGHT, ({ speakers }) => {
    const now = performance.now();
    for (const slug of speakers) {
      characters.get(slug)?.spotlight(now);
    }
  });

  const timer = new Timer();
  renderer.setAnimationLoop((time) => {
    timer.update(time);
    const seconds = Math.min(timer.getDelta(), MAX_STEP_SECONDS);
    for (const character of characters.values()) {
      if (character.idle && Math.random() < WANDER_CHANCE_PER_SECOND * seconds) {
        character.wanderTo(randomPoint(bounds));
      }
      character.update(seconds, time);
    }
    renderer.render(scene, camera);
    labels.render(scene, camera);
  });

  return () => {
    renderer.setAnimationLoop(null);
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
