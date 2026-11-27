# Pushpin

Concerts, films, and art and talks around Boston, Western Mass and New York, gathered from venues' own calendars and grouped by day, at https://pushpin.city/. Concerts and art and talks are listed 90 days ahead, films 30 (`DAYS_AHEAD`, `FILM_DAYS_AHEAD` in `events/build.py`).

Until November 2026 this lived in [grahamhagenah/news](https://github.com/grahamhagenah/news) (tag `before-split`) alongside the newsfeed, now [grahamhagenah/newsfeed](https://github.com/grahamhagenah/newsfeed).

## Running it

Python 3.12+, standard library only. `requirements.txt` (Pillow, rcssmin, rjsmin) is optional: it shrinks pictures and minifies the pages.

```bash
python3 -m events.build                                   # writes the whole site to dist/public
python3 -m http.server 8000 --directory dist/public       # serves it (the `pushpin` entry in .claude/launch.json)
python3 -m unittest                                       # runs the tests
```

## What's where

- `events/build.py`: the readers, the page, and each city (`CITIES`).
- `events/sources*.txt`: each city's venues, one per line (`sources.txt` is Boston's). Its header lists every reader.
- `events/skip.txt`: words that keep a listing off the page ("comedy"). Films are exempt.
- `events/share_cards.py`: the link-preview cards and icons, made by hand: `python3 -m events.share_cards`.
- `shared/`: fetching with retries, the page shell, fallback bookkeeping, and the GitHub issues for failing sources.
- `tests/`: every reader against saved samples of real sites (`tests/fixtures/`).

## How the readers work

Venues rarely publish feeds, so each source is read from the most dependable thing it offers. Each line of a sources file is `reader  url  category  name`, with `category` being `music`, `film` or `art`. Add `public=no` to keep a source off the site.

- **A reader** is a function in `READERS` in `events/build.py`. It takes the source and returns a list of `event(...)`s: title, day, start time, link, and whatever else the site gives (picture, price, ages, sold out, description).
- **Generic readers** cover whole platforms: `jsonld` (schema.org event data, e.g. DICE pages), `ics` calendar feeds, `tribe` (WordPress's The Events Calendar), `squarespace`, `wixevents`, `venuepilot`, `elfsight`, `localist`, `tickettailor`, `seetickets`, `filmbot`, `indy`, `veezi`, `tapos`, `spektrix`, `ticketmaster`, `aeg`, `axs`, `ticketweb`, and `eventbrite` (its API). Look for one of these before writing a new reader.
- **Venue-specific readers** handle sites that are their own thing (`coolidge`, `filmforum`, `metrograph`, `bam`, `wptheatre` for the Somerville Theatre and the Capitol, …).
- **Some readers sort kinds themselves** (the MFA's films, BAM, Mass MoCA). For venues that don't say, `guess_kind` sorts by name and description.
- **After reading**, the build drops what's outside the window or matches `skip.txt`, and folds a film showing at several theaters into one row (`merge_showings`). It also takes price and ages from short fact lines like "$10 · 21+" (`price_from`, `ages_from`) and stamps when each listing was first seen, which drives Just announced.
- **The Somerville Theatre and the Capitol** gave permission to be read (Oct 2026). The build identifies itself to them as `PushpinBot`.

Adding a venue: find a reader that fits (or write one), add its line to the city's sources file, and add its street address to `VENUE_ADDRESSES`. If the reader is new, save a sample page to `tests/fixtures/events/` and add a test.

Adding a city: add a `City` to `CITIES` (via `city_texts`), a `sources-<slug>.txt`, its venues' addresses (and neighborhoods in `VENUE_AREAS`), and its cards in `share_cards.py`. Retired cities go in `RETIRED`.

Some sites turn automated visits away (Film at Lincoln Center, the Museum of the Moving Image, the Clark, Jacob's Pillow, Williams College), so they aren't listed.

## The site

Each city has its own folder on pushpin.city: Boston at the root, `/westernma/`, `/nyc/`. Each has a home page, a page for each kind, tonight's, the weekends', Just announced, About, calendar feeds (`calendar/*.ics`) and a small page per listing (`e/<id>/`) for link previews. The root also has `/cities/`, `/contact/` (sent through FormSubmit to `PUBLIC_CONTACT`) and `/status/`, each source's health.

Visits are counted by [GoatCounter](https://hagenah.goatcounter.com), cookieless (`GOATCOUNTER` in `build.py`). Open https://pushpin.city/#toggle-goatcounter once in a browser to stop counting your own visits.

## When a source fails

- Each build publishes `listings.json`. If a source fails, or suddenly returns nothing, the next build reuses its listings from there for up to two days.
- A source failing for six hours opens a "Source failing" issue, and one listing far fewer than usual opens a "Source shrinking" issue. Both close themselves when the source recovers.
- When you fix a reader for a redesigned site, save a fresh sample in `tests/fixtures/`.

## Publishing

`.github/workflows/deploy.yml` runs the tests, builds, and pushes `dist/public` to `gh-pages`, which GitHub Pages serves at pushpin.city. It rebuilds every three hours (`EVENTS_EVERY_HOURS`) and after each push to `main`.

- **Secrets:** `TICKETMASTER_KEY` (Ticketmaster Discovery API) and `EVENTBRITE_TOKEN`. Without them those sources fall back, then fail.
- **Schedule:** GitHub skips many scheduled runs, so a [cron-job.org](https://cron-job.org) job dispatches the workflow: `POST https://api.github.com/repos/grahamhagenah/pushpin/actions/workflows/deploy.yml/dispatches`, body `{"ref":"main"}`, with a fine-grained token (this repo, Actions read/write) and a `User-Agent` header, without which GitHub answers 403. The token expires, so renew it in the job.
- **Keep-alive:** GitHub disables a workflow after 60 quiet days, so the `keepalive` job commits after 50. If it's disabled anyway: `gh workflow enable deploy.yml -R grahamhagenah/pushpin`.
