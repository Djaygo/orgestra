// The three.js world: a plaza where the cast wanders and walks up to each other to talk.
import {
  CircleGeometry,
  Color,
  DirectionalLight,
  HemisphereLight,
  Mesh,
  MeshStandardMaterial,
  PerspectiveCamera,
  Scene,
  Timer,
  WebGLRenderer,
} from "three";
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

/** A plaza that grows with the cast so a large edition does not turn into a crowd. */
export function plazaFor(castSize: number): Bounds {
  const halfWidth = Math.min(14, 4 + Math.sqrt(castSize) * 1.1);
  return { halfWidth, halfDepth: halfWidth * 0.55 };
}

/** Mount the world in `container`; returns the function that tears it down and frees the GPU. */
export function mountWorld(container: HTMLElement, cast: CastMember[], events: EventTarget): () => void {
  const bounds = plazaFor(cast.length);
  const scene = new Scene();
  scene.background = new Color("#dff0ff");

  const camera = new PerspectiveCamera(42, 1, 0.1, 100);
  camera.position.set(0, bounds.halfWidth * 0.75, bounds.halfWidth * 1.25);
  camera.lookAt(0, 0, bounds.halfDepth * 0.2);

  const renderer = new WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(pixelRatio(window.devicePixelRatio));
  const labels = new CSS2DRenderer();
  labels.domElement.className = "stage-labels";
  container.append(renderer.domElement, labels.domElement);

  scene.add(new HemisphereLight("#ffffff", "#8fbf7f", 1.6));
  const sun = new DirectionalLight("#ffffff", 1.4);
  sun.position.set(4, 10, 6);
  scene.add(sun);

  const groundGeometry = new CircleGeometry(1, 64);
  const groundMaterial = new MeshStandardMaterial({ color: new Color("#bfe3a8"), roughness: 1 });
  const ground = new Mesh(groundGeometry, groundMaterial);
  ground.rotation.x = -Math.PI / 2;
  ground.scale.set(bounds.halfWidth * 1.15, bounds.halfDepth * 1.3, 1);
  scene.add(ground);

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
    groundGeometry.dispose();
    groundMaterial.dispose();
    renderer.dispose();
    renderer.domElement.remove();
    labels.domElement.remove();
  };
}
