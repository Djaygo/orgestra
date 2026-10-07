// Entry of the stage island: small on purpose. three.js loads only once the stage is on screen.
import { bridgeSpotlight, bridgeTranscript, type CastMember } from "./events";

function readCast(stage: Element): CastMember[] {
  const data = stage.querySelector("#cast-data")?.textContent;
  return data ? (JSON.parse(data) as CastMember[]) : [];
}

function whenVisible(element: Element, run: () => void): void {
  const observer = new IntersectionObserver((entries) => {
    if (entries.some((entry) => entry.isIntersecting)) {
      observer.disconnect();
      run();
    }
  });
  observer.observe(element);
}

function start(): void {
  const stage = document.getElementById("stage");
  const world = stage?.querySelector<HTMLElement>("#world");
  const transcript = stage?.querySelector("#transcript");
  if (!stage || !world || !transcript) {
    return;
  }
  bridgeTranscript(transcript, document);
  bridgeSpotlight(document);
  const cast = readCast(stage);
  whenVisible(world, () => {
    import("./world").then(({ mountWorld }) => mountWorld(world, cast, document));
  });
}

start();
