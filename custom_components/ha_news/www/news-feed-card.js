// news-feed-card: a feed reader - every headline from the News feeds in
// one list, newest first, each row with picture, title, source and age,
// and a two-line summary; chips filter by source. Loaded by the News
// integration (ha_news), no resource to register.
//
//   type: custom:news-feed-card
//   feeds: [sensor.rte, sensor.bbc_world]   # optional: these, in this order
//
// Without `feeds` it shows every News feed, so a feed added in Settings
// appears on its own. Each feed sensor has `items` (title, link,
// published, summary, image) and `prefix` (an emoji). Feed text is
// untrusted: inserted as text only, only http(s) links, only https
// pictures (loaded without a referrer).
const newsFeeds = (hass, wanted) => {
  const ids = Array.isArray(wanted) && wanted.length
    ? wanted
    : Object.keys(hass.entities || {})
        .filter((id) => hass.entities[id].platform === "ha_news")
        .sort((a, b) => {
          const n = (id) => (hass.states[id] && hass.states[id].attributes.friendly_name) || id;
          return n(a).localeCompare(n(b));
        });
  return ids.map((id) => hass.states[id]).filter((s) => s);
};

class NewsFeedCard extends HTMLElement {
  static getStubConfig() {
    return {};
  }

  setConfig(config) {
    this._config = config || {};
    this._key = null;
    this._filter = null;
  }

  connectedCallback() {
    // Keep "12 min ago" current without rebuilding the list.
    this._timer = setInterval(() => this._updateAges(), 60000);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
  }

  set hass(hass) {
    this._hass = hass;
    const items = this._items();
    const key = JSON.stringify(items);
    if (key !== this._key) {
      this._key = key;
      this._list = items.items;
      this._sources = items.sources;
      this._render();
    }
  }

  _items() {
    const out = [];
    const seen = new Set();
    const sources = [];
    for (const s of newsFeeds(this._hass, this._config.feeds)) {
      const src = { name: s.attributes.friendly_name || s.entity_id, prefix: s.attributes.prefix || "" };
      sources.push(src);
      for (const it of Array.isArray(s.attributes.items) ? s.attributes.items : []) {
        if (!it || !it.title) continue;
        const link = /^https?:\/\//i.test(it.link || "") ? it.link : "";
        if (link && seen.has(link)) continue;
        seen.add(link);
        const t = Date.parse(it.published || "");
        out.push({
          title: String(it.title),
          link,
          time: isNaN(t) ? 0 : t,
          summary: String(it.summary || "").slice(0, 300),
          image: /^https:\/\//i.test(it.image || "") ? it.image : "",
          source: src.name,
          prefix: src.prefix,
        });
      }
    }
    out.sort((x, y) => y.time - x.time);
    return { sources, items: out };
  }

  static _ago(t) {
    if (!t) return "";
    const m = Math.round((Date.now() - t) / 60000);
    if (m < 1) return "just now";
    if (m < 60) return `${m} min ago`;
    const h = Math.round(m / 60);
    if (h < 24) return `${h} h ago`;
    return new Date(t).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
  }

  _updateAges() {
    if (!this.shadowRoot) return;
    for (const el of this.shadowRoot.querySelectorAll(".ago")) {
      el.textContent = NewsFeedCard._ago(Number(el.dataset.t));
    }
  }

  _el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  _render() {
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    const root = this.shadowRoot;
    root.textContent = "";
    const style = document.createElement("style");
    style.textContent = `
      ha-card { padding: 8px 0; }
      .chips { display: flex; flex-wrap: wrap; gap: 6px; padding: 4px 16px 10px; }
      .chip { font: inherit; font-size: 0.9em; cursor: pointer;
              border: 1px solid var(--divider-color); border-radius: 16px;
              padding: 4px 12px; background: none; color: var(--primary-text-color); }
      .chip[aria-pressed="true"] { background: var(--primary-color);
              border-color: var(--primary-color); color: var(--text-primary-color, #fff); }
      a.row, div.row { display: flex; gap: 12px; padding: 10px 16px;
              color: var(--primary-text-color); text-decoration: none;
              border-top: 1px solid var(--divider-color); }
      a.row:hover { background: var(--secondary-background-color); }
      .img { flex: 0 0 96px; height: 64px; border-radius: 8px; object-fit: cover;
             background: var(--secondary-background-color); }
      .noimg { display: flex; align-items: center; justify-content: center; font-size: 28px; }
      .body { min-width: 0; flex: 1; }
      .title { font-weight: 500; line-height: 1.3;
               display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
      .meta { font-size: 0.85em; color: var(--secondary-text-color); margin: 2px 0; }
      .sum { font-size: 0.9em; color: var(--secondary-text-color); line-height: 1.35;
             display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
      .empty { padding: 16px; color: var(--secondary-text-color); }`;
    const card = this._el("ha-card");
    const chips = this._el("div", "chips");
    const names = [null, ...this._sources.map((s) => s.name)];
    for (const n of names) {
      const src = this._sources.find((s) => s.name === n);
      const b = this._el("button", "chip", n === null ? "All" : `${src.prefix || ""} ${n}`.trim());
      b.type = "button";
      b.setAttribute("aria-pressed", String(this._filter === n));
      b.addEventListener("click", () => {
        this._filter = n;
        this._render();
      });
      chips.append(b);
    }
    card.append(chips);
    const list = this._list.filter((it) => this._filter === null || it.source === this._filter);
    if (!list.length) card.append(this._el("div", "empty", "No headlines yet"));
    for (const it of list) {
      let row;
      if (it.link) {
        row = this._el("a", "row");
        row.href = it.link;
        row.target = "_blank";
        row.rel = "noopener noreferrer";
      } else {
        row = this._el("div", "row");
      }
      if (it.image) {
        const img = this._el("img", "img");
        img.src = it.image;
        img.alt = "";
        img.loading = "lazy";
        img.referrerPolicy = "no-referrer";
        img.addEventListener("error", () => img.replaceWith(this._el("div", "img noimg", it.prefix)));
        row.append(img);
      } else {
        row.append(this._el("div", "img noimg", it.prefix));
      }
      const body = this._el("div", "body");
      body.append(this._el("div", "title", it.title));
      const meta = this._el("div", "meta", `${it.prefix} ${it.source}`.trim());
      if (it.time) {
        meta.append(" · ");
        const ago = this._el("span", "ago", NewsFeedCard._ago(it.time));
        ago.dataset.t = String(it.time);
        meta.append(ago);
      }
      body.append(meta);
      if (it.summary && it.summary !== it.title) body.append(this._el("div", "sum", it.summary));
      row.append(body);
      card.append(row);
    }
    root.append(style, card);
  }

  getCardSize() {
    return 2 + (this._list ? this._list.length * 2 : 0);
  }

  getGridOptions() {
    return { columns: "full" };
  }
}

customElements.define("news-feed-card", NewsFeedCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "news-feed-card",
  name: "News feed",
  description: "Headlines from the News feeds, newest first, with pictures",
});
