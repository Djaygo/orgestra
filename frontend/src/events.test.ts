import { expect, it } from "vitest";
import { onStageEvent, SAY, sayFromElement } from "./events";

it("reads a transcript line from its data-say-* attributes", () => {
  const line = { dataset: { saySpeaker: "a", sayListener: "b", sayText: "Hi" } } as unknown as Element;
  expect(sayFromElement(line)).toEqual({ speaker: "a", listener: "b", text: "Hi" });
});

it("ignores older lines without data-say-* attributes", () => {
  expect(sayFromElement({ dataset: {} } as unknown as Element)).toBeUndefined();
});

it("unsubscribes", () => {
  const target = new EventTarget();
  const heard: string[] = [];
  const stop = onStageEvent(target, SAY, (detail) => heard.push(detail.text));
  target.dispatchEvent(new CustomEvent(SAY, { detail: { speaker: "a", listener: "b", text: "one" } }));
  stop();
  target.dispatchEvent(new CustomEvent(SAY, { detail: { speaker: "a", listener: "b", text: "two" } }));
  expect(heard).toEqual(["one"]);
});
