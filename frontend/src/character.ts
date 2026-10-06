// A Mii-like character: big round head, capsule body, swinging limbs, a name tag and a speech bubble.
import {
  type BufferGeometry,
  CapsuleGeometry,
  CircleGeometry,
  Color,
  Group,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  SphereGeometry,
} from "three";
import { CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";
import type { CastMember } from "./events";
import { headingTo, meetingPoint, type Point, stepToward, turnToward } from "./wander";

const WALK_SPEED = 0.9;
const APPROACH_SPEED = 1.4;
// Walking on or off the plaza is brisk: nobody should wait for the cast to arrive.
const ENTRANCE_SPEED = 3.2;
const TURN_SPEED = 6;
const SWING = 0.6;
const STRIDE_RATE = 9;
const BUBBLE_MS = 3200;
const ARRIVAL_HOP_MS = 1500;
const ROAM_RADIUS = 0.6;
const BUBBLE_CHARS = 110;

/** Geometries shared by every character, created and disposed once by the world. */
export interface SharedParts {
  head: BufferGeometry;
  hair: BufferGeometry;
  eye: BufferGeometry;
  body: BufferGeometry;
  limb: BufferGeometry;
  shadow: BufferGeometry;
  skin: MeshStandardMaterial;
  dark: MeshStandardMaterial;
  shade: MeshBasicMaterial;
}

export function createSharedParts(): SharedParts {
  return {
    head: new SphereGeometry(0.34, 24, 16),
    hair: new SphereGeometry(0.355, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2.2),
    eye: new SphereGeometry(0.045, 8, 6),
    body: new CapsuleGeometry(0.24, 0.36, 6, 16),
    limb: new CapsuleGeometry(0.07, 0.32, 4, 8),
    // A soft blob under each character grounds it on the transparent page.
    shadow: new CircleGeometry(0.42, 24),
    skin: new MeshStandardMaterial({ color: new Color("#f2c9a0"), roughness: 0.8 }),
    dark: new MeshStandardMaterial({ color: new Color("#2b2522"), roughness: 0.6 }),
    shade: new MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.12, depthWrite: false }),
  };
}

export function disposeSharedParts(parts: SharedParts): void {
  for (const geometry of [parts.head, parts.hair, parts.eye, parts.body, parts.limb, parts.shadow]) {
    geometry.dispose();
  }
  for (const material of [parts.skin, parts.dark, parts.shade]) {
    material.dispose();
  }
}

type Mode = "wander" | "approach" | "talk";

/** A limb hanging from a pivot, so rotating the pivot swings it like a shoulder or hip. */
function limb(parts: SharedParts, material: MeshStandardMaterial, x: number, y: number): Group {
  const pivot = new Group();
  pivot.position.set(x, y, 0);
  const mesh = new Mesh(parts.limb, material);
  mesh.position.y = -0.2;
  pivot.add(mesh);
  return pivot;
}

function label(className: string, text: string): CSS2DObject {
  const element = document.createElement("div");
  element.className = className;
  element.textContent = text;
  return new CSS2DObject(element);
}

/** The speaker's tag is a real link to their talk, so the plaza works with a mouse, a finger and a keyboard. */
function tagFor(member: CastMember): HTMLAnchorElement {
  const tag = document.createElement("a");
  tag.className = "stage-tag";
  tag.href = `/talks/${member.talk}`;
  // The stage lives outside the boosted #app, so it carries the same boost settings (see base.html).
  tag.setAttribute("hx-boost", "true");
  tag.setAttribute("hx-target", "#main");
  tag.setAttribute("hx-select", "#main");
  tag.setAttribute("hx-swap", "outerHTML transition:true");
  tag.setAttribute("aria-label", `${member.name}: ${member.title}`);
  const name = document.createElement("span");
  name.className = "stage-name";
  name.textContent = member.name;
  const talk = document.createElement("span");
  talk.className = "stage-talk";
  talk.textContent = member.title;
  tag.append(name, talk);
  return tag;
}

export class Character {
  readonly root = new Group();
  readonly member: CastMember;
  position: Point;
  private heading = 0;
  private target: Point;
  private mode: Mode = "wander";
  private partner: Character | undefined;
  private talkUntil = 0;
  private line = "";
  private arrivedUntil = 0;
  /** In the front row: holds its spot instead of strolling. */
  private held = false;
  private hovered = false;
  private leaving = false;
  private arriving = false;
  private home: Point;
  /** Where this character walks off the plaza from where it stands; set by the world. */
  exit: (from: Point) => Point = (from) => from;
  /** Came on stage for a conversation and leaves when it is over. */
  guest = false;
  active = false;
  private readonly clothes: MeshStandardMaterial;
  private readonly limbs: { arms: Group[]; legs: Group[] };
  private readonly bubble: CSS2DObject;
  private readonly tag: CSS2DObject;

  constructor(member: CastMember, parts: SharedParts, start: Point) {
    this.member = member;
    this.position = start;
    this.target = start;
    this.home = start;
    this.clothes = new MeshStandardMaterial({ color: new Color().setHSL(member.hue / 360, 0.55, 0.55) });

    const body = new Mesh(parts.body, this.clothes);
    body.position.y = 0.66;
    const head = new Mesh(parts.head, parts.skin);
    head.position.y = 1.28;
    const hair = new Mesh(parts.hair, parts.dark);
    hair.position.y = 1.31;
    hair.rotation.x = -0.25;
    const eyes = [-0.11, 0.11].map((x) => {
      const eye = new Mesh(parts.eye, parts.dark);
      eye.position.set(x, 1.3, 0.31);
      return eye;
    });
    this.limbs = {
      arms: [limb(parts, this.clothes, -0.32, 0.9), limb(parts, this.clothes, 0.32, 0.9)],
      legs: [limb(parts, parts.dark, -0.11, 0.4), limb(parts, parts.dark, 0.11, 0.4)],
    };
    const anchor = tagFor(member);
    anchor.addEventListener("pointerenter", () => this.hover(true));
    anchor.addEventListener("pointerleave", () => this.hover(false));
    anchor.addEventListener("focus", () => this.hover(true));
    anchor.addEventListener("blur", () => this.hover(false));
    this.tag = new CSS2DObject(anchor);
    this.tag.position.y = 1.85;
    this.bubble = label("stage-bubble", "");
    this.bubble.position.y = 2.6;
    this.bubble.center.set(0.5, 1); // anchor the bottom edge, so long lines grow upward
    this.bubble.visible = false;

    const shadow = new Mesh(parts.shadow, parts.shade);
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.y = 0.01;

    this.root.add(
      shadow,
      body,
      head,
      hair,
      ...eyes,
      ...this.limbs.arms,
      ...this.limbs.legs,
      this.tag,
      this.bubble,
    );
    this.setActive(false);
  }

  get slug(): string {
    return this.member.slug;
  }

  get present(): boolean {
    return this.active && !this.leaving;
  }

  /** Free to take a stroll near its spot. */
  get roaming(): boolean {
    return this.present && !this.held && !this.hovered && this.idle;
  }

  get idle(): boolean {
    return this.mode === "wander" && this.target.x === this.position.x && this.target.z === this.position.z;
  }

  get strollPoint(): Point {
    return this.home;
  }

  get strollRadius(): number {
    return ROAM_RADIUS;
  }

  wanderTo(point: Point): void {
    if (this.mode === "wander") {
      this.target = point;
    }
  }

  /** Come on stage and walk to `slot` (or appear there at once). `front` holds the spot and stands out. */
  enter(slot: Point, from: Point, front: boolean, now: number, snap: boolean): void {
    if (!this.active) {
      this.position = snap ? slot : from;
      this.mode = "wander";
      this.partner = undefined;
      this.arrivedUntil = now + ARRIVAL_HOP_MS;
      this.arriving = !snap;
    }
    this.guest = false;
    this.leaving = false;
    this.settle(slot, front, snap);
    this.setActive(true);
  }

  /** Take a (new) spot while staying on stage. */
  settle(slot: Point, front: boolean, snap: boolean): void {
    this.home = slot;
    this.held = front;
    this.target = slot;
    if (snap) {
      this.position = slot;
    }
    this.tag.element.classList.toggle("front", front);
    this.tag.element.tabIndex = front ? 0 : -1;
  }

  /** Walk off the plaza, then disappear. */
  leave(snap: boolean): void {
    this.held = false;
    this.leaving = true;
    this.mode = "wander";
    this.partner = undefined;
    this.bubble.visible = false;
    this.target = this.exit(this.position);
    if (snap) {
      this.finishLeaving();
    }
  }

  private finishLeaving(): void {
    this.leaving = false;
    this.guest = false;
    this.hovered = false;
    this.setActive(false);
  }

  private setActive(active: boolean): void {
    this.active = active;
    this.root.visible = active;
    this.tag.visible = active;
    this.root.position.set(this.position.x, 0, this.position.z);
  }

  private hover(on: boolean): void {
    this.hovered = on;
    if (on && this.mode === "wander") {
      this.target = this.position;
    }
  }

  /** Walk up to `partner` and say `text` once there (or right away if already close). */
  say(text: string, partner: Character | undefined, now: number): void {
    this.partner = partner;
    this.mode = partner ? "approach" : "talk";
    this.line = text;
    this.bubble.visible = false;
    if (!partner) {
      this.startTalking(now);
    }
  }

  /** The bubble appears, and its time starts, when the speaker has walked up to the listener. */
  private startTalking(now: number): void {
    this.mode = "talk";
    this.talkUntil = now + BUBBLE_MS;
    this.showBubble(this.line);
  }

  /** Stop and turn toward the speaker. */
  listenTo(speaker: Character, now: number): void {
    this.partner = speaker;
    this.mode = "talk";
    this.talkUntil = now + BUBBLE_MS;
    this.target = this.position;
  }

  update(seconds: number, now: number): void {
    if (!this.active) {
      return;
    }
    const moving = this.move(seconds, now);
    if (this.mode === "talk" && now > this.talkUntil) {
      this.mode = "wander";
      this.partner = undefined;
      this.bubble.visible = false;
      if (this.guest) {
        this.leave(false);
      } else {
        this.target = this.home;
      }
    }
    if (this.leaving && !moving && this.idle) {
      this.finishLeaving();
      return;
    }
    const element = this.tag.element;
    element.classList.toggle("talking", this.mode !== "wander" && this.bubble.visible);
    this.animate(moving, now);
  }

  dispose(): void {
    this.clothes.dispose();
    this.tag.element.remove();
    this.bubble.element.remove();
    this.root.removeFromParent();
  }

  private move(seconds: number, now: number): boolean {
    if (this.mode === "approach" && this.partner) {
      this.target = meetingPoint(this.position, this.partner.position);
    }
    const hurrying = this.arriving || this.leaving || this.guest;
    const speed =
      this.mode === "approach" && !this.guest ? APPROACH_SPEED : hurrying ? ENTRANCE_SPEED : WALK_SPEED;
    const next =
      this.mode === "talk" ? this.position : stepToward(this.position, this.target, speed * seconds);
    const moving = next.x !== this.position.x || next.z !== this.position.z;
    const lookAt = moving ? next : this.partner?.position;
    if (this.hovered && !moving && !this.partner) {
      this.heading = turnToward(this.heading, 0, TURN_SPEED * seconds); // face the visitor
    } else if (lookAt) {
      this.heading = turnToward(this.heading, headingTo(this.position, lookAt), TURN_SPEED * seconds);
    }
    if (this.mode === "approach" && !moving) {
      this.startTalking(now);
    }
    if (!moving) {
      this.arriving = false;
    }
    this.position = next;
    this.root.position.set(next.x, 0, next.z);
    this.root.rotation.y = this.heading;
    return moving;
  }

  private animate(moving: boolean, now: number): void {
    const phase = (now / 1000) * STRIDE_RATE;
    const swing = moving ? Math.sin(phase) * SWING : 0;
    const [leftArm, rightArm] = this.limbs.arms;
    const [leftLeg, rightLeg] = this.limbs.legs;
    leftArm?.rotation.set(swing, 0, 0);
    const wave = this.hovered && !moving ? -2.6 + Math.sin(phase * 1.6) * 0.35 : 0;
    rightArm?.rotation.set(-swing, 0, wave || (this.mode === "talk" && this.bubble.visible ? -0.6 : 0));
    leftLeg?.rotation.set(-swing, 0, 0);
    rightLeg?.rotation.set(swing, 0, 0);
    const hop = now < this.arrivedUntil && !moving ? Math.abs(Math.sin(phase * 0.6)) * 0.25 : 0;
    this.root.position.y = (moving ? Math.abs(Math.sin(phase)) * 0.05 : 0) + hop;
  }

  private showBubble(text: string): void {
    // The full line is in the transcript; the bubble keeps the plaza readable.
    this.bubble.element.textContent = text.length > BUBBLE_CHARS ? `${text.slice(0, BUBBLE_CHARS)}…` : text;
    this.bubble.visible = true;
  }
}
