import { expect, it } from "vitest";
import { personaHue } from "./persona";

it("matches orgestra.personas.persona_hue (same values in tests/test_personas.py)", () => {
  expect(personaHue("martin-fowler")).toBe(70);
  expect(personaHue("sarah-meiklejohn")).toBe(287);
});
