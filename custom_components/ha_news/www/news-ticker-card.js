// news-ticker-card: a scrolling headline bar, like a TV news ticker.
// Loaded by the News integration (ha_news), no resource to register.
//
//   type: custom:news-ticker-card
//   speed: 60                     # pixels per second (optional)
//   per_feed: 3                   # newest headlines from each feed (optional)
//   feeds: [sensor.rte]           # optional: these, in this order
//
// Without `feeds` it takes every News feed, taking turns: the newest of
// each, then the second of each, and so on. Headlines come from outside
// feeds: inserted as text only (never HTML), and only http(s) links are
// followed. Pauses on hover; with "reduce motion" on, the headlines wrap
// instead of scrolling.
const newsTickerFeeds = (hass, wanted) => {
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

class NewsTickerCard extends HTMLElement {
  static getStubConfig() {
    return {};
  }

  setConfig(config) {
    this._config = { speed: 60, per_feed: 3, ...(config || {}) };
    this._key = null;
  }

  set hass(hass) {
    this._hass = hass;
    const items = this._items();
    const key = JSON.stringify(items);
    if (key !== this._key) {
      this._key = key;
      this._render(items);
    }
  }

  _items() {
    const lists = newsTickerFeeds(this._hass, this._config.feeds).map((s) =>
      (Array.isArray(s.attributes.items) ? s.attributes.items : [])
        .filter((it) => it && it.title)
        .slice(0, this._config.per_feed)
    );
    const out = [];
    const most = Math.max(0, ...lists.map((l) => l.length));
    for (let i = 0; i < most; i++) {
      for (const l of lists) {
        if (l[i]) out.push({ title: String(l[i].title), link: l[i].link || "", prefix: "" });
      }
    }
    return out;
  }

  _render(items) {
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    const root = this.shadowRoot;
    root.textContent = "";
    const style = document.createElement("style");
    style.textContent = `
      ha-card { overflow: hidden; }
      .bar { overflow: hidden; white-space: nowrap; padding: 10px 0; }
      .track { display: inline-block; padding-left: 100%;
               animation: scroll linear infinite; }
      .bar:hover .track { animation-play-state: paused; }
      @keyframes scroll { from { transform: translateX(0); }
                          to { transform: translateX(-100%); } }
      a, span.t { color: var(--primary-text-color); text-decoration: none; }
      .p { margin-right: 0.4em; font-weight: 600; }
      .sep { margin: 0 1.2em; opacity: 0.4; }
      @media (prefers-reduced-motion: reduce) {
        .bar { white-space: normal; padding: 10px 16px; }
        .track { animation: none; padding-left: 0; }
      }`;
    const card = document.createElement("ha-card");
    const bar = document.createElement("div");
    bar.className = "bar";
    const track = document.createElement("div");
    track.className = "track";
    if (!items.length) {
      const t = document.createElement("span");
      t.className = "t";
      t.textContent = "No headlines yet";
      track.append(t);
    }
    items.forEach((it, i) => {
      if (i) {
        const sep = document.createElement("span");
        sep.className = "sep";
        sep.textContent = "•";
        track.append(sep);
      }
      if (it.prefix) {
        const p = document.createElement("span");
        p.className = "p";
        p.textContent = it.prefix;
        track.append(p);
      }
      let el;
      if (/^https?:\/\//i.test(it.link)) {
        el = document.createElement("a");
        el.href = it.link;
        el.target = "_blank";
        el.rel = "noopener noreferrer";
      } else {
        el = document.createElement("span");
        el.className = "t";
      }
      el.textContent = it.title;
      track.append(el);
    });
    bar.append(track);
    card.append(bar);
    root.append(style, card);
    // Constant speed whatever the length: duration = width / speed.
    requestAnimationFrame(() => {
      const secs = Math.max(10, track.scrollWidth / this._config.speed);
      track.style.animationDuration = `${secs}s`;
    });
  }

  getCardSize() {
    return 1;
  }

  getGridOptions() {
    return { columns: "full", rows: 1, min_rows: 1 };
  }
}

customElements.define("news-ticker-card", NewsTickerCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "news-ticker-card",
  name: "News ticker",
  description: "Scrolling headline bar",
});
