# News (ha_news)

A Home Assistant custom integration for news headlines on the dashboard:
add RSS or Atom feeds or Google News searches from the UI, filter them by
keyword, and show them on two cards, a scrolling ticker and a feed reader
with pictures.

## Feeds

Settings > Devices & services > Add integration > **News**, once per feed.
Choose a **feed address** or a **Google News search**.

### Feed address

- **Name** shown on the cards (empty = the feed's own title)
- **Feed address** (RSS or Atom; checked when you add it)
- **Emoji** shown before the source, optional (🇮🇪, 🌍, 💻)
- **Headlines to keep** (default 5, up to 20)
- **Only headlines with these words**, optional: comma-separated words or
  phrases (`Dublin, Cork, home assistant`); a headline is kept when its
  title or summary has one of them
- **Leave out headlines with these words**, optional (`football, celebrity`)

### Google News search

For news *about* something (a person, a place, a team, a topic) from any
site, without looking for a feed:

- **Search**: e.g. `home assistant`, `ram price`, `gpu stock`.
  `"quotes"` for an exact phrase (`"home assistant"`), `-word` to leave a
  word out (`ram price -phone`), `OR` for either word (`ram OR ssd`),
  `site:` for one site (`site:bbc.com`).
- **Edition**: the country and language of the news (starts on your Home
  Assistant's language and country)
- **Published**: any time, past day or past week
- **Name** (empty = the search), **emoji**, **headlines to keep** and
  **leave out** words, as above

Google News search feeds have no pictures, and their links go through
news.google.com. Google lists a story once per site; repeats are shown
once. Google's RSS search is public and needs no account, but it isn't a
documented API: if Google changes it, these feeds stop updating (feed
addresses aren't affected).

### Keyword filter

Words match whole words (`ai` doesn't match `rain`), ignoring capitals and
accents (`sao paulo` matches São Paulo). The filter runs before the
headline count, so you get up to that many matching headlines. If none
match (or a search has no news yet) the sensor is empty until one does.

### After adding

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
