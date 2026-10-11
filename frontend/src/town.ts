// Entry of the town page (/town): the pixel world, the booth panel and the bag around it.
import { bridgeTranscript, type CastMember } from "./events";
import { adding, type BagStorage, readBag, writeBag } from "./town/bag";
import { renderBag, renderReceipt, type Shop, syncBooth } from "./town/shop";
import { mountTown, type TownData, type Visit } from "./town/world";

interface Htmx {
  ajax(verb: string, path: string, context: { target: Element; swap: string }): Promise<void>;
}

function readJson<T>(id: string, fallback: T): T {
  const text = document.getElementById(id)?.textContent;
  return text ? (JSON.parse(text) as T) : fallback;
}

function parseVisit(value: string | undefined): Visit | undefined {
  const [kind, id] = (value ?? "").split(":");
  if (kind === "booth" && id) {
    return { kind, slug: id };
  }
  if (kind === "room" && id) {
    return { kind, number: Number(id) };
  }
  return undefined;
}

/** Reading `window.localStorage` itself throws when site data is blocked; the bag then lives for the page. */
function localStorage(): BagStorage | undefined {
  try {
    return window.localStorage;
  } catch {
    return undefined;
  }
}

function start(): void {
  const town = document.getElementById("town");
  const world = document.getElementById("town-world");
  const panel = document.getElementById("town-panel");
  const panelBody = document.getElementById("town-panel-body");
  const bagRoot = document.getElementById("town-bag");
  const transcript = document.getElementById("town-transcript");
  if (!town || !world || !panel || !panelBody || !bagRoot || !transcript) {
    return;
  }
  const data = readJson<TownData>("town-data", { budget: 0, booths: [], rooms: [] });
  const cast = readJson<CastMember[]>("cast-data", []);
  const storage = localStorage();
  const shop: Shop = { booths: data.booths, budget: data.budget, bag: readBag(storage, data.booths) };

  const refresh = () => {
    writeBag(storage, shop.bag);
    renderBag(bagRoot, shop);
    syncBooth(panelBody, shop);
  };
  // The panel covers the right of the world on a wide screen; the camera keeps you in view beside it.
  const coverage = () =>
    panel.hidden || panel.offsetLeft < town.clientWidth / 3 ? 0 : town.clientWidth - panel.offsetLeft;
  const showPanel = () => {
    panel.hidden = false;
    town.classList.add("town-panel-open");
    mounted.coverRight(coverage());
  };
  const hidePanel = () => {
    panel.hidden = true;
    town.classList.remove("town-panel-open");
    mounted.coverRight(0);
  };
  const openPanel = (path: string) => {
    const htmx = (window as { htmx?: Htmx }).htmx;
    htmx?.ajax("GET", path, { target: panelBody, swap: "innerHTML" }).then(() => {
      syncBooth(panelBody, shop);
      showPanel();
      panel.scrollTop = 0;
    });
  };

  const mounted = mountTown(world, data, cast, document, (place) =>
    openPanel(place.kind === "booth" ? `/town/booths/${place.slug}` : `/town/rooms/${place.number}`),
  );
  bridgeTranscript(transcript, document);

  const take = (slugs: string[]) => {
    const next = adding(shop.booths, shop.bag, slugs, shop.budget);
    if (!next) {
      return;
    }
    shop.bag = next;
    refresh();
    const booth = shop.booths.find((offer) => offer.seeds.some((seed) => seed.slug === slugs[0]));
    if (booth) {
      const complete = booth.seeds.every((seed) => shop.bag.has(seed.slug));
      mounted.staffSay(
        booth.slug,
        complete ? "The whole stand! Enjoy the deal." : "Great pick, it grows fast!",
      );
    }
  };

  town.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const control = target?.closest<HTMLElement>(
      "[data-visit], [data-add-seed], [data-add-stand], [data-remove-seed], [data-checkout], [data-close-panel]",
    );
    if (!control) {
      return;
    }
    const { visit, addSeed, addStand, removeSeed } = control.dataset;
    if (visit !== undefined) {
      const place = parseVisit(visit);
      if (place) {
        event.preventDefault();
        control.closest("details")?.removeAttribute("open");
        mounted.visit(place);
      }
    } else if (addSeed) {
      take([addSeed]);
    } else if (addStand) {
      take(shop.booths.find((booth) => booth.slug === addStand)?.seeds.map((seed) => seed.slug) ?? []);
    } else if (removeSeed) {
      shop.bag.delete(removeSeed);
      refresh();
    } else if ("checkout" in control.dataset) {
      renderReceipt(panelBody, shop);
      showPanel();
      panel.scrollTop = 0;
    } else if ("closePanel" in control.dataset) {
      hidePanel();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !panel.hidden) {
      hidePanel();
    }
  });
  refresh();
}

start();
