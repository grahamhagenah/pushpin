"""Tests for shared/: the page both sites are built on, and the alerts. Run from the repo's top folder with:
python3 -m unittest"""

import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared import alerts, site  # noqa: E402


class Fetch(unittest.TestCase):
    def test_a_compressed_body_unpacked_though_not_asked_for(self):
        import gzip
        import zlib
        page = b'<div class="entry">The Sinclair</div>'
        self.assertEqual(site.unpacked(gzip.compress(page), "gzip"), page, "The Sinclair's, from November 2026")
        self.assertEqual(site.unpacked(gzip.compress(page), ""), page, "by its first bytes, where it isn't said")
        self.assertEqual(site.unpacked(zlib.compress(page), "deflate"), page)
        raw = zlib.compressobj(wbits=-zlib.MAX_WBITS)
        self.assertEqual(site.unpacked(raw.compress(page) + raw.flush(), "deflate"), page, "raw deflate too")
        self.assertEqual(site.unpacked(page, ""), page, "a plain one as it is")

    def test_a_429_waited_out_for_as_long_as_it_asks(self):
        import email.message
        import urllib.error

        def limited(after):
            headers = email.message.Message()
            if after is not None:
                headers["Retry-After"] = after
            return urllib.error.HTTPError("https://www.bso.org/events/x", 429, "Too Many Requests", headers, None)

        class Answer:
            headers = {}
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def geturl(self): return "https://www.bso.org/events/x"
            def read(self): return b"page"

        answers, waits = [limited("10"), Answer()], []

        def opened(request, timeout):
            answer = answers.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return answer

        with mock.patch.object(site.urllib.request, "urlopen", opened), mock.patch.object(site.time, "sleep", waits.append):
            self.assertEqual(site.fetch("https://www.bso.org/events/x", "x")[1], b"page", "bso.org's, November 2026")
        self.assertEqual(waits, [10], "its Retry-After")
        self.assertEqual(site.retry_after(limited("3600")), 30, "within reason")
        self.assertEqual(site.retry_after(limited(None)), 10, "a little, where it doesn't say")
        self.assertEqual(site.retry_after(limited("Fri, 27 Nov 2026 12:00:00 GMT")), 10, "or says it as a date")


class Page(unittest.TestCase):
    def test_header_names_both_pages_marking_this_one(self):
        news = site.page("news", "Newsfeed", "<ul></ul>", updated=datetime(2026, 9, 12, tzinfo=timezone.utc))
        events = site.page("events", "Events", "<ul></ul>")
        # Events is Pushpin Boston now; the page that used to be here sends a reader on to it.
        self.assertIn('<a href="./" aria-current="page">Newsfeed</a><a href="https://pushpin.city/">Events</a>', news)
        self.assertIn('<a href="https://news.grahamhagenah.com/">Newsfeed</a><a href="./" aria-current="page">Events</a>', events)
        self.assertIn('Updated <time class="updated" datetime="2026-09-12T00:00:00+00:00">', news)
        self.assertNotIn('<span class="header-note">', events, "no updated time given, no note")

    def test_each_site_adds_its_own_styles_and_icons(self):
        page = site.page("events", "Events", "", css=".mine { color: red; }", symbols=site.icon_symbols({"film": "<rect/>"}))
        self.assertLess(page.index(".row {"), page.index(".mine {"), "a site's styles come after the shared ones")
        self.assertIn('<symbol id="icon-film"', page)
        self.assertIn('content="Events"', page)

    def test_a_way_back_to_the_top(self):
        page = site.page("events", "Events", "<ul></ul>")
        self.assertIn('<button class="to-top" type="button" aria-label="Back to top">', page)
        self.assertLess(page.index("</main>"), page.index('class="to-top"'), "outside the page's content")

    def test_menu(self):
        menu = site.menu({"The Sinclair", "Brattle", "Arts at the Armory", "Club Passim"}, "All venues", "Venue")
        self.assertEqual(re.findall(r'<option value="([^"]*)">', menu), ["", "Arts at the Armory", "Brattle", "Club Passim", "The Sinclair"],
                         "everything first, then as they'd be said: The Sinclair among the S's")
        self.assertIn('<select class="pick" aria-label="Venue"><option value="">All venues</option>', menu)

    def test_icons(self):
        self.assertIn('aria-label="Film"', site.icon("film", "Film"))
        self.assertIn('aria-hidden="true"', site.icon("film"))


class Alerts(unittest.TestCase):
    def run_alerts(self, records, open_titles, shrinking=None):
        """Runs alerts.py on these sites' failures (and shrinkage), with these issues open; returns what it opened
        and closed."""
        calls, arguments, files = [], [], []
        for site_name, failing in records.items():
            if failing is None:  # Not built this run.
                arguments.append(f"{site_name}=/nonexistent/{site_name}.json")
                continue
            record = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
            json.dump({"failing": failing, "shrinking": (shrinking or {}).get(site_name, {})}, record)
            record.close()
            files.append(record.name)
            arguments.append(f"{site_name}={record.name}")
        issues = [{"number": number, "title": title} for number, title in enumerate(open_titles, start=1)]

        def gh(*args):
            calls.append(args)
            return json.dumps(issues) if args[:2] == ("issue", "list") else ""

        with mock.patch.object(alerts, "gh", gh), mock.patch.object(sys, "argv", ["alerts", *arguments]):
            alerts.main()
        for name in files:
            os.unlink(name)
        opened = [args[3] for args in calls if args[:2] == ("issue", "create")]
        closed = [issues[int(args[2]) - 1]["title"] for args in calls if args[:2] == ("issue", "close")]
        return opened, closed

    def failure(self, hours):
        return {"since": (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(), "error": "HTTP Error 520"}

    def test_opens_after_six_hours_only(self):
        opened, _ = self.run_alerts({"news": {"Kottke": self.failure(7), "Waxy.org": self.failure(1)}}, [])
        self.assertEqual(opened, ["Source failing: Kottke (news)"])

    def test_doesnt_open_twice(self):
        opened, closed = self.run_alerts({"news": {"Kottke": self.failure(9)}}, ["Source failing: Kottke (news)"])
        self.assertEqual((opened, closed), ([], []))

    def test_closes_once_it_loads_again(self):
        _, closed = self.run_alerts({"news": {}}, ["Source failing: Volts (news)"])
        self.assertEqual(closed, ["Source failing: Volts (news)"])

    def test_leaves_a_site_that_wasnt_built_alone(self):
        opened, closed = self.run_alerts(
            {"news": {}, "events": None},
            ["Source failing: Coolidge Corner (events)", "Source failing: Volts (news)"],
        )
        self.assertEqual((opened, closed), ([], ["Source failing: Volts (news)"]))

    def test_shrinking_opens_after_six_hours_and_closes_once_back(self):
        shrunk = lambda hours: {"since": (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(), "count": 3, "usual": 40}
        opened, closed = self.run_alerts({"events": {}}, [], shrinking={"events": {"Coolidge Corner": shrunk(7), "Brattle": shrunk(1)}})
        self.assertEqual((opened, closed), (["Source shrinking: Coolidge Corner (events)"], []))
        opened, closed = self.run_alerts({"events": {}}, ["Source shrinking: Coolidge Corner (events)", "Source failing: Brattle (events)"],
                                         shrinking={"events": {"Coolidge Corner": shrunk(9)}})
        self.assertEqual((opened, closed), ([], ["Source failing: Brattle (events)"]), "a failing issue isn't a shrinking one")
        _, closed = self.run_alerts({"events": {}}, ["Source shrinking: Coolidge Corner (events)"], shrinking={"events": {}})
        self.assertEqual(closed, ["Source shrinking: Coolidge Corner (events)"])


class Shrinking(unittest.TestCase):
    built = datetime(2026, 11, 25, 12, tzinfo=timezone.utc)

    def test_far_fewer_than_usual_once_theres_a_day_to_judge_by(self):
        previous = {"counts": {"Coolidge Corner": [40] * 8, "New": [40] * 7, "Small": [5] * 8}}
        history, shrinking = site.still_shrinking({"Coolidge Corner": 6, "New": 2, "Small": 1}, previous, self.built,
                                                  {"Coolidge Corner", "New", "Small"})
        self.assertEqual(shrinking, {"Coolidge Corner": {"since": self.built.isoformat(), "count": 6, "usual": 40}},
                         "not one with less than a day's counts, nor one that usually lists a handful")
        self.assertEqual(history["Coolidge Corner"], [40] * 8, "its low count not kept, so its usual stays")
        self.assertEqual(history["New"], [40] * 7 + [2])

    def test_a_little_fewer_is_nothing(self):
        _, shrinking = site.still_shrinking({"Brattle": 20}, {"counts": {"Brattle": [40] * 10}}, self.built, {"Brattle"})
        self.assertEqual(shrinking, {})

    def test_since_carries_over_and_two_weeks_is_its_new_usual(self):
        earlier = (self.built - timedelta(days=3)).isoformat()
        previous = {"counts": {"Tanglewood": [30] * 20}, "shrinking": {"Tanglewood": {"since": earlier, "count": 2, "usual": 30}}}
        _, shrinking = site.still_shrinking({"Tanglewood": 2}, previous, self.built, {"Tanglewood"})
        self.assertEqual(shrinking["Tanglewood"]["since"], earlier)
        previous["shrinking"]["Tanglewood"]["since"] = (self.built - timedelta(days=15)).isoformat()
        history, shrinking = site.still_shrinking({"Tanglewood": 2}, previous, self.built, {"Tanglewood"})
        self.assertEqual(shrinking, {})
        _, shrinking = site.still_shrinking({"Tanglewood": 2}, {"counts": history, "shrinking": shrinking}, self.built, {"Tanglewood"})
        self.assertEqual(shrinking, {}, "and stays its usual")

    def test_history_kept_for_one_that_didnt_load_and_dropped_for_one_taken_out(self):
        history, _ = site.still_shrinking({"Brattle": 12}, {"counts": {"Brattle": [10], "Passim": [9], "Gone": [4]}}, self.built,
                                          {"Brattle", "Passim"})
        self.assertEqual(history, {"Brattle": [10, 12], "Passim": [9]})
        cut = site.still_shrinking({"Brattle": 60}, {"counts": {"Brattle": list(range(100))}}, self.built, {"Brattle"})[0]
        self.assertEqual(len(cut["Brattle"]), site.SHRINK_HISTORY, "a week's counts at most")


if __name__ == "__main__":
    unittest.main()


class Scripts(unittest.TestCase):
    """The pages' scripts are written inside Python strings, where an escape like \\n turns into a real line
    break; one that no longer parses breaks the whole page (its filter, search and paging) without any other
    test noticing. Node, where it's installed (as on GitHub's runners), checks each one parses."""

    def test_page_scripts_parse(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node isn't installed")
        # Whichever pages this copy has: the newsfeed on its own (news/template.py) has no events page.
        scripts = {}
        for page in ("events", "news"):
            try:
                scripts[page] = importlib.import_module(f"{page}.build").INDEX_JS
            except ModuleNotFoundError:
                continue
        for name in ("AGES", "PREVIEWS", "SEARCH_KEYS", "TO_TOP"):
            scripts[name] = "".join(re.findall(r"<script>(.*?)</script>", getattr(site, name), re.S))
        for name, script in scripts.items():
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as file:
                file.write(script)
            result = subprocess.run([node, "--check", file.name], capture_output=True, text=True)
            os.unlink(file.name)
            self.assertEqual(result.returncode, 0, f"{name}: {result.stderr}")

