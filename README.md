# News (ha_news)

A Home Assistant custom integration for news headlines on the dashboard:
add RSS or Atom feeds from the UI, and show them on two cards, a scrolling
ticker and a feed reader with pictures.

## Feeds

Settings > Devices & services > Add integration > **News**, once per feed:

- **Name** shown on the cards (empty = the feed's own title)
- **Feed address** (RSS or Atom; checked when you add it)
- **Emoji** shown before the source, optional (🇮🇪, 🌍, 💻)
- **Headlines to keep** (default 5, up to 20)

Change a feed with **Configure**, rename it with **Rename**, remove it with
**Delete**. Each feed is one sensor: state = the newest headline,
attributes `items` (title, link, published, summary, image), `link`
and `prefix`. Feeds are fetched every 30 minutes; the headlines are kept
out of the history database.

## Cards

The integration loads both cards on every dashboard; there's no resource
to add. Without `feeds` they show every News feed, so a feed added in
Settings appears on its own.

```yaml
type: custom:news-ticker-card
speed: 60        # pixels per second
per_feed: 3      # newest headlines from each feed, taking turns
```

```yaml
type: custom:news-feed-card   # all headlines newest first, chips per source
```

Both take `feeds: [sensor.a, sensor.b]` to pick feeds and their order.

## Safety

Feed text is untrusted: summaries are reduced to plain text in Home
Assistant, the cards insert text only, follow only http(s) links and load
only https pictures, without a referrer. Standard library only (no extra
Python packages); feeds over 5 MB are refused.

## Install

Copy `custom_components/ha_news` to `/config/custom_components/` and
restart Home Assistant (or add this repository to HACS).
