// The DOM events between the server and the stage. Mirrors src/orgestra/events.py.

export const SAY = "character:say";
export const SPOTLIGHT = "character:spotlight";

/** One speaker of the cast, embedded by the server in <script id="cast-data">. */
export interface CastMember {
  slug: string;
  name: string;
  hue: number;
  /** `<year>/<talk-slug>` of the talk they are talking about. */
  talk: string;
  title: string;
}

export interface SayDetail {
  speaker: string;
  listener: string;
  text: string;
}

/** The speakers a page is about, named by its `data-spotlight` marker; they step to the front. */
export interface SpotlightDetail {
  speakers: string[];
}

interface StageEvents {
  [SAY]: SayDetail;
  [SPOTLIGHT]: SpotlightDetail;
}

/** Listen to a stage event; returns the function that stops listening. */
export function onStageEvent<K extends keyof StageEvents>(
  target: EventTarget,
  name: K,
  handle: (detail: StageEvents[K]) => void,
): () => void {
  const listener = (event: Event) => handle((event as CustomEvent<StageEvents[K]>).detail);
  target.addEventListener(name, listener);
  return () => target.removeEventListener(name, listener);
}

/** The newest transcript line, read from the data-say-* attributes the server renders on it. */
export function sayFromElement(element: Element): SayDetail | undefined {
  const { saySpeaker, sayListener, sayText } = (element as HTMLElement).dataset ?? {};
  if (!saySpeaker || !sayListener || sayText === undefined) {
    return undefined;
  }
  return { speaker: saySpeaker, listener: sayListener, text: sayText };
}

/** Turn each transcript line htmx swaps in (over SSE) into a `character:say` event on `target`. */
export function bridgeTranscript(transcript: Element, target: EventTarget): () => void {
  const listener = (event: Event) => {
    const element = (event as CustomEvent<{ elt: Element }>).detail.elt;
    const detail = transcript.contains(element) ? sayFromElement(element) : undefined;
    if (detail) {
      transcript.scrollTop = transcript.scrollHeight;
      target.dispatchEvent(new CustomEvent(SAY, { detail }));
    }
  };
  document.addEventListener("htmx:load", listener);
  return () => document.removeEventListener("htmx:load", listener);
}

/** The speakers named by the page's `data-spotlight` marker (space separated slugs); none without one. */
export function readSpotlight(root: ParentNode): string[] {
  const marker = root.querySelector<HTMLElement>("[data-spotlight]");
  return marker?.dataset.spotlight?.split(" ").filter(Boolean) ?? [];
}

/** Announce the page's spotlight whenever htmx has settled new content, but only when it changed. */
export function bridgeSpotlight(target: EventTarget): () => void {
  let last = "";
  const announce = () => {
    const speakers = readSpotlight(document);
    const key = speakers.join(" ");
    if (key !== last) {
      last = key;
      target.dispatchEvent(new CustomEvent(SPOTLIGHT, { detail: { speakers } }));
    }
  };
  document.addEventListener("htmx:afterSettle", announce);
  return () => document.removeEventListener("htmx:afterSettle", announce);
}
