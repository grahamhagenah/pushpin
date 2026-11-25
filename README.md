# Pushpin's archive

Every listing on pushpin.city, a day at a time: `YYYY/MM/DD.jsonl.gz`, one JSON line per listing as that day's
first build saw it. Facts only: city, venue, name, date, times, kind, price, sold out, link, and the day Pushpin
first saw it (`first_seen`). Not the venues' descriptions or pictures.

A show is in each day's file from when it's announced until it's passed, so comparing days shows when it was
announced, sold out, changed or went. Written by `events/archive.py` on the main branch.
