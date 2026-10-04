import { describe, expect, it } from "vitest";
import { distance, meetingPoint, stepToward, TALK_DISTANCE, turnToward } from "./wander";

describe("stepToward", () => {
  it("moves at most maxStep", () => {
    expect(stepToward({ x: 0, z: 0 }, { x: 10, z: 0 }, 1)).toEqual({ x: 1, z: 0 });
  });

  it("does not overshoot", () => {
    expect(stepToward({ x: 0, z: 0 }, { x: 0.5, z: 0 }, 1)).toEqual({ x: 0.5, z: 0 });
  });
});

describe("meetingPoint", () => {
  it("stops TALK_DISTANCE away from the partner, on the near side", () => {
    const spot = meetingPoint({ x: 10, z: 0 }, { x: 0, z: 0 });
    expect(spot).toEqual({ x: TALK_DISTANCE, z: 0 });
    expect(distance(spot, { x: 0, z: 0 })).toBeCloseTo(TALK_DISTANCE);
  });

  it("stays put when already close", () => {
    expect(meetingPoint({ x: 1, z: 0 }, { x: 0, z: 0 })).toEqual({ x: 1, z: 0 });
  });
});

describe("turnToward", () => {
  it("turns the short way round across ±π", () => {
    const next = turnToward(Math.PI - 0.1, -Math.PI + 0.1, 0.05);
    expect(next).toBeCloseTo(Math.PI - 0.05);
  });

  it("snaps to the target when within maxTurn", () => {
    expect(turnToward(0, 0.1, 0.5)).toBe(0.1);
  });
});
