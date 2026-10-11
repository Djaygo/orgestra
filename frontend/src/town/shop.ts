// The shop around the town: the bag in the corner, the buttons of an open booth, and the receipt.
import { type BoothOffer, lines, nudge, saved, shortBy, total } from "./bag";

export interface Shop {
  booths: BoothOffer[];
  budget: number;
  bag: Set<string>;
}

type Child = Node | string;

function element(document: Document, tag: string, className: string, ...children: Child[]): HTMLElement {
  const created = document.createElement(tag);
  created.className = className;
  created.append(...children);
  return created;
}

function button(
  document: Document,
  label: string,
  data: Record<string, string>,
  className = "btn",
): HTMLElement {
  const created = element(document, "button", className, label);
  created.setAttribute("type", "button");
  for (const [key, value] of Object.entries(data)) {
    created.dataset[key] = value;
  }
  return created;
}

const coins = (amount: number) => `${amount} ${amount === 1 ? "coin" : "coins"}`;

/** The bag in the corner: coins left, each stand's seeds and price, a nudge and the checkout. */
export function renderBag(root: HTMLElement, shop: Shop): void {
  const document = root.ownerDocument;
  const spent = total(shop.booths, shop.bag);
  const wallet = element(
    document,
    "p",
    "bag-wallet",
    element(document, "span", "bag-coin"),
    element(document, "strong", "", String(shop.budget - spent)),
    " expo coins left",
  );
  const heading = element(document, "h2", "bag-title", "Your bag");
  const content: Child[] = [heading, wallet];
  const bought = lines(shop.booths, shop.bag);
  if (!bought.length) {
    content.push(element(document, "p", "bag-empty", "Walk up to a booth to shop for tool seeds."));
  }
  const groups = bought.map((line) => {
    const items = line.seeds.map((seed) => {
      const remove = button(document, "×", { removeSeed: seed.slug }, "bag-remove");
      remove.setAttribute("aria-label", `Remove ${seed.name}`);
      return element(document, "li", "bag-item", element(document, "span", "", seed.name), remove);
    });
    const price = line.complete
      ? element(document, "span", "bag-deal", `Stand deal, ${coins(line.cost)}`)
      : element(document, "span", "bag-cost", coins(line.cost));
    const group = element(
      document,
      "li",
      "bag-line",
      element(document, "span", "bag-booth", line.booth.name),
      price,
      element(document, "ul", "bag-items", ...items),
    );
    group.style.setProperty("--booth", line.booth.color);
    return group;
  });
  if (groups.length) {
    content.push(element(document, "ul", "bag-lines", ...groups));
  }
  const saving = saved(shop.booths, shop.bag);
  if (saving) {
    content.push(element(document, "p", "bag-saved", `Stand deals saved you ${coins(saving)}.`));
  }
  const hint = nudge(shop.booths, shop.bag, shop.budget);
  if (hint) {
    content.push(
      element(
        document,
        "p",
        "bag-nudge",
        `Add ${hint.missing.name} to complete ${hint.booth.name} and save ${coins(hint.saving)}. `,
        button(document, "Add it", { addSeed: hint.missing.slug }, "btn btn-text bag-nudge-add"),
      ),
    );
  }
  if (bought.length) {
    content.push(button(document, `Check out, ${coins(spent)}`, { checkout: "" }, "btn bag-checkout"));
  }
  root.replaceChildren(...content);
}

/** The buttons of an open booth, for what is in the bag and what you can still afford. */
export function syncBooth(root: ParentNode, shop: Shop): void {
  for (const control of root.querySelectorAll<HTMLButtonElement>("[data-add-seed]")) {
    const slug = control.dataset.addSeed ?? "";
    const owned = shop.bag.has(slug);
    const short = shortBy(shop.booths, shop.bag, [slug], shop.budget);
    control.disabled = owned || short > 0;
    control.textContent = owned ? "In your bag" : short ? `${coins(short)} short` : "Add to bag";
    control.closest(".seed")?.classList.toggle("seed-owned", owned);
  }
  for (const control of root.querySelectorAll<HTMLButtonElement>("[data-add-stand]")) {
    const booth = shop.booths.find((offer) => offer.slug === control.dataset.addStand);
    const slugs = booth?.seeds.map((seed) => seed.slug) ?? [];
    const complete = slugs.every((slug) => shop.bag.has(slug));
    const short = shortBy(shop.booths, shop.bag, slugs, shop.budget);
    control.disabled = complete || short > 0;
    control.textContent = complete ? "Stand complete" : short ? `${coins(short)} short` : "Take the stand";
  }
}

/** What you bought and what each seed grew into; nothing is sent anywhere. */
export function renderReceipt(root: HTMLElement, shop: Shop): void {
  const document = root.ownerDocument;
  const bought = lines(shop.booths, shop.bag);
  const rows = bought.flatMap((line) =>
    line.seeds.map((seed) =>
      element(
        document,
        "li",
        "receipt-row",
        element(document, "strong", "", seed.name),
        element(document, "span", "receipt-from", ` from ${line.booth.name}, grows into `),
        ...seed.product.flatMap((product, index) => [
          ...(index ? [", "] : []),
          element(document, "code", "", product),
        ]),
      ),
    ),
  );
  const spent = total(shop.booths, shop.bag);
  const saving = saved(shop.booths, shop.bag);
  root.replaceChildren(
    element(
      document,
      "article",
      "receipt",
      element(
        document,
        "header",
        "booth-header",
        element(document, "p", "booth-kicker", "Receipt"),
        element(document, "h2", "", "Thanks for shopping at the expo"),
        element(
          document,
          "p",
          "booth-tagline",
          `${rows.length} ${rows.length === 1 ? "seed" : "seeds"} for ${coins(spent)}${saving ? `, ${coins(saving)} saved with stand deals` : ""}. Plant them in your agent harness and watch them grow.`,
        ),
      ),
      element(document, "ul", "receipt-rows", ...rows),
    ),
  );
}
