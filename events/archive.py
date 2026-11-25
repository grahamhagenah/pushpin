"""A day's record of every listing, kept for good: the first build each day (by Boston's clock) writes what the
site lists that day, its facts alone, to YYYY/MM/DD.jsonl.gz in the archive's folder, which the deploy keeps on
the repo's archive branch. Later builds that day leave it be.

Each line is one listing as that day's build saw it: its city, venue, name, day, times, kind, price, whether it's
sold out (and which times), the line under its name, its link, and when Pushpin first saw it. Not what a venue
says about it or its picture, which are the venue's own words and art, there only to send people its way.

A show is in every day's file until it's passed, so day by day the files say when it was announced, when it sold
out, when its time changed, and when it quietly went (cancelled, as often as not).

    python3 -m events.archive dist/public/listings.json ../archive
"""

import gzip
import json
import sys
from datetime import date, datetime
from pathlib import Path

from events import build

FIELDS = ("title", "date", "times", "category", "venue", "detail", "price", "ages", "sold_out", "sold_out_times", "link")
README = """# Pushpin's archive

Every listing on pushpin.city, a day at a time: `YYYY/MM/DD.jsonl.gz`, one JSON line per listing as that day's
first build saw it. Facts only: city, venue, name, date, times, kind, price, sold out, link, and the day Pushpin
first saw it (`first_seen`). Not the venues' descriptions or pictures.

A show is in each day's file from when it's announced until it's passed, so comparing days shows when it was
announced, sold out, changed or went. Written by `events/archive.py` on the main branch.
"""


def cities_by_source():
    """Each source's city, by its name: the listings themselves don't say."""
    return {source["name"]: city.slug for city in build.CITIES for source in build.read_sources(city.sources, city.slug, city.clock)}


def day_of(listings):
    """The day the build was, by Boston's clock."""
    built = datetime.fromisoformat(listings["built"])
    return built.astimezone(build.BOSTON).date()


def records(listings, cities):
    """Each listing's facts, one record a listing, with its city and when it was first seen."""
    first_seen = listings.get("first_seen") or {}
    for name, source in sorted(listings.get("sources", {}).items()):
        for item in source.get("events", []):
            record = {"city": cities.get(name, ""), "source": name}
            record.update({key: item.get(key) for key in FIELDS if key in item})
            key = build.listing_id(date.fromisoformat(item["date"]), item["title"], item.get("venue") or name)[0]
            record["first_seen"] = first_seen.get(key) or item.get("added") or ""
            yield record


def write(listings_path, folder):
    """Today's file, if there isn't one yet; True where one was written."""
    listings = json.loads(Path(listings_path).read_text())
    day = day_of(listings)
    target = Path(folder) / f"{day:%Y/%m/%d}.jsonl.gz"
    if target.exists():
        print(f"archive: {target.relative_to(folder)} already kept")
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records(listings, cities_by_source())]
    # mtime=0, so the same day's listings make the same file byte for byte.
    target.write_bytes(gzip.compress(("\n".join(lines) + "\n").encode(), mtime=0))
    readme = Path(folder) / "README.md"
    if not readme.exists():
        readme.write_text(README)
    print(f"archive: wrote {target.relative_to(folder)}, {len(lines)} listings")
    return True


if __name__ == "__main__":
    write(sys.argv[1], sys.argv[2])
