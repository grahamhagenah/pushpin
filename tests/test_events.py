"""Tests for build.py, against saved samples of each source (tests/fixtures), so they run offline and a change
that breaks a reader fails here instead of on the live page. Run from the repo's top folder with: python3 -m unittest

The samples are real responses, trimmed to a few items, except ticketmaster.json: the Discovery API needs a
key, so that one follows its documented format. When a site changes and its reader is updated, save a fresh
sample alongside the fix.
"""

import json
import os
import re
import sys
import unittest
import urllib.error
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from events import build  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "events"
# Which sample stands in for which address.
ROUTES = [
    ("aegwebprod.blob.core.windows.net/json/resources/8/events", "bowery.json"),  # A promoter's, over many venues.
    ("aegwebprod", "roadrunner.json"),
    ("sinclaircambridge.com/events/detail/1460677", "sinclair_show.html"),
    ("sinclaircambridge.com", "sinclair.html"),
    ("artsatthearmory.org/events.ics", "armory.ics"),
    ("api.membershipworks.com/v2/events", "membershipworks.xml"),
    ("24hourmusic.com/include/widgets/events/performancelist.asp?venue=1&", "burren.json"),
    ("berklee.edu/BPC/full-calendar-of-events-at-the-bpc", "berklee.html"),
    ("lilypadinman.com/home?format=json", "lilypad.json"),
    ("passim.org/live-music", "passim.html"),
    ("sallyobriensbar.com/music", "sally.html"),
    ("calendar.ploughandstars.com/events/calendar", "plough.html"),
    ("mccarthystoad.com", "toad.json"),  # Before the Iron Horse's: the same widget's address, another page's.
    ("data.accentapi.com/feed/87910.json", "jungle.json"),
    ("algolia.net/1/indexes/wp_platform_searchable_posts", "platform.json"),
    ("bostonconservatory.berklee.edu/events?page=", "bpl_end.xml"),  # Its later pages: none left.
    ("bostonconservatory.berklee.edu/events", "conservatory.html"),  # Its other shows' pages: no show time on them, so door times.
    ("mideastclub.com", "mideast.html"),
    ("brattlefilm.org", "brattle.html"),
    ("houseofblues.com", "houseofblues.html"),
    ("coolidge.org/showtimes", "coolidge.html"),
    ("drafthouse.com", "alamo.json"),
    ("boxofficeapi/schedule", "landmark_schedule.json"),
    ("boxofficeapi/movies", "landmark_movies.json"),
    ("app.ticketmaster.com", "ticketmaster.json"),
    ("cambridgema.gov", "cambridge.ics"),
    ("dice.fm", "dice.html"),
    ("tockify.com", "midway.ics"),
    ("lizardloungeclub.com", "lizardlounge.json"),
    ("calendar.mit.edu", "mit.json"),
    ("rss/events?types=test&page=1", "bpl.xml"),
    ("gateway.bibliocommons.com", "bpl_end.xml"),  # Every later page: the feed with nothing left in it.
    ("mfa.org/programs/lectures", "mfa_lectures.html"),
    ("mfa.org/programs/special-event", "mfa_special-event.html"),
    ("mfa.org/programs/film", "mfa_film.html"),
    ("mfa.org/programs/music", "mfa_music.html"),
    ("harvardfilmarchive.org/calendar", "hfa.html"),
    ("frenchlibrary.org", "frenchlibrary.html"),
    ("icaboston.org/calendar", "ica.html"),
    ("icaboston.org/events/colin-stetson", "ica_event.html"),
    ("internet-ticketing.com/websales/sales/LEXLEX/start", "tapos.html"),
    ("somervilletheatre.com/wp-json/wp/v2/wp_theatre_prod", "somerville_productions.json"),
    ("somervilletheatre.com/events/", "somerville_events.html"),
    ("internet-ticketing.com/websales/sales/CSBSOM/start", "somerville_sales.html"),
    ("capitoltheatreusa.com/wp-json/wp/v2/wp_theatre_prod", "capitol_productions.json"),
    ("capitoltheatreusa.com/events/", "404"),  # The Capitol shows only films, and has no events page.
    ("internet-ticketing.com/websales/sales/CSBARL/start", "capitol_sales.html"),
    ("rickshawstop.com", "seetickets.html"),
    ("yoshis.com", "yoshis.html"),
    ("sfmoma.org/events", "sfmoma.html"),
    ("exploratorium.edu/visit/calendar", "exploratorium.html"),
    ("ybca.org/calendar", "ybca.html"),
    ("bampfa.org/calendar", "bampfa.html"),
    ("bampfa.org/event/", "bampfa_event.html"),
    ("roxie.com/calendar", "roxie.html"),
    ("roxie.com/film/", "roxie_film.html"),
    ("theindependentsf.com", "ticketweb_set_out.html"),
    ("bimbos365club.com", "ticketweb_month_day.html"),
    ("westnewtoncinema.com/api/movie/playing-now", "veezi_now.json"),
    ("westnewtoncinema.com/api/movie/coming-soon", "veezi_soon.json"),
    ("massmoca.org/wp-json", "massmoca.json"),
    ("amherstcinema.org/calendar/month/2026-09-16", "amherst_day.html"),
    ("amherstcinema.org/calendar/month/", "empty.html"),  # Its other days: none.
    ("amherstcinema.org/films-and-events/", "amherst_film.html"),
    ("core.service.elfsight.com", "elfsight.json"),
    ("thedrakeamherst.org/events?format=json", "drake.json"),
    ("mahaiwe.org/events/?ical=1", "mahaiwe.ics"),
    ("sheatheater.org/d/0/?thisMonth=10", "shea_month.html"),
    ("sheatheater.org/d/0/", "empty.html"),  # Its other months: nothing.
    ("aomtheatre.com/event-calendar", "academy.html"),
    ("aomtheatre.com/aom_event/", "academy_event.html"),
    ("phoenixmovies.net/?/api_cinemamanager", "phoenix.json"),
    ("spektrix.com/berkshiretheatregroup/api/v3/events", "spektrix_events.json"),
    ("spektrix.com/berkshiretheatregroup/api/v3/instances", "spektrix_instances.json"),
    ("berkshiretheatregroup.org/", "btg_home.html"),  # Its calendar and home page, for each event's page.
    ("arts.umass.edu/performing-arts/events", "umass_fac.html"),
    # Bombyx's events' pages, for their names; any other event's page holds no name, and its event is left out.
    ("bombyx.live/events/page/", "empty.html"),  # Its later pages.
    ("bombyx.live/events/an-evening-with-tom-rush-2/", "bombyx_an-evening-with-tom-rush-2.html"),
    ("bombyx.live/events/rickie-lee-jones-2/", "bombyx_rickie-lee-jones-2.html"),
    ("bombyx.live/events/5rhythms-dance-class-12-5-26/", "bombyx_5rhythms-dance-class-12-5-26.html"),
    ("bombyx.live/events/film-night-dreaming-of-a-jewish-christmas/", "bombyx_film-night-dreaming-of-a-jewish-christmas.html"),
    ("bombyx.live/events/", "bombyx.html"),
    ("gardencinemas.net/?vdate=11/24/2026", "garden.html"),
    ("gardencinemas.net/?vdate=", "empty.html"),  # Its other days.
    ("gardencinemas.net", "garden.html"),
    ("theheavyculture.coop/shows", "heavyculture.html"),
    ("doubleedgetheatre.org/events", "doubleedge.html"),
    ("shelburnefallsmemorialhall.org/pothole-pictures/page/", "empty.html"),  # Its later page.
    ("shelburnefallsmemorialhall.org/pothole-pictures/", "pothole.html"),
    ("shelburnefallsmemorialhall.org/its-a-wonderful-life-1946/", "pothole_film.html"),
    ("shelburnefallsmemorialhall.org/metropolitan-operas/", "memorialhall_met.html"),
    ("live.barringtonhallgb.com", "tickettailor.html"),
    ("symphonyhallspringfield.com/events/detail/jeff-dunham", "symphonyhall_dunham.html"),
    ("symphonyhallspringfield.com/events/detail/", "empty.html"),  # Its other shows' pages.
    ("symphonyhallspringfield.com/events", "symphonyhall.html"),
    ("52sumner.com/events-and-tickets", "sumner.html"),
    ("hopecenterforthearts.org/upcoming", "hope_upcoming.html"),
    ("hopecenterforthearts.org/events/irish-tenors-christmas", "hope_event.html"),
    ("hopecenterforthearts.org/events/", "empty.html"),  # Its other show's page.
    ("delaluz.org/calendar", "delaluz.html"),
    ("m3pn87-t7.myshopify.com/products.json", "hutghis.json"),
    ("nohoarts.org/upcoming-events", "nohoarts.html"),
    ("latchis.com/wp-json/tribe/events/v1/events", "latchis.json"),
    ("bmcvt.org/wp-json/tribe/events/v1/events", "bmc.json"),
    ("brattleboromuseum.org/wp-json/tribe/events/v1/events", "bmac.json"),
    ("epsilonspires.org/upcoming-events", "epsilonspires.html"),  # Cut to its event data and a link.
    # Written by hand in the shape of Eventbrite's API, which needs a token to read.
    ("eventbriteapi.com/v3/organizers/119527559781/events/", "eventbrite_visions.json"),
    ("dspshows.com/venues/bombyx", "dsp.html"),
    ("bso.org/events/nov-27-tli-jazz-ted-rosenthal", "bso_rosenthal.html"),
    ("bso.org/events/h-h-handels-messiah-2026", "bso_messiah.html"),
    ("thefoundryws.com/event/", "foundry.html"),  # Its later pages too: they can be its first again.
    ("m.movies.abenity.com/theatre?id=725&date=11/24/2026", "abenity.html"),
    ("m.movies.abenity.com/theatre", "empty.html"),  # Its other days.
    ("amherst.edu/news/events/calendar?f%5B0%5D=type_of_event%3Alec&f%5B1%5D=type_of_event%3Aperform&page=", "empty.html"),
    ("amherst.edu/news/events/calendar", "amherst.html"),
    ("events.umass.edu/api/2/events", "localist_umass.json"),
    ("events.mtholyoke.edu/api/2/events", "localist_mhc.json"),
    ("smith.edu/news-events/events?field_event_category_target_id=100023&page=", "empty.html"),  # Its later pages.
    ("smith.edu/news-events/events?field_event_category_target_id=100023", "smith_performances.html"),
    ("smith.edu/news-events/events?field_event_category_target_id=100131&page=", "empty.html"),
    ("smith.edu/news-events/events?field_event_category_target_id=100131", "smith_readings.html"),
    # The Marigold's shows' pages; any other show's page is its home page, named only Marigold, and left out.
    ("marigold.org/jeff-the-brotherhood-with-cliffrose-ian-st-george/", "marigold_event.html"),
    ("marigold.org/sunday-blues-jam-december/", "marigold_jam.html"),
    ("marigold.org/", "marigold.html"),
    # Pushpin NYC's.
    ("filmforum.org", "filmforum.html"),
    ("metrograph.com/nyc", "metrograph.html"),
    ("ifccenter.com", "ifc.html"),
    ("nitehawkcinema.com/williamsburg/wp-json/nj/v1/showtime/listings", "filmbot_listings.json"),
    ("nitehawkcinema.com/williamsburg/wp-json/nj/v1/show?", "filmbot_shows.json"),
    ("spectacletheater.com/spex-rolling.html", "spectacle.html"),
    ("bam.org/api/BAMApi", "bam.json"),
    ("lpr.com/wp-admin/admin-ajax.php?action=do_ajax&fn=get_homepageEvents&json%5Bdate%5D=20261117&paged=1", "lpr.html"),
    ("lpr.com/wp-admin/admin-ajax.php", "empty.html"),  # Its later pages: nothing more.
    ("roulette.org/calendar", "roulette.html"),
    ("issueprojectroom.org/events", "issue.html"),
    ("pioneerworks.org/calendar", "pioneerworks.html"),
    ("anthologyfilmarchives.org/film_screenings/calendar?month=", "empty.html"),  # Next month's grid: nothing on it yet.
    ("anthologyfilmarchives.org/film_screenings/calendar", "anthology.html"),
    ("quadcinema.com", "quad.html"),
    ("mcnallyjackson.com/events/2026/11", "mcnally.html"),
    ("mcnallyjackson.com/events/", "empty.html"),  # Next month's page.
    ("villagevanguard.com", "vanguard.html"),
    ("nationalsawdust.org/performances", "nationalsawdust.html"),
]


def sample(url, **kwargs):
    for pattern, name in ROUTES:
        if pattern in url:
            if name == "404":  # A page the site doesn't have.
                raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
            return (FIXTURES / name).read_text()
    raise AssertionError(f"no sample for {url}")


def source(kind, url, category="music", name="Somewhere"):
    return {"kind": kind, "url": url, "category": category, "name": name}


class Readers(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(build, "fetch", sample)
        patcher.start()
        self.addCleanup(patcher.stop)

    def read(self, kind, url, category="music", name="Somewhere", sorts_its_own=False):
        found, error = build.READERS[kind](source(kind, url, category, name)), None
        self.assertTrue(found, f"{kind} read nothing from its sample")
        for item in found:
            self.assertTrue(item["title"].strip())
            self.assertIsInstance(item["date"], date)
            self.assertTrue(all(isinstance(moment, time) for moment in item["times"]))
            self.assertTrue(item["link"].startswith("http"), item["link"])
            if not sorts_its_own:
                self.assertEqual(item["category"], category)
        return found

    def test_aeg_promoter_feed_is_taken_for_one_venue(self):
        # Bowery Presents' Boston feed books a dozen venues; Royale's line takes Royale's shows out of it, and
        # leaves the Sinclair's, which this page reads from the Sinclair's own site.
        url = "https://aegwebprod.blob.core.windows.net/json/resources/8/events/7301mbln09/events.json"
        found = self.read("aeg", url, "music", "Royale")
        self.assertEqual([item["title"] for item in found], ["Willow Avalon", "Ashley Cooke"])
        self.assertEqual([item["title"] for item in self.read("aeg", url, "music", "The Sinclair")],
                         ["Damien Jurado", "John Craigie"])

    def test_aeg(self):
        found = self.read("aeg", "https://aegwebprod.blob.core.windows.net/json/events/219/events.json")
        self.assertEqual(len(found), 3)
        self.assertTrue(all(item["times"] for item in found))
        self.assertTrue(any(item["detail"].startswith("with ") for item in found))
        # Its picture about 678 pixels wide, not a thumbnail; its ages; no price, for the $0 it gives.
        self.assertTrue(all(item["image"].startswith("https://images.discovery-prod.axs.com/") for item in found))
        self.assertEqual({item["ages"] for item in found}, {"All ages", "18+"})
        self.assertFalse(any(item["price"] for item in found))

    def test_axs_show_times_without_cancelled_shows(self):
        with mock.patch.object(build, "today", lambda: date(2026, 9, 1)):
            found = self.read("axs", "https://www.sinclaircambridge.com/events/all")
        self.assertEqual([item["title"] for item in found], ["Chanel Beads", "DON WEST", "John Craigie", "The Glitter Boys"])
        first = found[0]
        # Its own page's show time, not the listing's door time, which its preview gives.
        self.assertEqual((first["date"], first["times"]), (date(2026, 9, 13), [time(20, 0)]))
        self.assertEqual(first["about"], ["Doors 7pm · All Ages"])
        self.assertEqual(first["ages"], "All ages")
        self.assertTrue(first["image"].startswith("https://images.discovery-prod.axs.com/"))
        self.assertEqual(first["detail"], "with Horse Vision, Ivy Knight")
        self.assertEqual(first["link"], "https://www.sinclaircambridge.com/events/detail/1460677")
        self.assertEqual(found[1]["times"], [time(19, 30)], "a page without a show time leaves the door time")
        self.assertEqual(found[2]["about"][0].split(" · ")[0], "Fall 2026", "the tour, first")
        self.assertEqual(found[3]["detail"], "", "no supporting acts")

    def test_axs_reads_show_pages_only_for_shows_in_the_window(self):
        asked = []
        with mock.patch.object(build, "fetch", lambda url, **options: asked.append(url) or sample(url)), \
                mock.patch.object(build, "today", lambda: date(2026, 6, 1)):  # Its sample's shows are all past the window then.
            build.read_axs(source("axs", "https://www.sinclaircambridge.com/events/all", "music", "The Sinclair"))
        self.assertEqual(asked, ["https://www.sinclaircambridge.com/events/all"])

    def test_membershipworks_keeps_the_lines_kind(self):
        """Arts Collaborative Medford's events, from its MembershipWorks feed: its concerts and its jam, at their
        times, with their pictures; not its discussion groups, markets or meetings."""
        url = "https://api.membershipworks.com/v2/events?_op=rss&org=35160&grp=2"
        found = build.read_membershipworks(source("membershipworks", url, "music", "Arts Collaborative Medford"))
        self.assertEqual([(item["title"], item["date"], item["times"]) for item in found], [
            ("An Evening of Scottish Fiddle", date(2026, 12, 11), [time(19, 30)]),
            ("Blizzard of Blues", date(2026, 12, 12), [time(19, 0)]),
            ("The Jam Down By Riverside (potluck)", date(2026, 12, 13), [time(13, 0)]),
        ])
        fiddle = found[0]
        self.assertEqual(fiddle["link"], "https://artscollabmedford.org/eventscalendar#!event/2026/12/11/an-evening-of-scottish-fiddle")
        self.assertTrue(fiddle["image"].startswith("https://d1tif55lvfk8gc.cloudfront.net/"))
        self.assertIn("Isabel Oliart", " ".join(fiddle["about"]))
        talks = build.read_membershipworks(source("membershipworks", url, "art", "Arts Collaborative Medford"))
        self.assertEqual([item["title"] for item in talks], ["World Poetry Salon", "Drawn Together: Art of Aging"],
                         "an art line would keep its talks, still not its markets or meetings")

    def test_armory_by_kind(self):
        found = build.read_armory(source("armory", "https://artsatthearmory.org/events.ics", "music", "Arts at the Armory"))
        self.assertEqual({item["title"]: item["category"] for item in found}, {
            "The Bowery Presents ear with Oral": "music",
            "Lovestruck Books Presents: Grim Tidings Release-Day Bash with B.K. Borison": "art",
            '"A Cell Phone Movie" Screening': "film",
            "Get to the Gig Presents Armand Hammer with Curly Castro": "music",
        })  # Not its comedy, or the show it moved to the Royale.
        self.assertEqual([item["title"] for item in found if item["sold_out"]], ["The Bowery Presents ear with Oral"], "SOLD OUT: out of its name")
        reading = next(item for item in found if item["category"] == "art")
        self.assertEqual((reading["date"], reading["times"]), (date(2026, 9, 15), [time(18, 30)]))
        self.assertFalse(any("$(" in line or "fbq(" in line for item in found for line in item["about"]), "not its ticket button's script")
        self.assertTrue(any("&" in line for item in found for line in item["about"]))
        self.assertFalse(any("&amp;" in line for item in found for line in item["about"]))

    def test_squarespace_shows_not_yoga_or_private_events(self):
        found = self.read("squarespace", "https://www.lilypadinman.com/home")
        self.assertEqual([item["title"] for item in found], ["2nd Annual Bach & Beer with Aaron Larget-Caplan", "Elan Mehler Trio"])
        first = found[0]
        self.assertEqual((first["date"], first["times"]), (date(2026, 9, 13), [time(13, 30)]))
        self.assertEqual(first["link"], "https://www.lilypadinman.com/home/2026/bach-and-beer-with-aaron-larget-caplan")
        self.assertTrue(first["about"][0].startswith("$25 admission"))
        self.assertFalse(any("--sqs" in line or "{" in line for item in found for line in item["about"]), "not its styles")

    def test_plough_and_stars_nights_from_its_month_grid(self):
        class November(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 11, 19, 12, tzinfo=tz)
        with mock.patch.object(build, "datetime", November):
            found = self.read("plough", "https://calendar.ploughandstars.com/events/calendar", "music", "The Plough and Stars")
        shows = [(item["date"], item["times"], item["title"], item["detail"]) for item in found]
        # From today on, each month once (the sample stands for every month asked for); its start alone ("4-6p").
        self.assertEqual(shows[:5], [
            (date(2026, 11, 19), [time(22, 0)], "Fat n’ Gristle Blues Band", ""),
            (date(2026, 11, 20), [time(22, 0)], "The Handymen", ""),
            (date(2026, 11, 21), [time(22, 0)], "KaBeatles", "Hosted by MC Kabir"),
            (date(2026, 11, 21), [time(16, 0)], "Mean Black Spider", ""),
            (date(2026, 11, 22), [time(16, 0)], "The Starlings", ""),  # Not its stray "with".
        ])
        self.assertEqual(len(found), 11)
        self.assertIn((date(2026, 11, 22), [], "MBF", ""), shows, "no time given: none")
        titles = {item["title"] for item in found}
        self.assertNotIn("Trivia Night", titles)
        self.assertNotIn("No Live Music", titles, "not Thanksgiving, when there's none")

    def test_toad_shows_from_the_calendar_it_shares_with_mccarthys(self):
        url = "https://core.service.elfsight.com/p/boot/?page=https%3A%2F%2Fwww.mccarthystoad.com%2Fcalendar&w=3fdd143a-e20d-4e92-9fcb-84d101240a59"
        found = self.read("toad", url, "music", "Toad")
        # The band as its name, the night it's in as its detail; not Upstairs at McCarthy's, or a weekly night.
        self.assertEqual([(item["date"], item["times"], item["title"], item["detail"]) for item in found][:4], [
            (date(2026, 11, 20), [time(18, 0)], "Jake Clough", "Friday club"),
            (date(2026, 11, 20), [time(22, 30)], "Prestige Worldwide", "Late Night Cover Band"),
            (date(2026, 11, 21), [time(16, 0)], "Stan Martin Band", "Saturday Revival"),
            (date(2026, 11, 22), [time(16, 0)], "Dennis Brennan Band", "Sunday Revival Series"),
        ])
        self.assertEqual(len(found), 8)
        titles = {item["title"] for item in found}
        self.assertNotIn("Late Night Cover Band", titles, "a night whose band isn't named yet")
        self.assertFalse(titles & {"Monday Open Mic", "Baker Thomas Band Wednesdays"}, "nor one every week")
        self.assertFalse(any("McCarthy" in title for title in titles), "nor upstairs")
        self.assertEqual(build.TOAD_NIGHT.match("Late Night band 'Jumper Cable'").groups(), ("Late Night band", "Jumper Cable"))

    def test_the_jungles_eventbrite_shows_from_its_sites_widget(self):
        found = self.read("sociablekit", "https://data.accentapi.com/feed/87910.json", "music", "The Jungle")
        first = found[0]
        self.assertEqual((first["date"], first["times"], first["title"]),
                         (date(2026, 11, 21), [time(16, 0)], "Monty Neysmith's Original Symarip, Riki Rocksteady"))
        self.assertTrue(first["sold_out"], "its description says so")
        self.assertTrue(first["link"].startswith("https://www.eventbrite.com/e/"))
        self.assertTrue(first["image"].startswith("https://img.evbuc.com/"))
        by_title = {item["title"]: item for item in found}
        # A bill's bands by commas, whether "|", "//" or "/" set them apart.
        self.assertIn("Irrational Apparatus, JB & The Weather Machine, Drip Dry", by_title)
        self.assertIn("The Glow, Konaa Kateru, BUND, Corinna Parrish", by_title)
        self.assertEqual(by_title["Vices inc, Type 66, Jacob Hebert"]["price"], "Free")
        self.assertEqual(by_title["Cold Start, Dogtown, Yopoh"]["price"], "$11.85–$17.15")
        # Not its open mics, karaoke, comedy or trivia, or the night it closes early.
        self.assertFalse([title for title in by_title if re.search(r"open mic|karaoke|trivia|comedy|closed", title, re.I)])
        self.assertEqual(len(found), 14)
        self.assertEqual(re.sub(r"(?:[,/\s]+TBA)?[,/\s]*$", "", "KK Gordon, TBA"), "KK Gordon")

    def test_the_platforms_music_and_dance_from_its_search_index(self):
        url = "https://y1vsi41hoc-dsn.algolia.net/1/indexes/wp_platform_searchable_posts?query=&hitsPerPage=1000"
        found = self.read("platform", url, "music", "The Platform", sorts_its_own=True)
        shows = {(item["date"], item["times"][0], item["title"], item["category"], item["detail"]) for item in found}
        # A performance a listing, by its show's name as written, filed by its show's genres: dance is art & talks.
        self.assertIn((date(2026, 11, 21), time(20, 0), "BalletX", "art", "Takeda Theater"), shows)
        self.assertIn((date(2026, 11, 22), time(15, 0), "BalletX", "art", "Takeda Theater"), shows)
        self.assertIn((date(2027, 2, 6), time(20, 0), "The Hot Sardines", "music", "Takeda Theater"), shows)
        # Not in capitals, nor with the season it's filed under.
        self.assertIn((date(2026, 12, 12), time(19, 30), "Across the Ocean: Voices from Southeast Asia", "music", "Tempo Stage"), shows)
        self.assertIn((date(2027, 3, 6), time(20, 0), "Cassie Kollman", "music", "Tempo Stage"), shows)
        titles = [item["title"] for item in found]
        self.assertFalse([title for title in titles if "test" in title.lower() or "Koubi" in title],
                         "not a test, nor one with no date")
        self.assertNotIn("Chuwi", titles, "not the site's Spanish copies")
        self.assertEqual(len(titles), len(set((item["title"], item["date"], tuple(item["times"])) for item in found)), "each once")
        self.assertTrue(all(item["link"].startswith("https://www.theplatformkendall.org/") for item in found))

    def test_boston_conservatory_without_its_students_recitals(self):
        found = self.read("conservatory", "https://bostonconservatory.berklee.edu/events", "music", "Boston Conservatory",
                          sorts_its_own=True)
        by_title = {}
        for item in found:
            by_title.setdefault(item["title"], item)
        carols = by_title["Boston Conservatory Choirs: Carols at St. Clements—Welcoming Winter"]
        self.assertEqual((carols["date"], carols["times"], carols["category"], carols["detail"], carols["price"]),
                         (date(2026, 12, 1), [time(19, 30)], "music", "St. Clements", "Free"), "its hall, past its label")
        self.assertEqual(carols["address"], ["1105 Boylston St", "Boston", "02215"])
        self.assertTrue(carols["about"][0].startswith("Boston Conservatory choirs gather"), "its own words, not its address")
        self.assertNotIn("Contemporary Theater Capstone: Double Sixes", by_title, "not the graduating class's capstones")
        self.assertEqual(by_title["Composers Recital Series"]["category"], "music")
        self.assertNotIn("Class Recital: Sophomore Alexander Technique", by_title, "not a class's recital")
        self.assertEqual(len(found), 8)
        self.assertIn("Faculty Recital: Preludes, Featuring Max Levinson, Piano", by_title)

    def test_sally_obriens_nights_from_its_handwritten_page(self):
        class November(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 11, 19, 12, tzinfo=tz)
        with mock.patch.object(build, "datetime", November):
            found = self.read("sally", "https://www.sallyobriensbar.com/music/", "music", "Sally O'Brien's")
        # Two shows the 21st, "followed by ..." between them; not Thanksgiving, when there's no band.
        self.assertEqual([(item["date"], item["times"], item["title"], item["price"]) for item in found], [
            (date(2026, 11, 19), [time(19, 30)], "Universal Union", "Free"),
            (date(2026, 11, 20), [time(19, 30)], "Mule Variations", "$10"),
            (date(2026, 11, 21), [time(12, 0)], "Benefit to Fight Parkinson's Disease", ""),
            (date(2026, 11, 21), [time(19, 30)], "Tim Gearan Band", "$10"),
            (date(2026, 11, 22), [time(21, 30)], "Dub Apocalypse", "Free"),
            (date(2026, 12, 2), [time(19, 30)], "Fandango featuring Brian Templeton", "Free"),
            (date(2026, 12, 4), [time(19, 30)], "Chris Cote and his Band of These Guys", "$10"),
        ])
        self.assertTrue(found[0]["image"].startswith("https://images.getbento.com/"), "its own poster")
        self.assertEqual(found[3]["image"], "", "the night's picture is its first show's")
        self.assertEqual(found[1]["link"], "https://www.sallyobriensbar.com/music/")

    def test_passim_club_shows_once_each(self):
        found = self.read("passim", "https://www.passim.org/live-music/")
        # Not the shows it presents elsewhere, or the cancelled one; The Clements Brothers only once.
        self.assertEqual([(item["date"], item["title"], item["times"]) for item in found], [
            (date(2026, 9, 16), "Ágora Cultural Architects present: Richard Peña Trío", [time(20, 0)]),
            (date(2026, 9, 27), "The Clements Brothers", [time(19, 0)]),
            (date(2026, 11, 22), "Bruce Molsky", [time(14, 0)]),
        ])
        self.assertTrue(found[0]["link"].startswith("https://www.passim.org/live-music/events/"))

    def test_showare_venue_shows_not_those_it_sells_for_elsewhere(self):
        url = "https://tickets.24hourmusic.com/include/widgets/events/performancelist.asp?venue=1"
        found = self.read("showare", url, "music", "The Burren")
        # Not Lunasa, which it sells for the Somerville Theatre.
        self.assertEqual([(item["date"], item["title"], item["times"]) for item in found], [
            (date(2026, 11, 6), "Molly Pinto Madigan, Sunfisher", [time(19, 0)]),
            (date(2026, 11, 18), "Brian O'Donovan Legacy Series: Revels Chantey Sing with David Coffin", [time(19, 30)]),
        ])
        first, second = found
        self.assertEqual(first["link"], "https://tickets.24hourmusic.com/eventperformances.asp?evt=1898")
        self.assertEqual(first["image"], "https://tickets.24hourmusic.com/uplimage/MPMSF26sw.jpg")
        self.assertEqual(first["price"], "$29.95")
        self.assertTrue(first["about"][0].startswith("Molly Pinto Madigan"))
        self.assertFalse(any("<" in line or "&rsquo;" in line for item in found for line in item["about"]))
        self.assertEqual((first["sold_out"], second["sold_out"]), (False, True))

    def test_berklee_shows_with_their_times(self):
        found = self.read("berklee", "https://www.berklee.edu/BPC/full-calendar-of-events-at-the-bpc", "music", "Berklee Performance Center")
        self.assertEqual([(item["date"], item["title"], item["times"]) for item in found], [
            (date(2026, 11, 6), "Warren Miller's Days Off", [time(19, 30)]),
            (date(2026, 11, 9), "Jazz Composers Alliance Orchestra in Concert", [time(20, 0)]),
            (date(2027, 5, 2), "Ndlovu Youth Choir", [time(15, 0)]),
        ])
        self.assertEqual(found[0]["link"], "https://www.berklee.edu/BPC/events/warren-millers-days-off")
        self.assertTrue(found[0]["about"][0].startswith("This fall, drop in on Warren Miller"))
        self.assertTrue(found[0]["image"].startswith("https://www.berklee.edu/sites/default/files/"))

    def test_ticketweb_venue_without_room(self):
        found = self.read("ticketweb", "https://mideastclub.com/")
        self.assertEqual(len(found), 3)
        self.assertTrue(all(item["times"] for item in found))
        self.assertFalse(any(" - " in item["venue"] or " – " in item["venue"] for item in found))

    def test_jsonld_brattle_titles_without_showtimes(self):
        found = self.read("jsonld", "https://brattlefilm.org/coming-soon/", "film")
        self.assertFalse(any("@" in item["title"] for item in found))

    def test_jsonld_house_of_blues(self):
        self.read("jsonld", "https://boston.houseofblues.com/shows")

    def test_coolidge_each_day(self):
        found = self.read("coolidge", "https://coolidge.org/showtimes", "film")
        self.assertTrue(all(item["times"] and "coolidge.org/films/" in item["link"] for item in found))

    def test_alamo_skips_past_showings(self):
        found = self.read("alamo", "https://drafthouse.com/s/mother/v2/schedule/market/boston", "film")
        sessions = __import__("json").loads(sample("drafthouse.com"))["data"]["sessions"]
        self.assertEqual(len(found), sum(session["status"] != "PAST" for session in sessions))
        self.assertTrue(all("drafthouse.com/boston/show/" in item["link"] for item in found))

    def test_landmark_titles(self):
        found = self.read("landmark", "X019B", "film")
        titles = {movie["title"] for movie in __import__("json").loads(sample("boxofficeapi/movies"))}
        self.assertTrue({item["title"] for item in found} <= titles)

    def test_ticketmaster_keeps_concerts_only(self):
        with mock.patch.dict(os.environ, {"TICKETMASTER_KEY": "test"}):
            found = self.read("ticketmaster", "KovZ917AJnQ")
        names = {item["title"]: item for item in found}
        self.assertIn("Oteil Burbridge with LaMP - Wish Benefit Tour", names)
        self.assertNotIn("Troy Hawke", names, "Arts & Theatre shows are left out")
        self.assertNotIn("Cancelled Show", names)
        self.assertEqual(names["Late Show, Time To Be Announced"]["times"], [])
        self.assertIn("Untyped Show", names, "a show without a type keeps the venue's category")

    def test_eventbrite_organizer_events(self):
        with mock.patch.dict(os.environ, {"EVENTBRITE_TOKEN": "test"}):
            found = self.read("eventbrite", "https://www.eventbrite.com/o/visions-video-119527559781", "film", "Visions Video")
        by_title = {item["title"]: item for item in found}
        self.assertEqual(set(by_title), {"Micro-Cinema #6: The Tallest Dwarf w/ filmmaker Julie Forrest Wyman",
                                         "Evil Puddle screening w/ director Charles Roxburgh & Matt Farley in person",
                                         "Outdoor Screening at Look Park"}, "not one canceled, nor one online only")
        dwarf = by_title["Micro-Cinema #6: The Tallest Dwarf w/ filmmaker Julie Forrest Wyman"]
        self.assertEqual((dwarf["date"], dwarf["times"], dwarf["price"], dwarf["image"], dwarf["address"]),
                         (date(2026, 12, 5), [time(19, 0)], "$10–$15", "https://img.evbuc.com/original.jpg", None),
                         "its local time, its price range, its full-size picture, and no address at the venue's own")
        puddle = by_title["Evil Puddle screening w/ director Charles Roxburgh & Matt Farley in person"]
        self.assertEqual((puddle["price"], puddle["sold_out"]), ("Free", True))
        self.assertEqual(by_title["Outdoor Screening at Look Park"]["address"], ["300 N Main St", "Florence", "01062"],
                         "one held elsewhere says where")

    def test_eventbrite_without_token_is_skipped(self):
        with mock.patch.dict(os.environ, {"EVENTBRITE_TOKEN": ""}):
            self.assertEqual(build.read_eventbrite(source("eventbrite", "https://www.eventbrite.com/o/x-1")), [])

    def test_ticketmaster_without_key_is_skipped(self):
        with mock.patch.dict(os.environ, {"TICKETMASTER_KEY": ""}):
            self.assertEqual(build.read_ticketmaster(source("ticketmaster", "X")), [])

    def test_jsonld_dice(self):
        found = self.read("jsonld", "https://dice.fm/venue/deep-cuts-nd6q")
        self.assertEqual(len(found), 3)
        self.assertEqual(found[0]["times"], [time(19, 0)])
        self.assertTrue(all(item["link"].startswith("https://dice.fm/event/") for item in found))

    def test_ics(self):
        self.read("ics", "https://www.cambridgema.gov/arts/Calendar.ics", "film")

    def test_ics_tockify_times_in_boston(self):
        found = self.read("ics", "https://tockify.com/api/feeds/ics/midwaycafejp")
        # 01:30 UTC on Sep 12 is 9:30pm on Sep 11 in Boston.
        self.assertEqual((found[0]["date"], found[0]["times"]), (date(2026, 9, 11), [time(21, 30)]))
        self.assertEqual(found[0]["title"], "CAVA (Germany) w/ Lupo Citta")

    def test_french_library_screenings_and_talks(self):
        found = build.read_french_library(source("frenchlibrary", "https://frenchlibrary.org/upcoming-events/", "art", "French Library"))
        kinds = {item["title"]: item["category"] for item in found}
        self.assertEqual(kinds["Ciné Club Series: Hugo by Pascal Bonitzer"], "film")
        self.assertEqual(kinds["Leïla Slimani: I’ll Take the Fire"], "art")
        # A screening known only by its description: "silent cinema as it was meant to be seen".
        self.assertEqual([kind for title, kind in kinds.items() if "House of Usher" in title], ["film"])
        # Not the children's story time, the cooking class, or the online conversation club.
        self.assertEqual(len(found), 3)
        hugo = next(item for item in found if item["title"].startswith("Ciné Club"))
        self.assertEqual((hugo["date"], hugo["times"]), (date(2026, 9, 15), [time(18, 0)]))

    def test_hfa_screenings_with_credits(self):
        found = self.read("hfa", "https://harvardfilmarchive.org/calendar", "film")
        self.assertEqual(len(found), 4)
        snow = next(item for item in found if item["title"] == "Snow White")
        self.assertEqual((snow["date"], snow["times"]), (date(2026, 9, 14), [time(19, 0)]))
        self.assertEqual(snow["about"][0], "Directed by João César Monteiro, 2000")
        self.assertTrue(snow["link"].startswith("https://harvardfilmarchive.org/calendar/snow-white"))
        self.assertTrue(any("Screening on Film" in line for item in found for line in item["about"]))

    def test_veezi_site_showtimes(self):
        found = self.read("veezi", "https://www.westnewtoncinema.com/", "film")
        rebel = next(item for item in found if item["title"] == "Rebel with a Clause")
        self.assertEqual((rebel["date"], rebel["times"]), (date(2026, 9, 24), [time(19, 0)]))
        self.assertEqual(rebel["link"], "https://www.westnewtoncinema.com/movie/rebel-with-a-clause")
        self.assertEqual(rebel["about"][-1], "Directed by Brandt Johnson · 1h 26m")

    def test_a_city_keeps_its_own_clock(self):
        from zoneinfo import ZoneInfo
        pacific = dict(source("ticketweb", "x", "music", "The Independent"), zone=ZoneInfo("America/Los_Angeles"))
        # An 8pm show in San Francisco is 8pm there, not 11pm here; its calendar entry says so too.
        show = build.event(pacific, "A show", date(2026, 9, 18), time(20, 0))
        self.assertEqual(show["zone"], "America/Los_Angeles")
        when = datetime(2026, 9, 18, tzinfo=timezone.utc)
        self.assertIn("DTSTART:20260919T030000Z", build.render_calendar("Bay Area", "x", [show], when))  # 8pm Pacific.
        here = build.event(source("ticketweb", "x", "music", "Middle East"), "A show", date(2026, 9, 18), time(20, 0))
        self.assertIn("DTSTART:20260919T000000Z", build.render_calendar("Boston", "x", [here], when))  # 8pm Eastern.

    def test_ybca_lists_its_days_and_not_its_runs(self):
        # The sample holds an exhibition, dated across months, and two things happening on a day.
        found = self.read("ybca", "https://ybca.org/calendar/", "art", "YBCA", sorts_its_own=True)
        self.assertEqual(len(found), 2)
        self.assertTrue(all(item["times"] and item["image"] for item in found))

    def test_exploratorium_lists_a_card_on_every_day_it_runs(self):
        found = self.read("exploratorium", "https://www.exploratorium.edu/visit/calendar", "art", "Exploratorium")
        self.assertTrue(all(item["image"] and "responsive_16_9" in item["image"] for item in found))
        # Its cards give a start and an end for each day, so a card with four times runs on two days.
        self.assertTrue(len(found) >= len({item["title"] for item in found}))

    def test_sfmoma_takes_each_listing_its_own_name(self):
        found = self.read("sfmoma", "https://www.sfmoma.org/events/", "art", "SFMOMA", sorts_its_own=True)
        # The name written beside a listing's own line, not the record of the listing after it: each name
        # belongs with the address it links to.
        for item in found:
            self.assertTrue(item["image"])
            first = re.sub(r"[^a-z]+", "-", item["title"].casefold()).strip("-").split("-")[0]
            self.assertIn(first, item["link"], item["title"])

    def test_yoshis_reads_the_day_from_the_label_its_links_carry(self):
        # Its rows head with "Fri 9.18" and no year; the label on its links has the day written out in full.
        found = self.read("yoshis", "https://yoshis.com/", "music", "Yoshi's")
        self.assertEqual(len(found), 2)
        self.assertTrue(all(item["times"] and item["price"] and item["image"] for item in found))
        self.assertTrue(all("/thumb_" not in item["image"] for item in found))  # The picture, not the thumbnail.

    def test_seetickets_reads_a_venue_site_listing(self):
        found = self.read("seetickets", "https://rickshawstop.com/", "music", "Rickshaw Stop")
        self.assertTrue(all(item["times"] and item["image"] for item in found))
        self.assertTrue(any(item["detail"].startswith("with ") for item in found))
        self.assertTrue(any(item["price"].startswith("$") for item in found))
        self.assertTrue(any(line.startswith("Doors ") for item in found for line in item["about"]))

    def test_bampfa_sorts_its_films_from_its_talks(self):
        found = self.read("bampfa", "https://bampfa.org/calendar", "art", "BAMPFA", sorts_its_own=True)
        self.assertTrue(found)
        # The calendar labels each listing, and a film goes with the films however the source line reads.
        self.assertEqual({item["category"] for item in found} - {"film", "art"}, set())
        self.assertTrue(all(item["times"] and item["link"].startswith("https://bampfa.org/event/") for item in found))
        # The same three months are read, so a listing in two of them is kept once.
        self.assertEqual(len(found), len({(item["title"], item["date"]) for item in found}))

    def test_roxie_reads_its_calendar_and_each_film_once(self):
        found = self.read("roxie", "https://roxie.com/calendar/", "film", "Roxie")
        self.assertTrue(found)
        self.assertTrue(all(item["times"] for item in found))
        self.assertTrue(all(item["link"].startswith("https://roxie.com/film/") for item in found))
        # A film plays for days on end, so its own page — where its picture and what it's about are — is read
        # once, and only for the days still to come, which this sample (September's first days) has none of.
        self.assertEqual({item["image"] for item in found}, {""})

    def test_ticketweb_reads_the_template_that_sets_the_date_out(self):
        # The Independent's rows give the date as 9.18 and the time as "Show: 9:00 PM", where the Middle East's
        # put both in the link's title; the support act is the row's own line.
        found = self.read("ticketweb", "https://www.theindependentsf.com/", "music", "The Independent")
        self.assertEqual(len(found), 2)
        self.assertTrue(all(item["times"] and item["title"] for item in found))
        self.assertTrue(any(item["detail"].startswith("with ") for item in found))

    def test_ticketweb_reads_the_template_that_heads_the_row_with_a_month(self):
        # Bimbo's puts September over 18 by the picture, and the time as "Show: 8:00 pm" in lower case.
        found = self.read("ticketweb", "https://bimbos365club.com/", "music", "Bimbo's 365 Club")
        self.assertEqual(len(found), 2)
        self.assertTrue(all(item["times"] for item in found))
        self.assertTrue(all(item["image"] for item in found))

    def test_tapos_gives_each_day_its_own_times(self):
        # Read as of when the sample was saved: its headings carry no year, and from two months on a September
        # day reads as next year's (test_tapos_day_takes_next_year_months_on), which would split its three days.
        class September(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 9, 15, 12, tzinfo=tz)
        with mock.patch.object(build, "datetime", September):
            found = self.read("tapos", "https://www.internet-ticketing.com/websales/sales/LEXLEX/start", "film")
        coyote = sorted((item["date"], item["times"]) for item in found if item["title"] == "Coyote vs. Acme")
        # Three days, a showing each: the times run on in the page under headings with no end of their own.
        self.assertEqual([(day.month, day.day, times) for day, times in coyote],
                         [(9, 17, [time(18, 45)]), (9, 18, [time(19, 15)]), (9, 19, [time(17, 0)])])
        self.assertEqual(len({day.year for day, _ in coyote}), 1)
        self.assertEqual(found[0]["image"], "https://image.tmdb.org/t/p/w780/vhv7lBWYM0DUuNU2a0V7Rhq21dD.jpg")
        self.assertTrue(any("billboard lawyer" in line for line in found[0]["about"]))
        # A film with no certificate says "Rating N/A" where one would go; that isn't part of its name.
        self.assertIn("National Theatre Live The Misanthrope", [item["title"] for item in found])

    def test_tapos_day_takes_next_year_months_on(self):
        # A day more than two months behind is next year's: January's, read in December. Up to two months behind
        # stays this year's, for a page still showing last week. (The heading's "17th" comes to it as "17".)
        self.assertEqual(build.tapos_day("Friday January 8", date(2026, 12, 20)), date(2027, 1, 8))
        self.assertEqual(build.tapos_day("Friday September 18", date(2026, 11, 17)), date(2026, 9, 18))
        self.assertEqual(build.tapos_day("Thursday September 17", date(2026, 11, 17)), date(2027, 9, 17))
        self.assertIsNone(build.tapos_day("Monday February 30", date(2026, 1, 1)))

    def test_wptheatre_takes_its_films_names_from_the_theatres_own_site(self):
        found = self.read("wptheatre", "https://www.somervilletheatre.com/#CSBSOM", "film", sorts_its_own=True)
        films = {item["title"]: item for item in found if item["category"] == "film"}
        # The ticketing calls it "The Devils"; the theatre's site, which the listing links to, says whose.
        self.assertIn("Ken Russell’s The Devils", films)
        devils = films["Ken Russell’s The Devils"]
        self.assertEqual(devils["link"], "https://www.somervilletheatre.com/production/ken-russells-the-devils/")
        self.assertTrue(devils["image"].startswith("https://www.somervilletheatre.com/"))
        self.assertTrue(devils["about"])
        # "House" is the site's "House (Hausu)", the nearest of its names holding it, not "House on Haunted Hill".
        self.assertIn("House (Hausu) in 35mm", films)
        self.assertNotIn("House", films)

    def test_wptheatre_adds_its_live_shows_and_leaves_out_what_is_already_a_showtime(self):
        found = self.read("wptheatre", "https://www.somervilletheatre.com/#CSBSOM", "film", sorts_its_own=True)
        music = [item for item in found if item["category"] == "music"]
        self.assertIn("Oteil Burbridge with LaMP – Wish Benefit Tour", [item["title"] for item in music])
        self.assertTrue(all("/production/" in item["link"] for item in music))
        # A film with an orchestra is on the events page and in the showtimes; it's listed once, as a film.
        phantom = [item for item in found if "Phantom of the Opera" in item["title"]]
        self.assertEqual([item["category"] for item in phantom], ["film"], phantom)
        self.assertEqual(len(phantom), 1)

    def test_wptheatre_reads_a_theatre_with_only_films_and_no_events_page(self):
        found = self.read("wptheatre", "https://www.capitoltheatreusa.com/#CSBARL", "film", "Capitol Theatre",
                          sorts_its_own=True)
        # The Capitol files its films under "movies" where the Somerville Theatre says "movie"; both are films.
        self.assertEqual({item["category"] for item in found}, {"film"})
        self.assertTrue(all("capitoltheatreusa.com/movie/" in item["link"] for item in found), found[0]["link"])
        self.assertIn("Sense and Sensibility", [item["title"] for item in found])
        self.assertTrue(all(item["image"] and item["about"] for item in found))

    def test_tribe_skips_what_isnt_a_show(self):
        found = self.read("tribe", "https://lizardloungeclub.com/wp-json/tribe/events/v1/events")
        titles = [item["title"] for item in found]
        self.assertEqual(len(titles), 4)
        self.assertIn("The Gravel Project/Lara Cwass", titles)
        self.assertFalse(any("No Event" in title or "Poetry Jam" in title for title in titles))
        self.assertTrue(all(item["times"] for item in found))


class WesternMass(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(build, "fetch", sample)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_mass_moca_by_its_categories(self):
        with mock.patch.object(build, "today", lambda: date(2026, 9, 15)):
            found = build.read_mass_moca(source("massmoca", "https://massmoca.org/wp-json/tribe/events/v1/events", "art", "Mass MoCA"))
        by_title = {item["title"]: item for item in found}
        self.assertEqual(by_title["Madison Cunningham"]["category"], "music")
        self.assertEqual(by_title["Madison Cunningham"]["detail"], "Ace Tour", "its subtitle, out of its name")
        self.assertEqual(by_title["Lucinda Williams and her band"]["detail"], "FreshGrass Presents")
        self.assertEqual((by_title["The Emilys & Daytime Moon"]["category"], by_title["The Emilys & Daytime Moon"]["detail"]),
                         ("art", "Heather Abel & Kerri Schlottman"), "a subtitle span left open")
        self.assertFalse(any("Storytime" in title for title in by_title), "not its events for kids")
        self.assertEqual((by_title["Laurent Grasso"]["date"], by_title["Laurent Grasso"]["detail"]), (date(2026, 11, 7), "Metaphysical Maze"),
                         "an exhibition, on the day it opens")
        self.assertFalse(any("Kubisch" in title for title in by_title), "not one that opened years ago, and runs for years")
        self.assertTrue(by_title["Madison Cunningham"]["price"] and by_title["Madison Cunningham"]["image"])

    def test_tribe_titles(self):
        self.assertEqual(build.tribe_title('Yana &#8211; SOLD OUT!'), ("Yana – SOLD OUT!", ""))
        self.assertEqual(build.tribe_title('Uncomputable Thread <br> <span class="title-light">A Lecture Performance'),
                         ("Uncomputable Thread", "A Lecture Performance"))

    def test_amherst_cinema(self):
        with mock.patch.object(build, "today", lambda: date(2026, 9, 16)):
            found = build.read_amherst_cinema(source("amherstcinema", "https://amherstcinema.org/", "film", "Amherst Cinema"))
        self.assertEqual([item["title"] for item in found], ["Finding Emily", "James McNeill Whistler", "Teenage Sex and Death at Camp Miasma"])
        self.assertEqual(found[0]["times"], [time(16, 40)])
        self.assertEqual(found[1]["detail"], "Exhibition On Screen", "its series")
        self.assertTrue(all(item["link"].startswith("https://amherstcinema.org/films-and-events/") for item in found))
        self.assertTrue(found[0]["image"].startswith("https://amherstcinema.org/sites/default/files/"))
        self.assertTrue(found[0]["about"][0].startswith("When a lovesick musician"), "not its notes for particular days")

    def test_indy_cinemas(self):
        answers = json.loads((FIXTURES / "indy.json").read_text())
        asked = []

        def post(url, body, headers):
            asked.append((url, headers))
            return answers["dates"] if "datesWithShowing" in body["query"] else answers["showings"]
        with mock.patch.object(build, "post_json", post), mock.patch.object(build, "today", lambda: date(2026, 9, 15)):
            found = build.read_indy(source("indy", "https://www.imagescinema.org/?site=57&circuit=49", "film", "Images Cinema"))
        self.assertEqual(asked[0], ("https://www.imagescinema.org/graphql", {"client-type": "consumer", "site-id": "57", "circuit-id": "49"}))
        spider = [item for item in found if item["title"] == "Spider-Man: Brand New Day"]
        self.assertEqual((spider[0]["date"], spider[0]["times"]), (date(2026, 9, 16), [time(15, 30)]), "UTC, as Boston's time")
        self.assertEqual(spider[0]["link"], "https://www.imagescinema.org/movie/spider-man-brand-new-day")
        self.assertTrue(spider[0]["image"].startswith("https://indy-systems.imgix.net/") and spider[0]["about"])
        self.assertFalse(any(item["sold_out"] for item in found))
        answers["showings"]["data"]["showingsForDate"]["data"][0]["seatsRemaining"] = 0
        with mock.patch.object(build, "post_json", post), mock.patch.object(build, "today", lambda: date(2026, 9, 15)):
            found = build.read_indy(source("indy", "https://www.imagescinema.org/?site=57&circuit=49", "film", "Images Cinema"))
        self.assertTrue(found[0]["sold_out"], "no seats left")

    def test_iron_horse_and_parlor_room_from_one_calendar(self):
        url = "https://core.service.elfsight.com/p/boot/?page=https%3A%2F%2Fwww.ironhorse.org%2Fshows&w=c4b76df1-e520-4ed0-9318-f18bd056c38a"
        horse = build.read_elfsight(source("elfsight", url, "music", "Iron Horse"))
        parlor = build.read_elfsight(source("elfsight", url, "music", "Parlor Room"))
        self.assertEqual([item["title"] for item in horse], ["Bettye Lavette", "Sarah Jarosz: 10 Years of Undercurrent"],
                         "its own room's, not the kids' series or the workshop")
        self.assertEqual((horse[0]["date"], horse[0]["times"], horse[0]["price"]), (date(2026, 9, 16), [time(19, 0)], "$50.40"))
        self.assertTrue(horse[0]["link"].startswith("https://theparlorroom.my.salesforce-sites.com/") and horse[0]["image"])
        self.assertTrue(horse[1]["sold_out"])
        self.assertEqual((parlor[0]["title"], parlor[0]["detail"]), ("Trans Joy and Resilience", "with Jessye DeSilva + Hazel Basil"))

    def test_the_drake_and_supporting_acts(self):
        found = build.read_squarespace(source("squarespace", "https://www.thedrakeamherst.org/events", "music", "The Drake"))
        self.assertEqual((found[0]["title"], found[0]["detail"]), ("MINI TREES", "with Frown Line"))
        self.assertEqual(build.with_support("Dylan Earl w/ Olivia Ellen Lloyd"), ("Dylan Earl", "with Olivia Ellen Lloyd"))
        self.assertEqual(build.with_support("An Evening with Bettye LaVette"), ("An Evening with Bettye LaVette", ""), "only w/")

    def test_mahaiwe_by_its_categories(self):
        found = build.read_mahaiwe(source("mahaiwe", "https://www.mahaiwe.org/events/?ical=1", "music", "Mahaiwe"))
        kinds = {item["title"]: item["category"] for item in found}
        self.assertFalse(any("Comedy" in title or "Salsa Class" in title for title in kinds), "not its comedy or dance classes")
        self.assertEqual(kinds["Los Lonely Boys"], "music")
        self.assertEqual(kinds["London’s National Theatre in HD: The Playboy of the Western World"], "film")
        self.assertTrue(any(category == "art" for category in kinds.values()), "its lectures")
        indigo = next(item for item in found if item["title"] == "Nine Days Acoustic")
        self.assertEqual((indigo["venue"], indigo["detail"]), ("Mahaiwe", "Indigo Room"))
        self.assertEqual(indigo["address"][:2], ["20 Castle Street", "Great Barrington"], "next door, at its own address")

    def test_shea_theater(self):
        with mock.patch.object(build, "today", lambda: date(2026, 10, 1)):
            found = build.read_shea(source("shea", "https://sheatheater.org/", "music", "Shea Theater"))
        by_title = {item["title"]: item for item in found}
        self.assertEqual((by_title["Sam Grisman Project"]["date"], by_title["Sam Grisman Project"]["times"]), (date(2026, 10, 2), [time(20, 0)]))
        self.assertEqual(by_title["Sam Grisman Project"]["detail"], "", "Shea Presents: out of its name, and not its detail")
        self.assertTrue(by_title["Sam Grisman Project"]["image"].endswith("/calendar/calendar_23292_large.jpg"))
        self.assertTrue(by_title["Sam Grisman Project"]["about"])
        screening = next(item for item in found if item["title"].startswith("Friday the 13th"))
        self.assertEqual(screening["category"], "film")

    def test_bombyx_its_shows_by_their_pages_names_and_not_its_classes(self):
        with mock.patch.object(build, "today", lambda: date(2026, 11, 24)):
            found = build.read_bombyx(source("bombyx", "https://bombyx.live/events/", "music", "Bombyx"))
        by_title = {item["title"]: item for item in found}
        rush = by_title["An Evening with Tom Rush"]
        self.assertEqual((rush["date"], rush["times"], rush["category"]), (date(2026, 12, 5), [time(19, 0)], "music"),
                         "a singer's evening a concert, not a talk")
        self.assertEqual(rush["detail"], "Accompanied by Matt Nakoa and Brendan Cleary", "the line under its name")
        self.assertEqual(rush["price"], "$35-50")
        self.assertTrue(rush["about"] and rush["image"] and rush["link"] == "https://bombyx.live/events/an-evening-with-tom-rush-2/")
        self.assertEqual(by_title["Rickie Lee Jones"]["category"], "music", "by her name, not her memoir in what's said about her")
        self.assertEqual(by_title["Film Night! “Dreaming of a Jewish Christmas”"]["category"], "film")
        self.assertFalse([title for title in by_title if "5Rhythms" in title], "not its dance classes")
        self.assertEqual(len(found), 3, "only those whose pages give a name")

    def test_marigold_its_easthampton_shows_not_its_jams(self):
        with mock.patch.object(build, "today", lambda: date(2026, 11, 24)):
            found = build.read_marigold(source("marigold", "https://marigold.org/", "music", "Marigold Theater"))
        self.assertEqual(len(found), 1, "the one show sampled; its jam left out, and pages named only Marigold too")
        show = found[0]
        self.assertEqual(show["title"], "Jeff The Brotherhood With Cliffrose & Ian St George")
        self.assertEqual((show["date"], show["times"], show["category"]), (date(2026, 12, 13), [time(20, 0)], "music"),
                         "its day from its tile, its time from its page")
        self.assertEqual(show["price"], "$15")
        self.assertTrue(show["about"] and show["image"].startswith("https://marigold.org/wp-content/uploads/"))

    def test_umass_calendar_its_arts_not_its_clubs_nor_the_fine_arts_centers(self):
        found = build.read_localist(source("localist", "https://events.umass.edu/api/2/events", "music", "UMass Amherst"))
        titles = {item["title"] for item in found}
        moors = [item for item in found if item["title"] == "The Moors"]
        self.assertEqual(len(moors), 6, "each performance of the theater department's play")
        self.assertEqual((moors[0]["category"], moors[0]["detail"], moors[0]["price"]), ("art", "Curtain Theater", "$7–$19"))
        self.assertIn("Faculty Dance Concert - UMass & Amherst College", titles, "marked for the arts, though for no audience")
        self.assertTrue(any(title.startswith("Faculty Concert Series") for title in titles))
        self.assertIn("Artist Talk: Farihah Aliyah Shah", titles, "a talk on the arts")
        self.assertNotIn("Maria Mazzotta", titles, "at the Drake, which the Fine Arts Center's own source has")
        self.assertNotIn("Film Screening with Dining Sustainability", titles, "neither for the public nor about the arts")
        self.assertFalse([title for title in titles if "Dissertation" in title or "Book Club" in title or "Winter Week" in title])

    def test_mount_holyoke_only_whats_for_the_public(self):
        found = build.read_localist(source("localist", "https://events.mtholyoke.edu/api/2/events", "music", "Mount Holyoke"))
        titles = [item["title"] for item in found]
        self.assertIn("Mount Holyoke Symphony Orchestra: Mary Lyon Concert", titles, "an ensemble's concert")
        self.assertEqual(titles.count("Holiday Vespers"), 2)
        self.assertNotIn("DOZ Bible Study", titles, "filed under its concerts, for no audience")
        self.assertFalse([title for title in titles if "Student Recital" in title or "Studio Recital" in title])
        self.assertNotIn("Artist Talk with Kerri Clarke: The Seven Sisters Possum", titles, "online only")

    def test_smith_its_performances_and_readings_not_coursework(self):
        with mock.patch.object(build, "today", lambda: date(2026, 11, 24)):
            found = build.read_smith(source("smith", "https://www.smith.edu/news-events/events", "music", "Smith College"))
        by_title = {item["title"]: item for item in found}
        gamelan = by_title["Central Javanese Gamelan Fall Concert"]
        self.assertEqual((gamelan["date"], gamelan["times"], gamelan["category"]), (date(2026, 12, 2), [time(19, 30)], "music"))
        self.assertTrue(gamelan["link"].startswith("https://www.smith.edu/news-events/events/"))
        self.assertEqual(by_title["Reading by Novelist Megan Giddings"]["category"], "art")
        self.assertEqual(by_title["Reading by Novelist Megan Giddings"]["about"], [], "not its placeholder, xxx")
        self.assertNotIn("Dance at Noon", by_title, "a course's showing")
        self.assertNotIn("Fall Studio Productions", by_title, "student-directed one-acts")
        self.assertNotIn("FMS Screening", by_title, "students' projects")

    def test_smith_start_from_its_hours(self):
        start = lambda hours: build.smith_start(f"Wednesday, December 2, 2026 | {hours}")
        self.assertEqual(start("7:30-9 p.m."), time(19, 30))
        self.assertEqual(start("12:10-1:05 p.m."), time(12, 10))
        self.assertEqual(start("11-1 p.m."), time(11, 0), "eleven in the morning, to end at one")
        self.assertEqual(start("11 a.m.-1 p.m."), time(11, 0))
        self.assertEqual(start("noon-1 p.m."), time(12, 0))

    def test_heavy_culture_from_its_wix_pages_data(self):
        with mock.patch.object(build, "today", lambda: date(2026, 11, 24)):
            found = build.read_wix_events(source("wixevents", "https://www.theheavyculture.coop/shows", "music", "The Heavy Culture"))
        by_title = {item["title"]: item for item in found}
        ice = by_title["Ice Giant / Chained to the Dead / Lurching"]
        self.assertEqual((ice["date"], ice["times"]), (date(2026, 11, 28), [time(19, 0)]), "by its own clock, not UTC's")
        self.assertEqual(ice["link"], "https://www.theheavyculture.coop/event-details/ice-giant-chained-to-the-dead-lurching")
        self.assertTrue(ice["image"].startswith("https://static.wixstatic.com/media/"))
        self.assertIn("Skratch / Glasss / When The Time Comes", by_title, "from the month's grid, past the list's first few")
        self.assertNotIn("Dead Media Market #2", by_title, "not its markets")
        self.assertFalse([item for item in found if item["date"] < date(2026, 11, 24)], "not what's past")
        self.assertEqual(len(found), 11)

    def test_amherst_college_its_concerts_here_not_the_folgers_in_washington(self):
        url = "https://www.amherst.edu/news/events/calendar?f%5B0%5D=type_of_event%3Alec&f%5B1%5D=type_of_event%3Aperform"
        with mock.patch.object(build, "today", lambda: date(2026, 11, 24)):
            found = build.read_amherst(source("amherst", url, "music", "Amherst College"))
        by_title = {item["title"]: item for item in found}
        coleman = by_title["Valerie Coleman & Friends"]
        self.assertEqual((coleman["date"], coleman["times"], coleman["category"], coleman["detail"]),
                         (date(2027, 2, 12), [time(19, 30)], "music", "Buckley Recital Hall"), "M@A Presents: out of its name")
        self.assertTrue(coleman["image"].startswith("https://www.amherst.edu/system/files/") and coleman["about"])
        self.assertTrue(coleman["link"].startswith("https://www.amherst.edu/"))
        self.assertNotIn("Hamlet", by_title, "at the Folger, in Washington")
        self.assertFalse([title for title in by_title if "Salon" in title], "not its weekly salons")
        self.assertNotIn("Artemis", by_title, "at the Drake, whose own calendar has it")
        self.assertEqual(len(found), 2)

    def test_double_edge_its_performances_here_a_night_each(self):
        # Its sample is its real cards, from its past events, under its upcoming heading: it had none upcoming then.
        with mock.patch.object(build, "today", lambda: date(2026, 10, 1)):
            found = build.read_double_edge(source("doubleedge", "https://doubleedgetheatre.org/events/", "art", "Double Edge Theatre"))
        forest = [item for item in found if item["title"] == "Out of the Darkest Forest"]
        self.assertEqual([item["date"] for item in forest], [date(2026, 11, 19), date(2026, 11, 20), date(2026, 11, 21)],
                         "a listing a night, Nov 19 — Nov 21")
        self.assertEqual((forest[0]["times"], forest[0]["category"], forest[0]["detail"]), ([], "art", "The Farm Center"))
        self.assertTrue(forest[0]["link"].startswith("https://doubleedgetheatre.org/eventos/") and forest[0]["image"])
        evening = next(item for item in found if item["detail"] == "Shea Theater Arts Center")
        self.assertEqual(evening["address"][1], "Turners Falls", "at the Shea, at its address")
        titles = {item["title"] for item in found}
        self.assertNotIn("Fall Community Day", titles, "not its community days")
        self.assertNotIn("Fall 2026 Open Training", titles, "nor its trainings")
        self.assertFalse([item for item in found if "Lenfest" in item["detail"]], "nor where it tours")

    def test_pothole_pictures_a_night_each_with_its_music(self):
        with mock.patch.object(build, "today", lambda: date(2026, 11, 24)):
            found = build.read_memorial_hall(source("memorialhall", "https://shelburnefallsmemorialhall.org/pothole-pictures/", "film", "Pothole Pictures"))
        wonderful = [item for item in found if item["title"] == "It’s a Wonderful Life (1946)"]
        self.assertEqual([(item["date"], item["times"]) for item in wonderful], [(date(2026, 12, 18), [time(19, 30)]), (date(2026, 12, 19), [time(19, 30)])],
                         "a listing a night, its time from its own page where the list doesn't say")
        self.assertTrue(wonderful[0]["about"][0].startswith("Free live music at 7 pm"), "the music before it")
        self.assertTrue(wonderful[0]["image"].startswith("https://") and "?" not in wonderful[0]["image"], "its picture, whole")
        conformist = next(item for item in found if item["title"] == "The Conformist (1970)")
        self.assertEqual((conformist["date"], conformist["times"]), (date(2027, 1, 22), [time(19, 30)]), "next year's, by its own year")
        titles = {item["title"] for item in found}
        self.assertNotIn("Community Open Meeting", titles)
        self.assertNotIn("Sherlock, Jr. (1924)", titles, "not what's past")

    def test_memorial_halls_met_opera_by_its_posts_dates_not_its_titles(self):
        with mock.patch.object(build, "today", lambda: date(2026, 11, 24)):
            found = build.read_memorial_hall(source("memorialhall", "https://shelburnefallsmemorialhall.org/metropolitan-operas/",
                                                    "music", "Shelburne Falls Memorial Hall"))
        by_title = {item["title"]: item for item in found}
        samson = by_title["Samson et Dalila: Saint-Saëns"]
        self.assertEqual((samson["date"], samson["times"]), (date(2026, 12, 5), [time(13, 0)]),
                         "its post's Saturday, December 5, not its title's 12/6/2026, which is out of its name")
        self.assertEqual((samson["category"], samson["detail"]), ("music", "Met Opera Live in HD"))
        self.assertEqual(by_title["Manon: Massenet"]["times"], [time(12, 0)], "at 12PM")
        self.assertEqual(by_title["Parsifal — Richard Wagner"]["date"], date(2027, 6, 5), "its next June 5, with no year said")
        self.assertNotIn("Macbeth: Verdi", by_title, "not what's past")

    def test_tanglewood_from_the_bsos_search_only_whats_in_lenox(self):
        answer = json.loads((FIXTURES / "bso_search.json").read_text())
        asked = []
        post = lambda url, body, headers=None: asked.append((url, body)) or answer
        with mock.patch.object(build, "post_json", post), mock.patch.object(build, "today", lambda: date(2026, 11, 24)):
            found = build.read_tanglewood(source("tanglewood", "https://www.bso.org/tanglewood", "music", "Tanglewood"))
        self.assertEqual(asked[0][1]["filters"], 'section:"Upcoming Events"', "only what's upcoming, from its search")
        self.assertEqual(len(found), 1, "Tanglewood's, not Symphony Hall's Messiah, nor its photography class")
        jazz = found[0]
        self.assertTrue(jazz["title"].startswith("TLI Jazz: Ted Rosenthal Quartet"))
        self.assertEqual((jazz["date"], jazz["times"], jazz["category"]), (date(2026, 11, 27), [time(19, 0)], "music"))
        self.assertEqual(jazz["detail"], "Studio E, Linde Center for Music and Learning", "its hall, without its town")
        self.assertEqual(jazz["address"][1], "Lenox")
        self.assertTrue(jazz["about"] and jazz["image"].startswith("https://cdn.bso.org/"))

    def test_symphony_hall_springfield_without_its_comedian(self):
        with mock.patch.object(build, "today", lambda: date(2026, 11, 25)):
            found = build.read_eventitems(source("eventitems", "https://www.symphonyhallspringfield.com/events", "music", "Symphony Hall Springfield"))
        by_title = {item["title"]: item for item in found}
        jazz = by_title["Jazz Up the Holidays"]
        self.assertEqual((jazz["date"], jazz["times"], jazz["category"]), (date(2026, 12, 12), [time(16, 0)], "music"))
        self.assertEqual(jazz["detail"], "Presented by the Springfield Symphony Orchestra", "the line under its name")
        self.assertEqual(by_title["Favorite Choral Works"]["date"], date(2027, 4, 17), "next year's, with no year said")
        self.assertEqual(by_title["Swan Lake"]["category"], "art", "a ballet, by its presenters, International Ballet Stars")
        self.assertNotIn("Jeff Dunham Inappropriate Contact", by_title, "a comedian, by his own page")
        self.assertTrue(jazz["link"].startswith("https://www.symphonyhallspringfield.com/events/detail/") and jazz["image"])

    def test_52_sumner_from_its_table(self):
        found = build.read_sumner(source("sumner", "https://52sumner.com/events-and-tickets/", "music", "52 Sumner"))
        by_title = {item["title"]: item for item in found}
        hambridge = by_title["Tom Hambridge - Blue 52 Series"]
        self.assertEqual((hambridge["date"], hambridge["times"], hambridge["category"]), (date(2026, 12, 4), [], "music"))
        self.assertTrue(hambridge["link"].startswith("https://www.eventbrite.com/e/") and "?" not in hambridge["link"],
                        "where its tickets are, without what's added for counting visitors")
        carol = by_title["Creepy Christmas Carol"]
        self.assertEqual((carol["category"], carol["detail"]), ("art", "Produced by FEVER"), "a play, its producer its line")
        self.assertIn("Springfield Symphony Chamber Players", by_title, "without its note that tickets are coming")
        self.assertFalse([title for title in by_title if re.search(r"private|chamber event", title, re.I)],
                         "not its private bookings or the Chamber of Commerce's mixers")

    def test_hope_center_from_its_upcoming_page_and_each_shows(self):
        with mock.patch.object(build, "today", lambda: date(2026, 11, 25)):
            found = build.read_hope(source("hope", "https://hopecenterforthearts.org/upcoming/", "music", "HOPE Center for the Arts"))
        by_title = {item["title"]: item for item in found}
        tenors = by_title["The Irish Tenors"]
        self.assertEqual((tenors["date"], tenors["times"], tenors["price"]), (date(2026, 12, 4), [time(19, 0)], "$65–$90"),
                         "when the show starts, not when the lobby opens")
        self.assertTrue(tenors["about"] and tenors["image"])
        self.assertEqual(by_title["CCM: A Night of Worship"]["date"], date(2026, 11, 28), "its day from its card, its page aside")

    def test_de_la_luz_by_its_months_not_its_weekly_series(self):
        found = build.read_delaluz(source("delaluz", "https://delaluz.org/calendar", "music", "De La Luz"))
        by_title = {item["title"]: item for item in found}
        lopez = by_title["Harold López-Nussa"]
        self.assertEqual((lopez["date"], lopez["times"], lopez["detail"], lopez["price"]),
                         (date(2027, 1, 16), [time(19, 0)], "Soundstage", "$38.50"))
        self.assertEqual(lopez["link"], "https://delaluz.org/events/harold-lopez-nussa")
        self.assertEqual(by_title["The Interlude"]["about"], ["Thanksgiving has an afterparty"], "the line under its name")
        self.assertNotIn("Armour Yard", by_title, "not its weekly vinyl nights")

    def test_hutghis_shows_from_its_shop(self):
        with mock.patch.object(build, "today", lambda: date(2026, 11, 25)):
            found = build.read_shopify(source("shopify", "https://m3pn87-t7.myshopify.com/products.json?limit=250", "music", "Hutghi's at the Nook"))
        by_title = {item["title"]: item for item in found}
        ska = by_title["Mephiskapheles / Skarmy of Darkness / Soularites / Mega Infinity"]
        self.assertEqual((ska["date"], ska["times"], ska["price"]), (date(2027, 3, 13), [time(19, 0)], "$16.66"),
                         "its day from its name, its time from what it says")
        self.assertEqual(ska["link"], "https://m3pn87-t7.myshopify.com/products/saturday-march-13th-mephiskapheles-skarmy-of-darkness-soularites-mega-infinity")
        self.assertEqual(by_title["Jeanines, Now, Time Thief"]["date"], date(2026, 11, 18), "a day said 11/18")
        self.assertFalse([title for title in by_title if re.search(r"shirt|every|trivia", title, re.I)],
                         "not its shirts, nor its weekly comedy and trivia")

    def test_noho_arts_events_from_its_page_list(self):
        with mock.patch.object(build, "today", lambda: date(2026, 11, 25)):
            found = build.read_squarespace_list(source("squarespacelist", "https://www.nohoarts.org/upcoming-events", "music",
                                                       "Northampton Center for the Arts"))
        by_title = {item["title"]: item for item in found}
        jazz = by_title["Pioneer Valley Jazz Shares: Tropos"]
        self.assertEqual((jazz["date"], jazz["times"], jazz["price"], jazz["category"]),
                         (date(2027, 1, 21), [time(19, 30)], "$20", "music"), "its year as it says it, its start of 7:30-9:30 PM")
        self.assertEqual(jazz["link"], "https://www.nohoarts.org/tropos", "its Learn more page")
        self.assertTrue(jazz["image"].startswith("https://images.squarespace-cdn.com/"))
        self.assertEqual(by_title["Slow Burn Speakeasy"]["times"], [time(20, 0)])
        self.assertEqual(by_title["30 Poems in November Reading & Celebration"]["category"], "art")
        self.assertEqual(by_title["30 Poems in November Reading & Celebration"]["price"], "Free")
        night = by_title["Arts Night Out at 33"]
        self.assertEqual((night["date"], night["times"], night["category"]), (date(2026, 12, 11), [time(17, 0)], "art"),
                         "a monthly one by its next date, a gallery night as art")
        self.assertFalse([title for title in by_title if re.search(r"fair|market|meeting|prom\b|tank|passion", title, re.I)],
                         "not its fairs, markets, meetings, prom, discussion group or dance social")

    def test_latchis_stage_shows_not_its_new_releases_runs(self):
        found = build.read_latchis(source("latchis", "https://latchis.com/wp-json/tribe/events/v1/events", "music", "Latchis Theatre"))
        by_title = {item["title"]: item for item in found}
        self.assertIn("Joel Veena: Ragas & Sagas", by_title)
        self.assertEqual(by_title["Joel Veena: Ragas & Sagas"]["times"], [time(19, 0)])
        self.assertFalse([title for title in by_title if "Opens" in title], "not a new release's first day")

    def test_brattleboro_music_center_concerts_not_its_workshops(self):
        found = build.read_bmc(source("bmc", "https://www.bmcvt.org/wp-json/tribe/events/v1/events?categories=special-events",
                                      "music", "Brattleboro Music Center"))
        titles = {item["title"] for item in found}
        self.assertIn("Palaver Strings: What Travels", titles)
        self.assertFalse([title for title in titles if re.search(r"workshop|pub session|ballad sing", title, re.I)])

    def test_brattleboro_museum_talks_not_its_calls_or_workshops(self):
        found = build.read_bmac(source("bmac", "https://www.brattleboromuseum.org/wp-json/tribe/events/v1/events", "art",
                                       "Brattleboro Museum & Art Center"))
        titles = {item["title"] for item in found}
        self.assertIn("Art Talk: Amy Beecher on Glotech Cantata", titles)
        self.assertFalse([title for title in titles if re.search(r"call for entries|workshop|model railroad|feast", title, re.I)])

    def test_epsilon_spires_films_with_bands_and_their_own_links(self):
        with mock.patch.object(build, "today", lambda: date(2026, 11, 25)):
            found = build.read_wix_events(source("wixevents", "https://www.epsilonspires.org/upcoming-events", "music", "Epsilon Spires"))
        by_title = {item["title"]: item for item in found}
        hausu = by_title["HAUSU (1977) + Gift Horse!"]
        self.assertEqual(hausu["category"], "film", "a film by the year in its name, though a band plays")
        self.assertEqual(hausu["link"], "https://www.epsilonspires.org/event-info/hausu-1977-gift-horse", "its pages where its links say")
        self.assertNotIn("Fellini SATYRICON (1969)", by_title, "not one with no date yet")
        self.assertEqual(by_title["ETERNAL RETURNS PRESENTS... EARTH II + Filmmaker Q&A!"]["category"], "film", "a filmmaker's Q&A's")

    def test_dsp_shows_venue_pages_by_their_events_data(self):
        found = build.read_jsonld(source("jsonld", "https://dspshows.com/venues/bombyx/", "music", "Bombyx"))
        titles = {item["title"] for item in found}
        self.assertIn("Rickie Lee Jones", titles)
        self.assertTrue(any(title.startswith("A St. Patrick's Day Celebration") for title in titles), "its apostrophes unescaped")

    def test_barrington_hall_from_its_ticket_tailor_box_office(self):
        found = build.read_tickettailor(source("tickettailor", "https://live.barringtonhallgb.com/", "music", "Barrington Hall"))
        by_title = {item["title"]: item for item in found}
        howie = by_title["Howie Day"]
        self.assertEqual((howie["date"], howie["times"], howie["category"]), (date(2026, 12, 5), [time(20, 0)], "music"),
                         "from \"Sat Dec 5 , 2026 8:00 PM\", its parts run together")
        self.assertTrue(howie["link"].startswith("https://live.barringtonhallgb.com/events/barringtonhall/") and howie["image"])
        self.assertEqual(len(found), 4)

    def test_the_foundry_by_the_day_it_shows_once_each_not_its_craft_nights(self):
        found = build.read_foundry(source("foundry", "https://thefoundryws.com/event/", "music", "The Foundry"))
        by_title = {item["title"]: item for item in found}
        self.assertEqual((by_title["The Kwintet"]["date"], by_title["The Kwintet"]["times"]), (date(2026, 12, 5), [time(19, 30)]),
                         "the day it shows, Sat, Dec 5, not the day early it gives machines")
        self.assertEqual(len(found), len(by_title), "each once, though its next page is its first again")
        self.assertNotIn("SALA: Holiday Ornament Craft Night!", by_title, "not its craft nights")
        self.assertTrue(by_title["The Kwintet"]["about"] and by_title["The Kwintet"]["link"].startswith("https://thefoundryws.com/event/"))

    def test_tower_theaters_from_abenity_linked_to_its_own_site(self):
        with mock.patch.object(build, "today", lambda: date(2026, 11, 24)):
            found = build.read_abenity(source("abenity", "https://m.movies.abenity.com/theatre?id=725#https://www.towertheaters.com/",
                                              "film", "Tower Theaters"))
        by_title = {item["title"]: item for item in found}
        self.assertEqual(set(by_title), {"The Hunger Games: Sunrise on the Reaping", "Ebenezer"}, "without their ratings")
        ebenezer = by_title["Ebenezer"]
        self.assertEqual((ebenezer["date"], ebenezer["times"]), (date(2026, 11, 24), [time(10, 0), time(13, 0), time(15, 45), time(18, 15)]))
        self.assertTrue(all(item["link"] == "https://www.towertheaters.com/" for item in found), "the theater's own site, from its line")
        self.assertTrue(ebenezer["image"] and ebenezer["about"][0].startswith("This November"))
        self.assertEqual(ebenezer["about"][-1], "1 hr. 56 mins")
        with self.assertRaises(ValueError, msg="a line without its own site fails, rather than link to Abenity"):
            build.read_abenity(source("abenity", "https://m.movies.abenity.com/theatre?id=725", "film", "Tower Theaters"))
        sources = build.read_sources(WESTERN_MASS_SOURCES, "westernma")
        self.assertTrue(all(re.search(r"#https?://", s["url"]) and "abenity" not in s["url"].split("#")[1]
                            for s in sources if s["kind"] == "abenity"), "every Abenity line gives its cinema's own site")

    def test_cityspace_from_venuepilot(self):
        answer = json.loads((FIXTURES / "venuepilot.json").read_text())
        asked = []
        post = lambda url, body, headers=None: asked.append(body["variables"]) or answer
        with mock.patch.object(build, "post_json", post), mock.patch.object(build, "today", lambda: date(2026, 11, 24)):
            found = build.read_venuepilot(source("venuepilot", "https://www.cityspaceeasthampton.org/all-events/#924", "music", "CitySpace"))
        self.assertEqual(asked[0]["accountIds"], [924], "its account, from after the # in its line")
        by_title = {}
        for item in found:
            by_title.setdefault(item["title"], item)
        mind = by_title["Mind Left Body"]
        self.assertEqual((mind["date"], mind["times"], mind["category"]), (date(2026, 11, 28), [time(20, 0)], "music"),
                         "its show's time, not its doors'; CitySpace Presents: out of its name")
        self.assertEqual((mind["detail"], mind["ages"]), ("Back on the Bus at CitySpace", "21+"))
        self.assertTrue(mind["link"].startswith("https://tickets.venuepilot.com/") and mind["image"] and mind["about"])
        self.assertEqual(by_title["Haley Kean - Passive Forms"]["category"], "art", "an exhibition's reception")
        self.assertEqual(by_title["Haley Kean - Passive Forms"]["price"], "Free")
        self.assertEqual(by_title["Scott Hsu Album Release Show"]["category"], "music", "a singer who plays isn't a play")
        self.assertEqual(by_title["Foes of a Minimum Wage Guard"]["category"], "art", "a comedy-drama play, by its name not comedy")
        self.assertEqual(by_title["Gogol Dreams of Gogol Dreaming"]["category"], "art", "puppetry")
        screening = next(item for title, item in by_title.items() if title.startswith("Second Nature: Documentary Screening"))
        self.assertEqual(screening["category"], "film")
        self.assertNotIn("Tour of Old Town Hall", by_title)
        self.assertNotIn("Tiny Pop-Up Market", by_title)

    def test_garden_cinemas_a_day_to_a_page(self):
        with mock.patch.object(build, "today", lambda: date(2026, 11, 24)):
            found = build.read_garden_cinemas(source("gardencinemas", "https://www.gardencinemas.net/", "film", "Garden Cinemas"))
        by_title = {item["title"]: item for item in found}
        self.assertEqual(len(found), 10, "the day sampled; the others' pages are empty")
        self.assertEqual((by_title["Hexed"]["date"], by_title["Hexed"]["times"]), (date(2026, 11, 24), [time(15, 30), time(18, 0), time(20, 30)]),
                         "its 3D showing and its others together")
        self.assertEqual(by_title["Hexed"]["link"], "https://www.gardencinemas.net/movie/Hexed")
        self.assertTrue(by_title["Hexed"]["image"].startswith("https://img.cnmhstng.com/"))

    def test_academy_of_music(self):
        with mock.patch.object(build, "today", lambda: date(2026, 9, 15)):
            found = build.read_academy_of_music(source("academyofmusic", "https://aomtheatre.com/event-calendar/", "music", "Academy of Music"))
        self.assertEqual(found[0]["title"], "World Ballet Company: Swan Lake")
        self.assertEqual((found[0]["date"], found[0]["times"]), (date(2026, 9, 18), [time(19, 0)]))
        self.assertEqual(found[0]["detail"], "Gorskaya-Hartwick Productions presents")
        self.assertTrue(all(item["image"] and item["about"] for item in found))

    def test_kinds_guessed(self):
        for name, described, kind in [("Ivy League of Comedy Tour", "", None), ("Gary Gulman", "The comedian returns", None),
                                      ("Friday the 13th Part VII Screening", "", "film"), ("World Ballet Company: Swan Lake", "", "art"),
                                      ("An Evening with David Sedaris", "", "art"), ("Randy Travis", "his co-star in independent film The Price", "music"),
                                      ("Deadgrass", "A Grateful Dead tribute", "music")]:
            self.assertEqual(build.guess_kind(name, described), kind, name)
        self.assertEqual(build.presented("DSP Shows Presents: Beth Orton", "Shea"), ("Beth Orton", "DSP Shows presents"))
        self.assertEqual(build.presented("Shea Presents: Upstate", "Shea"), ("Upstate", ""))

    def test_beacon_cinema(self):
        with mock.patch.object(build, "today", lambda: date(2026, 9, 18)):
            found = build.read_phoenix(source("phoenix", "https://www.phoenixmovies.net/theatres/beacon-cinema/005", "film", "Beacon Cinema"))
        films = build.merge_showings(found)
        self.assertEqual(len(films), 2)
        self.assertTrue(all(len(film["times"]) > 1 for film in films))
        self.assertTrue(films[0]["link"].startswith("https://www.phoenixmovies.net/movies/"))
        self.assertTrue(films[0]["image"].startswith("https://ticketing.phoenixmovies.net/CDN/media/entity/get/FilmBackdrop/f-"), "its wide picture")
        self.assertEqual(build.phoenix_image({"Poster_ID": "HO1"}), "https://ticketing.phoenixmovies.net/CDN/media/entity/get/FilmPosterGraphic/"
                         "f-HO1?height=1000&width=600&referenceScheme=Global&allowPlaceHolder=true", "its poster, without a backdrop")

    def test_colonial_theatre(self):
        with mock.patch.object(build, "today", lambda: date(2026, 9, 15)):
            found = build.read_spektrix(source("spektrix", "https://www.berkshiretheatregroup.org/calendar/?spektrix=berkshiretheatregroup",
                                               "music", "Colonial Theatre"))
        titles = {item["title"] for item in found}
        self.assertIn("Klezmer by Candlelight", titles)
        self.assertNotIn("Summer, 1976", titles, "the Unicorn's, not the Colonial's")
        self.assertFalse(any("Comedy" in title for title in titles))
        klezmer = next(item for item in found if item["title"] == "Klezmer by Candlelight")
        self.assertTrue(klezmer["detail"].startswith("featuring"), "the line after its name")
        self.assertEqual(klezmer["link"], "https://www.berkshiretheatregroup.org/event/klezmer-by-candlelight/")

    def test_umass_fine_arts_center(self):
        with mock.patch.object(build, "today", lambda: date(2026, 9, 15)):
            found = build.read_umass_fac(source("umassfac", "https://arts.umass.edu/performing-arts/events", "music", "UMass Fine Arts Center"))
        self.assertEqual((found[0]["title"], found[0]["date"], found[0]["times"]), ("The Carpenters Songbook", date(2026, 9, 25), [time(19, 30)]))
        self.assertEqual(found[0]["detail"], "Frederick C. Tillis Performance Hall", "its hall")
        self.assertEqual(found[0]["address"][1], "Amherst", "the Fine Arts Center's, so it's under Amherst in the venue menu")
        drake = next(item for item in found if item["detail"] == "The Drake")
        self.assertEqual(list(drake["address"]), list(build.VENUE_ADDRESSES["The Drake"]), "a show at the Drake at the Drake's address")
        self.assertTrue(found[0]["link"].startswith("https://arts.umass.edu/performing-arts/events/"))
        self.assertTrue(all(item["image"] for item in found))

    def test_every_source_readable_and_placed(self):
        sources = build.read_sources(WESTERN_MASS_SOURCES, "westernma")
        self.assertEqual({s["name"] for s in sources}, {"Mass MoCA", "Amherst Cinema", "Images Cinema", "Triplex Cinema",
                                                       "Iron Horse", "Parlor Room", "The Drake", "Mahaiwe", "Shea Theater",
                                                       "Academy of Music", "Beacon Cinema", "Colonial Theatre", "UMass Fine Arts Center",
                                                       "Calvin Theatre", "Bombyx", "Marigold Theater",
                                                       "UMass Amherst", "Mount Holyoke", "Smith College", "The Heavy Culture", "CitySpace", "New City Brewery",
                                                       "Amherst College", "Tower Theaters", "Agawam Cinemas", "Double Edge Theatre",
                                                       "Garden Cinemas", "Pothole Pictures",
                                                       "Shelburne Falls Memorial Hall", "Barrington Hall", "The Foundry", "Dreamaway Lodge",
                                                       "Tanglewood", "Pines Theater", "Tree House Brewing",
                                                       "Symphony Hall Springfield", "52 Sumner", "HOPE Center for the Arts",
                                                       "De La Luz", "Hutghi's at the Nook", "Visions Video",
                                                       "Northampton Center for the Arts", "Stone Church",
                                                       "Vermont Jazz Center", "Latchis Theatre", "Epsilon Spires", "Brattleboro Museum & Art Center", "Next Stage Arts"})
        for s in sources:
            self.assertIn(s["kind"], build.READERS)
            self.assertIn(s["name"], build.VENUE_ADDRESSES, "each under its town in the venue menu")
            self.assertEqual(s["city"], "westernma")


WESTERN_MASS_SOURCES = build.ROOT / "sources-westernma.txt"


class Cities(unittest.TestCase):
    def tearDown(self):
        build.use_city(build.BOSTON_CITY)

    def test_city_switcher_in_the_header_to_the_same_page_elsewhere(self):
        build.use_city(build.WESTERN_MASS)
        switcher = build.city_switcher("film/")
        self.assertIn('<summary aria-label="City: Western Mass. Choose another">Western Mass', switcher)
        self.assertIn('<a href="/film/">Boston</a>', switcher, "Boston's films, at the root")
        self.assertIn('<a href="/westernma/film/" aria-current="true">Western Mass</a>', switcher)
        self.assertIn('<a href="/nyc/film/">NYC</a>', switcher)
        self.assertIn('<a href="/cities/">All cities</a>', switcher)
        self.assertIn('<a href="/nyc/">NYC</a>', build.city_switcher("venue/somewhere/"), "a page not every city has: its home")
        self.assertIn('<a href="/nyc/weekend/next/">NYC</a>', build.city_switcher("weekend/next/"))
        page = build.public_page("about/", "About", "<p>Hi</p>")
        self.assertIn('<details class="city-switch">', page.split("</header>")[0], "in the header")

    def test_each_city_its_own_site(self):
        self.assertEqual([city.slug for city in build.CITIES], ["boston", "westernma", "nyc"])
        self.assertEqual(build.BOSTON_CITY.sources, build.SOURCES_FILE)
        build.use_city(build.WESTERN_MASS)
        self.assertEqual((build.PUBLIC_URL, build.PUBLIC_ROOT, build.PUBLIC_NAME), ("https://pushpin.city/westernma/", "/westernma/", "Pushpin Western Mass"))
        images = dict(source("indy", "x", "film", "Images Cinema"), public=True)
        page = build.render_index([build.event(images, "Tony", date(2026, 9, 15), time(19, 0))], [images], [], [],
                                  datetime(2026, 9, 15, tzinfo=timezone.utc), public=True)
        self.assertIn("<title>Pushpin Western Mass · Concerts, films and talks in Western Mass</title>", page)
        self.assertIn("the Pioneer Valley and the Berkshires", page)
        self.assertIn('href="/westernma/film/"', page)
        self.assertIn('<a href="/cities/">All cities</a>', page)
        # Just Pushpin in the header; the line under it says where.
        self.assertIn(f'aria-current="page">{build.WORDMARK}</a>', page)
        self.assertIn('aria-label="Pushpin"', build.WORDMARK, "read as the name, not as Pushp-dotless-i-n")
        self.assertNotIn('<span class="city">', page)
        self.assertIn('<h1 class="tagline">Concerts, films, and talks around Western Mass.</h1>', page)
        about = build.render_about([images], datetime(2026, 9, 15, tzinfo=timezone.utc))
        self.assertIn("Who makes this?", about)
        self.assertIn("I grew up in Western Mass", about)
        self.assertNotIn("I live in Somerville", about)
        self.assertIn("venues across the Pioneer Valley and the Berkshires", about)
        build.use_city(build.BOSTON_CITY)
        self.assertEqual(build.PUBLIC_URL, "https://pushpin.city/", "Boston's at the root")
        self.assertEqual(build.CITY_DIR, build.PUBLIC_DIR)

    def test_sources_by_city(self):
        sinclair, images = source("axs", "x", "music", "The Sinclair"), source("indy", "y", "film", "Images Cinema")
        sinclair["city"], images["city"] = "boston", "westernma"
        items = [build.event(sinclair, "A", date(2026, 9, 15)), build.event(images, "B", date(2026, 9, 15))]
        events, sources, failed, stale = build.by_city(build.WESTERN_MASS, items, [sinclair, images], ["The Sinclair", "Images Cinema"], [])
        self.assertEqual(([item["title"] for item in events], [s["name"] for s in sources], failed), (["B"], ["Images Cinema"], ["Images Cinema"]))

    def test_the_sites_own_pages(self):
        home = build.render_cities(build.CITIES)
        self.assertIn('<a href="/">Boston</a>', home)
        self.assertIn('<link rel="canonical" href="https://pushpin.city/cities/">', home)
        self.assertIn('<a href="/westernma/">Western Mass</a>', home)
        self.assertIn("share/site/home.png", home, "its own card, not Boston's, which is at share/ now")
        self.assertIn("<h2>Massachusetts</h2>", home, "its cities under the state they're in")
        self.assertIn('<h2>New York</h2>\n<ul><li><a href="/nyc/">NYC</a><p>Brooklyn, Manhattan, and Queens</p></li>', home)
        self.assertNotIn('class="soon"', home, "nothing being worked on right now")
        self.assertIn('<a href="/contact/">Let us know</a>', home, "a way to ask for another")
        contact = build.render_contact()
        self.assertIn("https://formsubmit.co/", contact)
        self.assertIn('value="Pushpin: a message"', contact, "one form for every city")
        self.assertIn('value="https://pushpin.city/contact/?sent"', contact)
        missing = build.render_not_found(build.CITIES, build.RETIRED)
        self.assertIn('["westernma", "nyc"]', missing, "Boston's pages are at the root, in no folder")
        self.assertIn('/^\\/boston(\\/|$)/.test(path)', missing, "addresses from when Boston's were under /boston/")
        self.assertIn('(moved ? "/" + rest : home)', missing, "go to the same page at the root")

    def test_a_retired_city_says_so_rather_than_becoming_boston(self):
        """Pushpin Bay Area's addresses are still in bookmarks and search results. Without a word about them,
        the 404 page would take /bayarea/film/ for an address from before there were cities and send it on to
        Boston's — a reader in San Francisco looking at Cambridge's showtimes."""
        self.assertNotIn("bayarea", [city.slug for city in build.CITIES])
        self.assertIn("bayarea", build.RETIRED)
        missing = build.render_not_found(build.CITIES, build.RETIRED)
        self.assertIn('["bayarea"].find(', missing)
        self.assertIn('if (gone) location.replace("/" + gone + "/");', missing)
        self.assertLess(missing.index("if (gone)"), missing.index("const moved"), "before Boston gets it")
        page = build.render_retired("bayarea", "Pushpin Bay Area", build.CITIES)
        self.assertIn("Pushpin Bay Area isn’t updated any more", page)
        self.assertIn('<a href="/">Boston</a>, <a href="/westernma/">Western Mass</a> and <a href="/nyc/">NYC</a>', page)
        self.assertIn('<a class="home" href="/cities/">All cities →</a>', page)
        self.assertIn('<link rel="canonical" href="https://pushpin.city/bayarea/">', page)
        self.assertIn('<meta name="robots" content="noindex">', page, "for search results to forget it")
        # And the site's own list of cities doesn't name it.
        self.assertNotIn("Bay Area", build.render_cities(build.CITIES))


class Archive(unittest.TestCase):
    def test_a_days_listings_kept_once_their_facts_alone(self):
        import gzip
        import tempfile
        from events import archive
        listings = {"built": "2026-11-25T04:30:00+00:00",  # 11:30pm on the 24th, by Boston's clock.
                    "first_seen": {"2026-12-16-rickie-lee-jones-bombyx": "2026-11-20"},
                    "sources": {"Bombyx": {"events": [
                        {"title": "Rickie Lee Jones", "date": "2026-12-16", "times": ["18:30"], "category": "music",
                         "venue": "Bombyx", "detail": "", "price": "$50-65", "sold_out": False, "sold_out_times": [],
                         "link": "https://bombyx.live/events/rickie-lee-jones-2/", "about": ["Her own words."],
                         "image": "https://bombyx.live/a.jpg", "added": "2026-11-21"}]}}}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "listings.json"
            path.write_text(json.dumps(listings))
            kept = Path(folder) / "kept"
            self.assertTrue(archive.write(path, kept))
            self.assertFalse(archive.write(path, kept), "once a day; a later build that day leaves it be")
            day = kept / "2026" / "11" / "24.jsonl.gz"
            self.assertTrue(day.exists(), "by Boston's day, not the server's")
            record = json.loads(gzip.decompress(day.read_bytes()).decode().splitlines()[0])
        self.assertEqual((record["city"], record["title"], record["first_seen"]), ("westernma", "Rickie Lee Jones", "2026-11-20"))
        self.assertNotIn("about", record, "not the venue's words")
        self.assertNotIn("image", record, "nor its picture")


class Skipping(unittest.TestCase):
    def test_whole_words_in_any_case(self):
        with mock.patch.object(build, "SKIP_FILE", FIXTURES.parent.parent / "fixtures" / "events" / "skip.txt"):
            skip = build.skipping()
        for title in ["IMPROV COMEDY: an evening of", "Comedy night", "Strummerville Ukulele Club"]:
            self.assertTrue(skip.search(title), title)
        for title in ["A Comedic Evening", "Ukulele Clubhouse Orchestra", "Armand Hammer"]:
            self.assertFalse(skip.search(title), title)

    def test_nothing_to_skip(self):
        with mock.patch.object(build, "SKIP_FILE", FIXTURES / "no-such-file.txt"):
            self.assertIsNone(build.skipping())


class Calendars(unittest.TestCase):
    def test_a_feed_one_event_per_listing_in_utc(self):
        sinclair = dict(source("axs", "x", "music", "The Sinclair"), public=True)
        show = build.event(sinclair, "Chanel Beads; a show, live", date(2026, 9, 13), time(20, 0), link="https://example.com/1",
                           detail="with Horse Vision", about=["Doors at seven " * 10])
        show["times"].append(time(22, 0))
        untimed = build.event(sinclair, "An Exhibition", date(2026, 9, 14), link="https://example.com/2")
        feed = build.render_calendar("Pushpin Boston · The Sinclair", "What's on", [untimed, show], datetime(2026, 9, 13, tzinfo=timezone.utc))
        self.assertTrue(feed.startswith("BEGIN:VCALENDAR\r\n") and feed.endswith("END:VCALENDAR\r\n"))
        self.assertNotIn("\n", feed.replace("\r\n", ""), "every line ends CRLF")
        self.assertTrue(all(len(line.encode()) <= 75 for line in feed.split("\r\n")), "folded at 75 bytes")
        self.assertEqual(feed.count("BEGIN:VEVENT"), 2, "one event a listing, however many times it has")
        self.assertIn("DTSTART:20260914T000000Z", feed, "8pm in Boston, in UTC")
        self.assertIn("DTSTART;VALUE=DATE:20260914", feed, "all day, without a time")
        unfolded = feed.replace("\r\n ", "")
        self.assertIn("SUMMARY:Chanel Beads\\; a show\\, live", unfolded)
        self.assertIn("Times: 8pm\\, 10pm", unfolded)
        self.assertIn("LOCATION:The Sinclair\\, 52 Church St\\, Cambridge\\, MA 02138", unfolded)
        uid = re.findall(r"UID:(\S+)", unfolded)
        again = build.render_calendar("x", "y", [untimed, show], datetime(2026, 9, 14, tzinfo=timezone.utc))
        self.assertEqual(uid, re.findall(r"UID:(\S+)", again.replace("\r\n ", "")), "the same ids from build to build")

    def test_a_feed_for_each_kind_and_venue(self):
        sinclair = dict(source("axs", "x", "music", "The Sinclair"), public=True)
        hidden = dict(source("ics", "y", "music", "Not Ours"), public=False)
        items = [build.event(sinclair, "A", date(2026, 9, 13), time(20, 0)), build.event(hidden, "B", date(2026, 9, 13))]
        feeds = build.calendar_feeds([sinclair, hidden], items, datetime(2026, 9, 13, tzinfo=timezone.utc))
        self.assertEqual(set(feeds), {"calendar/music.ics", "calendar/film.ics", "calendar/talks.ics", "calendar/the-sinclair.ics"})
        self.assertNotIn("SUMMARY:B", feeds["calendar/music.ics"], "not a source kept off the public site")
        self.assertEqual(build.calendar_address("calendar/music.ics"), "webcal://pushpin.city/calendar/music.ics")
        self.assertIn("calendar.google.com", build.calendar_address("calendar/music.ics", google=True))

    def test_each_listing_opens_its_own_view(self):
        sinclair = dict(source("axs", "x", "music", "The Sinclair"), public=True)
        items = [build.event(sinclair, "Akira (4K Restoration)", day, time(20, 0)) for day in (date(2026, 9, 13), date(2026, 9, 14))]
        page = build.render_index(items, [sinclair], [], [], datetime(2026, 9, 13, tzinfo=timezone.utc), public=True)
        # Each its own address, which the same show on other days shares the rest of.
        self.assertIn('data-id="2026-09-13-akira-4k-restoration-the-sinclair" data-series="akira-4k-restoration-the-sinclair"', page)
        self.assertIn('data-id="2026-09-14-akira-4k-restoration-the-sinclair"', page)
        self.assertEqual(page.count('<dialog class="event"'), 1)
        self.assertIn('<button class="event-share" type="button">', page)
        self.assertIn('<button class="event-add" type="button">', page, "and a way to add it to a calendar")
        self.assertIn('<button class="event-back" type="button" aria-label="Previous listing">', page, "the way through the list")
        self.assertIn('<button class="event-on" type="button" aria-label="Next listing">', page)
        self.assertIn("ArrowLeft: -1, ArrowRight: 1", page, "and from the keyboard")
        self.assertIn("navigator.share({ title, url })", page, "the share sheet, with the link alone, so it keeps its preview")
        self.assertIn(f"SHARE_URL = {json.dumps(build.PUBLIC_URL)}", page)
        self.assertNotIn('class="share"', page, "sharing is in the view, not on each row")


class Facts(unittest.TestCase):
    def test_price_from_a_line_of_facts(self):
        for line, price in [("$15 / $10 students", "$10–$15"), ("21+ · $10 cover", "$10"), ("Doors 8pm | 21+ | $5-20 cover", "$5–$20"),
                            ("$10-21+", "$10"), ("$13.50", "$13.50"), ("NO COVER! · 21+", "Free"), ("Free (cash only bar)", "Free"),
                            ("Free admission", "Free"), ("$0", ""), ("18 and under free", ""), ("Free pizza", ""),
                            ("Free with museum admission", ""), ("Raised $5 million", ""),
                            ("The cinema will be donating $4 from every ticket", "")]:
            self.assertEqual(build.price_from(line), price, line)
        self.assertEqual(build.price_of("18", 20.0), "$18–$20")
        self.assertEqual(build.price_of(0, None), "")

    def test_ages(self):
        for line, ages in [("All Ages", "All ages"), ("21+ · $10 cover", "21+"), ("18 and over", "18+"), ("18 and under free", "")]:
            self.assertEqual(build.ages_from(line), ages, line)

    def test_an_event_takes_price_and_ages_from_its_facts_not_its_prose(self):
        club = source("ics", "x")
        show = build.event(club, "A show", date(2026, 9, 13), about=["Doors at 8 · 21+ · $10 cover"])
        self.assertEqual((show["price"], show["ages"]), ("$10", "21+"))
        prose = "A long paragraph about the band, who raised $5,000 for charity and have played for all ages, " * 3
        self.assertEqual(build.event(club, "B", date(2026, 9, 13), about=[prose])[("price")], "")
        stated = "Presented by Get To The Gig Ages: This event is 21+ Valid ID required for Entry Doors 7:00 PM " * 2
        self.assertEqual(build.event(club, "C", date(2026, 9, 13), about=[stated])["ages"], "21+", "ages as a venue states them")
        given = build.event(club, "D", date(2026, 9, 13), about=["$10 cover"], price="$12", ages="All Ages")
        self.assertEqual((given["price"], given["ages"]), ("$12", "All ages"), "the source's own, when it gives them")

    def test_lighter_pictures(self):
        self.assertEqual(build.lighter("https://s1.ticketm.net/dam/a/1/x_TABLET_LANDSCAPE_LARGE_16_9.jpg"),
                         "https://s1.ticketm.net/dam/a/1/x_TABLET_LANDSCAPE_16_9.jpg")
        self.assertEqual(build.lighter("https://dice-media.imgix.net/a.jpg?rect=0"), "https://dice-media.imgix.net/a.jpg?rect=0&w=800")
        page = 'srcset="https://s3/p-2-203x300.jpg 203w, https://s3/p-2-768x1138.jpg 768w, https://s3/p-2-1382x2048.jpg 1382w"'
        self.assertEqual(build.lighter("https://s3/p-2-scaled.jpg", page), "https://s3/p-2-768x1138.jpg")
        self.assertEqual(build.lighter("https://s3/q.jpg", page), "https://s3/q.jpg")

    def test_the_view_shows_them(self):
        sinclair = dict(source("axs", "x", "music", "The Sinclair"), public=True)
        show = build.event(sinclair, "A show", date(2026, 9, 13), time(20, 0), image="https://example.com/a.jpg?w=1&h=2",
                           price="$18–$20", ages="21+")
        page = build.render_index([show], [sinclair], [], [], datetime(2026, 9, 13, tzinfo=timezone.utc), public=True)
        # Its picture and price; not who it's for, which is the door's rule and the venue's to give.
        self.assertIn('data-image="https://example.com/a.jpg?w=1&amp;h=2" data-price="$18–$20"', page)
        self.assertNotIn("data-ages", page)
        self.assertIn('<div class="event-image" hidden><img alt=""', page)
        self.assertIn('<p class="event-facts"></p>', page)
        films = [build.event(dict(sinclair, name=name), "Hope", date(2026, 9, 13), image=image) for name, image in (("A", ""), ("B", "https://b/1.jpg"))]
        self.assertEqual(build.combine_films([dict(film, category="film") for film in films])[0]["image"], "https://b/1.jpg")


class StructuredData(unittest.TestCase):
    def test_a_listing_gives_what_it_knows_and_no_more(self):
        sinclair = dict(source("axs", "x", "music", "The Sinclair"), public=True)
        priced = build.event(sinclair, "A show", date(2026, 9, 22), time(20, 0),
                             image="https://example.com/a.jpg", price="$20–$60", link="https://example.com/tickets")
        data = build.event_data(priced)
        self.assertEqual(data["image"], "https://example.com/a.jpg")
        self.assertEqual({data["offers"]["@type"], data["offers"]["lowPrice"], data["offers"]["highPrice"]},
                         {"AggregateOffer", "20", "60"})
        self.assertEqual(build.event_data(build.event(sinclair, "Free show", date(2026, 9, 22), time(20, 0),
                                                      price="Free"))["offers"]["price"], "0")
        # Nothing invented: a listing with no price and no picture says neither.
        bare = build.event_data(build.event(sinclair, "A show", date(2026, 9, 22), time(20, 0)))
        self.assertNotIn("offers", bare)
        self.assertNotIn("image", bare)
        # Sold out, where the source says so.
        gone = build.event_data(build.event(sinclair, "A show", date(2026, 9, 22), time(20, 0), price="$20", sold_out=True))
        self.assertEqual(gone["offers"]["availability"], "https://schema.org/SoldOut")


class Descriptions(unittest.TestCase):
    def test_all_of_it_kept_and_a_preview_clipped(self):
        long = "\n\n".join(f"Paragraph {n} says a good deal about the show, the band, and the night ahead of us all." for n in range(8))
        kept = build.about(long)
        self.assertEqual(len(kept), 8, "all of it, for the view")
        self.assertEqual(build.clip(["a" * 10, "b b b " * 100], 100), ["a" * 10, ("b b b " * 100)[:90].rsplit(" ", 1)[0] + "…"])
        self.assertEqual(build.clip(["one", "two", "three", "four"], 400), ["one", "two", "three"])
        self.assertEqual(build.clip(["x" * 300, "y y y " * 50], 320, least=60), ["x" * 300], "not a stub of a paragraph")

    def test_the_public_row_carries_none_of_it_its_search_an_excerpt_and_its_page_all_of_it(self):
        sinclair = dict(source("axs", "x", "music", "The Sinclair"), public=True)
        words = [f"Paragraph {n} says a good deal about the show, the band, and the night ahead of us all." for n in range(6)]
        show = build.event(sinclair, "A show", date(2026, 9, 13), time(20, 0), about=words)
        brief = build.event(sinclair, "Another", date(2026, 9, 13), time(21, 0), about=words[:1])
        bare = build.event(sinclair, "Nothing said", date(2026, 9, 13), time(22, 0))
        page = build.render_index([show, brief, bare], [sinclair], [], [], datetime(2026, 9, 13, tzinfo=timezone.utc), public=True)
        rows = re.sub(r'<script type="application/ld\+json">.*?</script>', "", page, flags=re.S)
        self.assertNotIn("Paragraph 0", rows, "the rows are lighter without it")
        self.assertEqual(page.count('data-more=""'), 2, "its view fetches it wherever there's any")
        texts = build.search_texts([sinclair], [show, brief, bare])
        self.assertTrue(texts["2026-09-13-a-show-the-sinclair"].startswith("Paragraph 0 says"))
        self.assertNotIn("Paragraph 5", texts["2026-09-13-a-show-the-sinclair"], "as much as the row used to carry")
        self.assertNotIn("2026-09-13-nothing-said-the-sinclair", texts)
        self.assertIn('fetch(new URL(SHARE_URL).pathname + "search.json")', page)
        own = build.event_pages([sinclair], [show])["e/2026-09-13-a-show-the-sinclair/index.html"]
        self.assertIn('<div class="about"><p>Paragraph 0', own)
        self.assertIn("Paragraph 5 says", own)
        self.assertIn('<button class="event-more" type="button" hidden', page)


    def test_search_engines_read_the_coming_week_on_the_home_page_and_everything_on_a_kinds(self):
        sinclair = dict(source("axs", "x", "music", "The Sinclair"), public=True)
        soon = build.event(sinclair, "Soon", date(2026, 9, 15), time(20, 0))
        later = build.event(sinclair, "Later", date(2026, 9, 30), time(20, 0))
        built = datetime(2026, 9, 13, 12, tzinfo=timezone.utc)
        home = build.render_index([soon, later], [sinclair], [], [], built, public=True)
        music = build.render_index([soon, later], [sinclair], [], [], built, public=True, category="music")
        described = lambda page: re.search(r'<script type="application/ld\+json">(.*?)</script>', page, re.S).group(1)
        self.assertIn('"name":"Soon"', described(home))
        self.assertNotIn('"name":"Later"', described(home), "the music page has it")
        self.assertIn('"name":"Later"', described(music))


class NewYork(unittest.TestCase):
    """Pushpin NYC's readers, each against a sample saved on November 17, 2026, and read as of then: several of
    its cinemas' pages give a day with no year, or only its number in the month."""

    def setUp(self):
        class November(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 11, 17, 12, tzinfo=tz)
        for patcher in (mock.patch.object(build, "fetch", sample), mock.patch.object(build, "datetime", November)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def read(self, kind, url, category, name):
        found = build.READERS[kind](dict(source(kind, url, category, name), zone=build.NYC.clock))
        self.assertTrue(found, f"{kind} read nothing from its sample")
        for item in found:
            self.assertTrue(item["title"].strip())
            self.assertIsInstance(item["date"], date)
            self.assertTrue(all(isinstance(moment, time) for moment in item["times"]))
            self.assertTrue(item["link"].startswith("http"), item["link"])
        return found

    def times(self, found, title, day):
        return [moment for item in found if item["title"] == title and item["date"] == day for moment in item["times"]]

    def test_its_own_site_and_sources(self):
        build.use_city(build.NYC)
        self.addCleanup(build.use_city, build.BOSTON_CITY)
        self.assertEqual((build.PUBLIC_URL, build.PUBLIC_NAME), ("https://pushpin.city/nyc/", "Pushpin NYC"))
        sources = build.read_sources(build.NYC.sources, "nyc", build.NYC.clock)
        self.assertEqual(build.NYC.sources.name, "sources-nyc.txt")
        self.assertEqual(len({s["name"] for s in sources}), len(sources), "a name is how a source's listings are kept")
        for s in sources:
            self.assertIn(s["kind"], build.READERS, s["name"])
            self.assertIn(s["category"], build.CATEGORIES, s["name"])
            # Each has an address, in New York, and a neighborhood for the venue menu to group it under.
            self.assertEqual(build.VENUE_ADDRESSES[s["name"]][2], "NY", s["name"])
            self.assertIn(s["name"], build.VENUE_AREAS)
        theirs = {s["name"] for city in build.CITIES if city is not build.NYC
                  for s in build.read_sources(city.sources, city.slug, city.clock)}
        self.assertFalse(theirs & {s["name"] for s in sources}, "no name another city's source has")
        about = build.render_about(sources, datetime(2026, 11, 17, tzinfo=timezone.utc))
        self.assertIn("I started Pushpin in Boston", about)
        self.assertNotIn("I live in Somerville", about)

    def test_the_venue_menu_goes_by_neighborhood(self):
        """Brooklyn says little about where a venue is; Bushwick does. A venue with no neighborhood goes by its
        town; one with one stays under it wherever a night of its own is (McNally Jackson's four stores)."""
        build.use_city(build.NYC)
        self.addCleanup(build.use_city, build.BOSTON_CITY)
        pool, vitus, issue = (dict(source("jsonld", name, "music", name), public=True) for name in ("Union Pool", "Saint Vitus", "ISSUE Project Room"))
        events = [build.event(pool, "A", date(2026, 11, 18), time(20, 0)), build.event(vitus, "B", date(2026, 11, 18), time(20, 0)),
                  build.event(issue, "C", date(2026, 11, 18), time(20, 0))]
        page = build.render_index(events, [pool, vitus, issue], [], [], datetime(2026, 11, 17, 17, tzinfo=timezone.utc), public=True)
        menu = page.split('aria-label="Venue">')[1].split("</select>")[0]
        self.assertEqual(sorted(re.findall(r'<optgroup label="([^"]+)">', menu)), ["Bushwick", "Downtown Brooklyn", "Williamsburg"])
        self.assertIn('data-address', build.address_attribute(dict(events[0], address=["1 Elsewhere St", "Queens", "NY", "11101"])))
        self.assertEqual(build.written(build.VENUE_ADDRESSES["Union Pool"]), "484 Union Ave, Brooklyn, NY 11211")

    def test_capitals_come_down_to_title_case(self):
        for shouted, said in [("RAISE THE RED LANTERN", "Raise the Red Lantern"), ("LADY WINDERMERE'S FAN", "Lady Windermere's Fan"),
                              ("L'INNOCENTE", "L'Innocente"), ("ROME, OPEN CITY", "Rome, Open City"), ("ROCKY II", "Rocky II"),
                              ("MACBETH 3000 (w/ Q&A)", "Macbeth 3000 (w/ Q&A)"), ("JFK", "JFK"), ("5 AGAINST THE HOUSE", "5 Against the House"),
                              ("TROMEO AND JULIET (Will Keenan in person on Sun, Nov 1!)", "Tromeo and Juliet (Will Keenan in person on Sun, Nov 1!)"),
                              ("EC: ERNIE GEHR", "EC: Ernie Gehr"), ("NYC SHORTS", "NYC Shorts"), ("RAN", "Ran"),
                              ("DOG STAR MAN: PART ONE", "Dog Star Man: Part One"), ("Memento", "Memento"),
                              ("threeASFOUR: FULL CIRCLE", "threeASFOUR: Full Circle")]:
            self.assertEqual(build.uncapped(shouted), said)

    def test_filmforum_times_have_no_am_or_pm(self):
        found = self.read("filmforum", "https://filmforum.org/", "film", "Film Forum")
        # Three of its week's tabs, each headed by the day of the month alone: the 17th, 20th and 22nd.
        self.assertEqual(sorted({item["date"] for item in found}), [date(2026, 11, 17), date(2026, 11, 20), date(2026, 11, 22)])
        # 12:20 is just after noon and 3:00 the afternoon's; an 11:00, Sunday's Film Forum Jr., the morning's.
        self.assertEqual(self.times(found, "Raise the Red Lantern", date(2026, 11, 17)), [time(12, 20), time(15, 0), time(17, 40), time(20, 20)])
        self.assertEqual(self.times(found, "Little Fugitive", date(2026, 11, 22)), [time(11, 0)])
        self.assertIn("Once Upon a Time in Harlem", {item["title"] for item in found}, "not in capitals")
        fatherland = next(item for item in found if item["title"] == "Fatherland")
        self.assertEqual(fatherland["link"], "https://filmforum.org/film/fatherland")
        self.assertTrue(fatherland["image"].endswith("FATHERLAND_thumbnail_1.png"), "from the page's list of what's playing")

    def test_metrograph_marks_a_sold_out_showing(self):
        found = self.read("metrograph", "https://metrograph.com/nyc/", "film", "Metrograph")
        self.assertEqual([(item["title"], item["date"], item["times"], item["sold_out"]) for item in found][:4],
                         [("Memento", date(2026, 11, 20), [time(15, 10)], False),
                          ("The Killing of a Sacred Deer", date(2026, 11, 20), [time(15, 45)], False),
                          ("That Day, On The Beach", date(2026, 11, 20), [time(17, 30)], False),
                          ("Wallace & Gromit: The Classic Shorts", date(2026, 11, 22), [time(11, 15)], True)])
        self.assertEqual(found[0]["about"][0], "Christopher Nolan · 2000 · 113min · 35mm")
        self.assertEqual(found[0]["link"], "https://metrograph.com/film/9999005093-memento/")
        self.assertTrue(all(item["image"] for item in found))

    def test_ifc_days_carry_no_year(self):
        found = self.read("ifc", "https://www.ifccenter.com/", "film", "IFC Center")
        self.assertEqual(sorted({item["date"] for item in found}), [date(2026, 11, 17), date(2026, 11, 18)])
        self.assertEqual(self.times(found, "The Devils", date(2026, 11, 17)), [time(11, 0), time(16, 35), time(19, 25), time(21, 15)])
        self.assertEqual(self.times(found, "Mouse", date(2026, 11, 18)), [time(10, 50), time(18, 40)])
        self.assertTrue(all(item["image"].startswith("https://images.amcnetworks.com/") for item in found))
        # A January day read in December is the January coming, not the one just gone.
        self.assertEqual(build.yearless("Jan", "3", date(2026, 12, 20)), date(2027, 1, 3))
        self.assertEqual(build.yearless("Nov", "17", date(2026, 11, 20)), date(2026, 11, 17))
        self.assertIsNone(build.yearless("Feb", "30", date(2026, 1, 1)))

    def test_filmbot_names_its_films_from_its_list_of_them(self):
        found = self.read("filmbot", "https://nitehawkcinema.com/williamsburg/", "film", "Nitehawk Williamsburg")
        self.assertEqual({item["title"] for item in found}, {"You Can See Everything"})
        self.assertEqual(self.times(found, "You Can See Everything", date(2026, 11, 17)), [time(15, 15), time(18, 5), time(21, 5)])
        self.assertEqual(found[0]["link"], "https://nitehawkcinema.com/williamsburg/movies/you-can-see-everything/")
        self.assertTrue(found[0]["image"].startswith("https://s3.amazonaws.com/nightjarprod/"))
        self.assertTrue(found[0]["about"][0].startswith("Elizabeth Holmes invites a skeptical film crew"))
        self.assertEqual(found[0]["about"][-1], "2026 · 174 min · R")

    def test_spectacle_reads_down_each_days_column(self):
        found = self.read("spectacle", "https://www.spectacletheater.com/spex-rolling.html", "film", "Spectacle")
        self.assertEqual(len(found), 17)
        tuesday = sorted((item["times"][0], item["title"]) for item in found if item["date"] == date(2026, 11, 17))
        self.assertEqual(tuesday, [(time(19, 30), "The Mob"), (time(22, 0), "The Crow Double Feature")])
        # A day with a third screening where the others have two: the cells under theirs are empty, not shifted along.
        self.assertEqual(sorted(item["title"] for item in found if item["times"] == [time(23, 55)]),
                         ["Mummy Theme Park", "Young Blondes Stalked and Murdered"])
        self.assertEqual({item["date"] for item in found if item["times"] == [time(23, 55)]}, {date(2026, 11, 20), date(2026, 11, 21)})
        mob = next(item for item in found if item["title"] == "The Mob")
        self.assertEqual(mob["link"], "https://www.spectacletheater.com/journey-through-the-past-70s-canadian-classics/")
        self.assertTrue(mob["image"].startswith("https://www.spectacletheater.com/wp-content/"))

    def test_bam_sorts_its_productions_by_kind(self):
        found = self.read("bam", "https://www.bam.org/api/BAMApi/GetCalendarEventsByDayWithOnGoing", "film", "BAM")
        kinds = {item["title"]: item["category"] for item in found}
        self.assertEqual(kinds["ArteEast Presents Sunshine Express"], "film")
        self.assertEqual(kinds["Samson et Dalila"], "film", "the Met's opera, live in its cinemas")
        self.assertEqual(kinds["Einstein on the Beach–50th Anniversary Concert"], "music")
        self.assertEqual(kinds["La Distance"], "art")
        self.assertEqual(kinds["Somi in conversation with Claudia Rankine and Helga Davis"], "art")
        self.assertNotIn("BAM TeenSpace", kinds, "not its classes")
        distance = next(item for item in found if item["title"] == "La Distance")
        self.assertEqual((distance["date"], distance["times"]), (date(2026, 11, 18), [time(19, 30)]))
        self.assertEqual(distance["link"], "https://www.bam.org/theater/2026/la-distance")
        self.assertIn("width=800", distance["image"])
        self.assertTrue(distance["about"][0].startswith("When a daughter opts for exile on Mars"))
        self.assertIn("I’mPossible Holiday Wonders", kinds, "its names' marks unescaped, twice over")

    def test_lpr_keeps_to_its_own_rooms(self):
        found = self.read("lpr", "https://lpr.com/wp-admin/admin-ajax.php?action=do_ajax&fn=get_homepageEvents", "music", "Le Poisson Rouge")
        # The page has a show it presents at The Town Hall and one in Miami Beach; neither is at LPR.
        self.assertEqual([(item["title"], item["date"], item["times"], item["detail"]) for item in found],
                         [("Phillip Phillips", date(2026, 11, 17), [time(18, 30)], "with Briscoe"),
                          ("Fruition", date(2026, 11, 18), [time(18, 30)], "with Handmade Moments")])
        self.assertEqual(found[0]["link"], "https://lpr.com/lpr_events/pp26nyc/")
        self.assertTrue(found[0]["image"].startswith("https://lpr.com/wp-content/uploads/"))

    def test_roulette(self):
        found = self.read("roulette", "https://roulette.org/calendar/", "music", "Roulette")
        self.assertEqual([(item["title"], item["date"], item["times"], item["price"]) for item in found][:2],
                         [("Qasim Naqvi: Slow Television", date(2026, 11, 18), [time(20, 0)], "$25"),
                          ("Breaks: A Solo Performance by Jessica Cook (Night 1)", date(2026, 11, 19), [time(20, 0)], "$25")])
        self.assertTrue(found[0]["about"][0].startswith("For his Roulette Commission"))
        self.assertTrue(found[0]["image"].endswith("-400x400.jpg"), "a size up from the list's thumbnail")

    def test_issue_says_where_a_night_elsewhere_is(self):
        found = self.read("issue", "https://issueprojectroom.org/events", "music", "ISSUE Project Room")
        crawford, _, girma = found
        # Its markup gives the time in UTC: 1am on the 20th there is 8pm on the 19th in Brooklyn.
        self.assertEqual((crawford["date"], crawford["times"]), (date(2026, 11, 19), [time(20, 0)]))
        self.assertIsNone(crawford["address"], "its own theater, by the venue's address")
        self.assertEqual(crawford["detail"], "")
        self.assertEqual(girma["detail"], "at MITU580")
        self.assertTrue(crawford["link"].startswith("https://issueprojectroom.org/event/"))
        self.assertTrue(crawford["image"].startswith("https://issueprojectroom.org/sites/default/files/"))

    def test_pioneer_works_lists_its_programs(self):
        found = self.read("pioneerworks", "https://pioneerworks.org/calendar", "art", "Pioneer Works")
        # Not its class, the gallery's open hours, or a festival that runs for weeks.
        self.assertEqual([(item["title"], item["date"], item["times"]) for item in found],
                         [("Rachel Cusk: Life of M", date(2026, 11, 17), [time(19, 30)])])
        self.assertEqual(found[0]["link"], "https://pioneerworks.org/programs/rachel-cusk-life-of-m")
        self.assertEqual(found[0]["about"], ["Doors 7pm"])
        self.assertTrue(found[0]["image"].endswith("?w=800&auto=format"))

    def test_anthology_reads_its_months_grid(self):
        found = self.read("anthology", "https://www.anthologyfilmarchives.org/film_screenings/calendar", "film", "Anthology Film Archives")
        self.assertEqual([(item["title"], item["date"], item["times"]) for item in found],
                         [("Tromeo and Juliet (Will Keenan in person on Sun, Nov 1!)", date(2026, 11, 1), [time(15, 30)]),
                          ("EC: Ernie Gehr", date(2026, 11, 1), [time(16, 30)]),
                          ("Terror Firmer (Lloyd Kaufman in person for both screenings!)", date(2026, 11, 1), [time(18, 15)]),
                          ("Dorsky & Hiler, PGM 2: Jerome Hiler", date(2026, 11, 17), [time(19, 0)]),
                          ("Devo: Restorations and Revelations", date(2026, 11, 17), [time(19, 30)])])
        self.assertTrue(found[0]["link"].endswith("/film_screenings/calendar?view=list&month=11&year=2026#showing-62052"))
        # A still's name with a space in it is an address with one escaped.
        self.assertEqual(found[-1]["image"], "https://www.anthologyfilmarchives.org/uploads/WHIP_IT%20copy.jpg")

    def test_quad_names_its_days_by_number(self):
        found = self.read("quad", "https://quadcinema.com/", "film", "Quad Cinema")
        self.assertEqual(self.times(found, "Digger", date(2026, 11, 17)), [time(13, 20), time(16, 20)])
        self.assertEqual(self.times(found, "Digger", date(2026, 11, 18)), [time(12, 45), time(15, 20)])
        heat = next(item for item in found if item["title"] == "Body Heat")
        self.assertEqual((heat["times"], heat["detail"], heat["link"]), ([time(19, 30)], "Femme Noir", "https://quadcinema.com/film/body-heat/"))
        self.assertTrue(heat["image"].startswith("https://quadcinema.com/wp-content/uploads/"))
        # A week's page named by day numbers alone: the 28th on a page read on the 27th is tomorrow, and a 2 next month's.
        self.assertEqual(build.day_numbered("28", date(2026, 11, 27)), date(2026, 11, 28))
        self.assertEqual(build.day_numbered("2", date(2026, 11, 27)), date(2026, 12, 2))
        self.assertIsNone(build.day_numbered("15", date(2026, 11, 27)))

    def test_mcnally_lists_its_talks_at_the_store_each_is_in(self):
        found = self.read("mcnally", "https://mcnallyjackson.com/events", "art", "McNally Jackson")
        # Not the book club between them.
        self.assertEqual([(item["title"], item["date"], item["times"], item["detail"]) for item in found],
                         [("Soyica Diggs Colbert & Salamishah Tillet", date(2026, 11, 2), [time(19, 0)], "Seaport"),
                          ("Girls Write Now: Metamorphosis Anthology Launch Party", date(2026, 11, 4), [time(18, 0)], "Seaport")])
        self.assertEqual(found[0]["address"], ["4 Fulton Street", "New York", "NY", "10038"])
        self.assertEqual(found[0]["link"], "https://mcnallyjackson.com/event/2026-11-02/soyica-diggs-colbert-salamishah-tillet")
        self.assertTrue(found[0]["about"][0].startswith("An illuminating portrait"))
        self.assertTrue(found[0]["image"].startswith("https://mcnallyjackson.com/sites/default/files/"))

    def test_vanguard_lists_a_band_on_each_night_of_its_run(self):
        found = self.read("vanguard", "https://villagevanguard.com/", "music", "Village Vanguard")
        zorn = [item for item in found if item["title"] == "John Zorn’s New Masada Quartet"]
        self.assertEqual([item["date"].day for item in zorn], [17, 18, 19, 20, 21, 22], "November 17 ‑ November 22")
        self.assertTrue(all(not item["times"] for item in found), "the page gives the nights, not the sets")
        self.assertEqual(zorn[0]["about"], ["John Zorn – Saxophone · Julian Lage – Guitar · Jorge Roeder – Bass · Kenny Wollesen – Drums"])
        self.assertEqual(zorn[0]["link"], "https://vv.squadup.com/artists/john-zorn-new-masada-quartet")
        # A run over New Year's ends in the year after it starts; one night alone has no end.
        potter = [item["date"] for item in found if item["title"] == "Chris Potter Quartet"]
        self.assertEqual((potter[0], potter[-1], len(potter)), (date(2026, 12, 29), date(2027, 1, 3), 6))
        self.assertEqual([item["date"] for item in found if item["title"].startswith("New Year’s Eve")], [date(2026, 12, 31)])

    def test_national_sawdust_lists_by_day(self):
        found = self.read("nationalsawdust", "https://www.nationalsawdust.org/performances", "music", "National Sawdust")
        self.assertEqual([(item["title"], item["date"], item["times"]) for item in found],
                         [("makemake presents: Wholly Unwinding (A New Musical) - NYC Premiere", date(2026, 11, 17), []),
                          ("makemake presents: Opera Praktikos’ La Sonnambula", date(2026, 11, 18), [])])
        self.assertEqual(found[1]["link"], "https://www.nationalsawdust.org/event/opera-praktikos-presents-la-sonnambula")
        self.assertTrue(found[1]["image"].endswith("logo-sleeve%20(1).png"), "to its end, past the bracket in its name")
        self.assertTrue(found[0]["about"][0].startswith("Step through a portal"))


class DayHeadings(unittest.TestCase):
    def test_today_and_tomorrow_are_written_in(self):
        """As of the build, by the city's clock, so they're there as the page first shows rather than swapped in
        once its script, at the foot of a long page, has run; the script says them again by the reader's day."""
        venue = dict(source("axs", "x", "music", "The Sinclair"), public=True)
        events = [build.event(venue, "A show", date(2026, 9, day), time(20, 0)) for day in (15, 16, 17)]
        page = build.render_index(events, [venue], [], [], datetime(2026, 9, 15, 16, tzinfo=timezone.utc), public=True)
        self.assertIn('<h2><span class="relative">Today</span><span class="date"><span class="weekday">Tuesday</span>, Sep 15</span></h2>', page)
        self.assertIn('<h2><span class="relative">Tomorrow</span><span class="date"><span class="weekday">Wednesday</span>, Sep 16</span></h2>', page)
        self.assertIn('<h2><span class="relative"></span><span class="date"><span class="weekday">Thursday</span>, Sep 17</span></h2>', page)
        # 11pm on the 15th in Boston is already the 16th by UTC: the city's day, not the clock's.
        late = build.render_index(events, [venue], [], [], datetime(2026, 9, 16, 3, tzinfo=timezone.utc), public=True)
        self.assertIn('<span class="relative">Today</span><span class="date"><span class="weekday">Tuesday</span>', late)


class JustAnnounced(unittest.TestCase):
    def setUp(self):
        self.built = datetime(2026, 9, 15, 12, tzinfo=timezone.utc)
        self.venue = dict(source("axs", "x", "music", "The Sinclair"), public=True)

    def listing(self, day, title="A show", category="music"):
        return dict(build.event(self.venue, title, date(2026, 9, day), time(20, 0)), category=category)

    def gather(self, found, previous):
        return build.gather([(self.venue, found, None)], previous, self.built)

    def test_first_seen_stamped_and_kept(self):
        # The first build of all: everything older than new, so nothing is announced.
        *_, seen = self.gather([self.listing(20)], {"sources": {"The Sinclair": {"fetched": self.built.isoformat(), "events": []}}})
        self.assertEqual(set(seen.values()), {"2026-09-07"})
        # A build after that: what's turned up since is stamped today, and what was there keeps its day.
        before = {"sources": {"The Sinclair": {"fetched": self.built.isoformat(), "events": []}},
                  "first_seen": {"2026-09-20-a-show-the-sinclair": "2026-09-01"}}
        events, *_, seen = self.gather([self.listing(20), self.listing(21, "New show")], before)
        self.assertEqual(seen["2026-09-20-a-show-the-sinclair"], "2026-09-01", "as it was")
        self.assertEqual(seen["2026-09-21-new-show-the-sinclair"], "2026-09-15")
        self.assertEqual([item["added"] for item in events], ["2026-09-01", "2026-09-15"])

    def test_a_source_that_failed_keeps_its_days(self):
        before = {"sources": {}, "first_seen": {"2026-09-20-a-show-the-sinclair": "2026-09-01", "2026-08-01-old-show-the-sinclair": "2026-07-01"}}
        *_, seen = build.gather([(self.venue, [], OSError("520"))], before, self.built)
        self.assertEqual(seen, {"2026-09-20-a-show-the-sinclair": "2026-09-01"}, "what it still has ahead, not what's passed")

    def test_newly_added_is_this_week_without_films(self):
        fresh = dict(self.listing(20), added="2026-09-15")
        older = dict(self.listing(21, "Older"), added="2026-09-01")
        film = dict(self.listing(22, "A film", "film"), added="2026-09-15")
        soonest = dict(self.listing(18, "Sooner"), added="2026-09-15")
        found = build.newly_added([older, fresh, film, soonest], self.built)
        self.assertEqual([item["title"] for item in found], ["Sooner", "A show"], "this week's, soonest first; films stay out")

    def test_late_night_just_announced_and_sold_out_are_filters(self):
        """Each row marked for the filters it meets (data-late, data-new, data-soldout), and each switch in the
        panel only where the page has any: Hide sold out leaving the marked rows out, the others keeping them,
        and Just announced for its kinds alone, as its lead is."""
        late = dict(build.event(self.venue, "Late Set", date(2026, 9, 21), time(22, 0)), added="2026-09-01")
        fresh = dict(self.listing(22, "Announced"), added="2026-09-15")
        gone = dict(build.event(self.venue, "Gone", date(2026, 9, 23), time(19, 0), sold_out=True), added="2026-09-01")
        page = build.render_index([late, fresh, gone], [self.venue], [], [], self.built, public=True)
        row = lambda title: page[page.rindex("<li ", 0, page.index(f">{title}</a>")):page.index(f">{title}</a>")]
        self.assertIn(" data-late>", row("Late Set"))
        self.assertIn(" data-new>", row("Announced"))
        self.assertIn(" data-soldout>", row("Gone"))
        self.assertNotIn("data-late", row("Announced"), "8pm isn't late")
        self.assertIn('<input type="checkbox" name="late" data-mark="late">', page)
        self.assertIn('<input type="checkbox" name="new" data-mark="new" data-kinds="art music">', page)
        self.assertIn('<input type="checkbox" name="available" data-mark="soldout" data-hides>', page)
        self.assertNotIn('name="once"', page, "no film showing once here")
        self.assertIn("""li => (input.dataset.mark in li.dataset) !== ("hides" in input.dataset)""", page)
        # By when it starts, as its row says: a film with a late show among earlier ones isn't late night. Past
        # midnight is, and a late show and one after midnight.
        self.assertFalse(build.late_night({"times": [time(19), time(21, 45)]}))
        self.assertTrue(build.late_night({"times": [time(21, 45), time(0, 15)]}))
        self.assertTrue(build.late_night({"times": [time(0, 30)]}))
        self.assertFalse(build.late_night({"times": [time(21, 15)]}))
        self.assertFalse(build.late_night({"times": []}), "no time given isn't late")

    def test_the_list_is_unpainted_until_the_script_has_run(self):
        """What's passed since the build would show for a moment and then go: nothing under the header is painted
        until the page has been read through and its script has run, and then it shows, the script or not."""
        page = build.render_index([dict(self.listing(20), added="2026-09-15")], [self.venue], [], [], self.built, public=True)
        start = page.index('<script>document.documentElement.classList.add("settling");')
        self.assertLess(start, page.index('class="filter"'), "marked before any of it is read")
        self.assertIn('addEventListener("DOMContentLoaded", () => document.documentElement.classList.remove("settling"));', page)
        self.assertIn(".settling main > :not(header):not(.tagline):not(.lead):not(.bar-mark):not(.filter):not(.skeleton) "
                      "{ visibility: hidden; opacity: 0; }", page, "the listings; what's over them shows at once")
        self.assertIn("transition: opacity .18s ease-out", page, "and then fades in")
        self.assertIn('</nav>\n<div class="skeleton" aria-hidden="true">', page, "an outline in their place meanwhile")

    def test_a_venue_saying_its_closed_isnt_a_show(self):
        """Club Passim's "club closed" and Midway Cafe's "**CLOSED**" are its calendar saying it's shut; a name with
        the word in it is still a show."""
        for notice in ["club closed", "**CLOSED**", "Closed for Christmas", "CLOSED TODAY!", "The Club Is Closed"]:
            self.assertTrue(build.CLOSURE.fullmatch(notice), notice)
        for name in ["Closed Circuit", "Doors Closed Live", "Holiday Party (closed to public)"]:
            self.assertFalse(build.CLOSURE.fullmatch(name), name)

    def test_sally_obriens_is_never_announced(self):
        """Its page is written by hand, and a night's name there is as often notes and set times as a band's."""
        sally = dict(self.listing(20, "Bluegrass Jam 8pm followed by"), venue="Sally O'Brien's", added="2026-09-15")
        found = build.newly_added([sally, dict(self.listing(21), added="2026-09-15")], self.built)
        self.assertEqual([item["venue"] for item in found], ["The Sinclair"])

    def test_a_name_all_in_capitals_is_calmed_over_the_listings(self):
        """Three names shouting are most of what's announced there. Only one that's nearly all capitals: a band
        that writes itself so among others that don't keeps its own, and the list below keeps every name."""
        self.assertEqual(build.calm('PLASTIC, ANDREW DANFORTH, WARRN "TRAE" CRUDUP & AYUMI ISHITO'),
                         'Plastic, Andrew Danforth, Warrn "Trae" Crudup & Ayumi Ishito')
        for name in ("SKORTS, Paper Lady, Truman Flyer", "Sidney Gish Live Performance", "MGMT", "DJ Rekha",
                     "BENEDICT KOH BIG BAND + durianhead"):  # Written with care, capitals and all: left as it is.
            self.assertEqual(build.calm(name), name)
        shouting = dict(self.listing(20, "DRU CUTLER, ZAPBEETLE, HANA BOOKMAN"), added="2026-09-15")
        lead = build.render_lead([shouting], self.built)[0]
        self.assertIn('<span class="fresh-name">Dru Cutler, Zapbeetle, Hana Bookman</span>', lead)
        self.assertIn("event=2026-09-20-dru-cutler-zapbeetle-hana-bookman-the-sinclair", lead, "its row is still the one it goes to")

    def test_headed_and_drawn_as_the_list_is(self):
        """Each part headed in words over a hairline, white and semibold, led by its kind's mark in its color; and
        on a wide screen the two over the list's two columns."""
        page = build.render_index([dict(self.listing(20), added="2026-09-15")], [self.venue], [], [], self.built, public=True)
        self.assertIn('<div class="lead-head"><a class="lead-tag fresh-tag" href="', page)
        self.assertIn(".lead-tag { color: #fff; font-size: .95rem; font-weight: 600;", page)
        self.assertNotIn("lead-mark", page.split('class="fresh"')[1].split("</div>")[0], "its words alone, no mark")
        self.assertNotIn(".fresh-more { display: none; }", page, "See all is there on a phone too")
        # A line each: the name alone, cut short where it must be; beside the film's card on a wide screen.
        self.assertIn(".fresh-name { flex: 0 1 auto; min-width: 3em;", page)
        self.assertNotIn("fresh-meta", page, "no venue after it, which left the name cut short")
        self.assertIn(".lead { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 4fr);", page)
        # Room between the listings, and on a phone alone a hairline: not over the first the filter leaves.
        self.assertIn(".day > ul > li.row { padding-top: .45rem; padding-bottom: .45rem; }", page)
        self.assertIn("    .day > ul > li.row { padding-top: .65rem; padding-bottom: .65rem; }\n"
                      "    .day > ul > li:not([hidden]) ~ li.row:not(.evening-starts) { border-top: 1px solid #161616; }", page,
                      "a phone's two lines a little more room")

    def test_the_list_and_the_page(self):
        events = [dict(self.listing(20 + n, f"Show {n}"), added="2026-09-15") for n in range(10)]
        lead, film = build.render_lead(events, self.built)
        self.assertEqual(film, "", "no film among them")
        self.assertIn('<div class="lead one">', lead, "on its own, with no film big enough beside it")
        self.assertEqual(lead.count("<li data-ends="), build.FRESH_SHOWN + build.FRESH_SPARE,
                         "the newest few, a line each, and spares for any that's started by the time it's read")
        page = build.render_index(events, [self.venue], [], [], self.built, public=True)
        self.assertIn(f".fresh-list li:nth-child(n+{build.FRESH_SHOWN + 1}) {{ display: none; }}", page,
                      "the spares unseen until one before them goes")
        # One whose listing the page has dropped goes, rather than opening a listing that's not there.
        self.assertIn('if (link.closest(".fresh-list")) link.closest("li").remove();', page)
        self.assertIn(f'<li data-ends="2026-09-20T20:00"><a href="{R}?event=2026-09-20-show-0-the-sinclair" data-category="music">'
                      '<svg class="icon" role="img" aria-label="Music"><use href="#icon-music"/></svg>'
                      '<span class="fresh-name">Show 0</span><span class="fresh-day">'
                      '<span class="lead-day" data-date="2026-09-20" data-said="Sep 20">Sep 20</span></span></a></li>', lead,
                      "its name and its day, without its weekday; its venue is in its view")
        # Today's and tomorrow's say so, as the film's day does; the script says them again by the reader's day.
        soon = [dict(self.listing(15, "Tonight's"), added="2026-09-15"), dict(self.listing(16, "Tomorrow's"), added="2026-09-15")]
        self.assertIn('<span class="lead-day" data-date="2026-09-15" data-said="Sep 15">Today</span>', build.render_lead(soon[:1], self.built)[0])
        self.assertIn('<span class="lead-day" data-date="2026-09-16" data-said="Sep 16">Tomorrow</span>', build.render_lead(soon[1:], self.built)[0])
        self.assertNotIn("<img", lead, "words alone")
        self.assertIn(f'<a class="fresh-more" href="{R}new/">See all →</a></div><ul class="fresh-list">', lead,
                      "the way to the rest in the heading's line, not one of its own")
        # Nothing new and nothing big: nothing over the list at all.
        self.assertEqual(build.render_lead([dict(self.listing(20), added="2026-09-01")], self.built), ("", ""))
        page = build.render_index(events, [self.venue], [], [], self.built, public=True, added=True)
        self.assertIn('<section class="day" data-added><h2><span class="date">Recently added</span></h2>', page)
        self.assertEqual(page.count('<section class="day"'), 1, "one list, newest first")
        self.assertIn('</svg><span class="when">Sun, Sep 20</span><span class="clock">', page,
                      "the day each is on, leading the small line over its name")
        self.assertIn("<title>Just announced in Boston · Pushpin Boston</title>", page)
        self.assertIn('data-narrowed="Nothing added in the last week">No new events this week. Check back as venues announce more.</p>', page)
        home = build.render_index([], [self.venue], [], [], self.built, public=True)
        self.assertIn('data-narrowed="Nothing coming up">Nothing coming up.</p>', home)
        home = build.render_index(events, [self.venue], [], [], self.built, public=True)
        self.assertIn('<div class="fresh">', home)
        self.assertNotIn('<div class="fresh">', page, "not on the page itself")
        self.assertIn(f'<li><a href="{R}new/">Just announced</a></li>', build.public_footer(""))
        self.assertIn(f"<loc>{build.PUBLIC_URL}new/</loc>", build.render_sitemap(self.built))


class ViewHoldsThePage(unittest.TestCase):
    def test_the_page_behind_an_open_view_doesnt_scroll(self):
        """The root hides its sideways overflow, so hiding the body's doesn't reach the window's scrolling: the
        root's is hidden too, and the view's scrolling stops at its ends rather than carrying on into the page."""
        venue = dict(source("ics", "x", "music", "The Sinclair"), public=True)
        page = build.render_index([build.event(venue, "A Show", date(2026, 9, 15), time(20))], [venue], [], [],
                                  datetime(2026, 9, 13, tzinfo=timezone.utc), public=True)
        self.assertIn("body.viewing, html:has(> body.viewing) { overflow: hidden; }", page)
        self.assertIn("dialog.event, .event-body { overscroll-behavior: contain; }", page)


class TimeColumn(unittest.TestCase):
    """A listing's time in a column of its own before its name, so the eye runs down the times rather than
    hunting for each after a name of its own length."""
    venue = dict(source("ics", "x", "music", "The Sinclair"), public=True)
    day = date(2026, 9, 15)
    built = datetime(2026, 9, 13, tzinfo=timezone.utc)

    def test_the_first_and_how_many_more(self):
        self.assertEqual(build.render_clock([time(21), time(19), time(19)]), '<span class="clock"><b>7<span class="oclock">:00</span>pm</b><small title="1 more showtime">+1 more</small></span>')
        self.assertEqual(build.render_clock([time(20, 30)]), '<span class="clock"><b>8:30pm</b></span>')
        # No time given: said in a word, the script's to say again.
        self.assertEqual(build.render_clock([]), '<span class="clock" data-untimed="Time TBA"><i class="untimed">Time TBA</i></span>')
        self.assertIn(">All day</i>", build.render_clock([], category="art"), "an exhibition's day")
        # And after the day's timetable, not over it, in the build and in the script.
        built = datetime(2026, 9, 15, 16, 0, tzinfo=timezone.utc)
        venue = source("aeg", "https://example.com", name="The Sinclair")
        untimed = build.event(venue, "Untimed", date(2026, 9, 20))
        timed = build.event(venue, "Timed", date(2026, 9, 20), time(20, 0))
        page = build.render_index([untimed, timed], [venue], [], [], built, public=True)
        self.assertLess(page.index(">Timed<"), page.index(">Untimed<"))
        self.assertIn('const firstOf = li => li.dataset.first || "~";', page)

    def test_after_the_mark_and_before_the_name(self):
        row = build.render_row(build.event(self.venue, "A Show", self.day, time(20)))
        self.assertIn('</svg><span class="clock"><b>8<span class="oclock">:00</span>pm</b></span><div class="headline">', row)
        self.assertNotIn("<time", row[row.index('class="clock"'):row.index('class="headline"')],
                         "no <time> in it: the row's own times are what the script counts and drops")

    def test_a_film_at_several_theaters_counts_them_all(self):
        film = dict(self.venue, category="film")
        showings = [build.event(dict(film, name="Coolidge Corner"), "Wide Release", self.day, time(13)),
                    build.event(dict(film, name="Brattle"), "Wide Release", self.day, time(16)),
                    build.event(dict(film, name="Somerville"), "Wide Release", self.day, time(13))]
        combined = [item for item in build.combine_films(showings) if "showings" in item]
        self.assertEqual(len(combined), 1)
        self.assertIn('<span class="clock"><b>1<span class="oclock">:00</span>pm</b><small title="1 more showtime">+1 more</small></span><div class="headline"><span class="title">Wide Release',
                      build.render_row(combined[0]), "1pm at two of them and 4pm at the third: 1pm, and one more")

    def test_each_listing_one_block_on_a_phone_and_a_timetables_line_wider(self):
        page = build.render_index([build.event(self.venue, "A Show", self.day, time(20))], [self.venue], [], [], self.built, public=True)
        self.assertIn(".day .headline > .times, .day .headline .tail, .day .headline > .later { display: none; }", page,
                      "said once, on the small line")
        # A wide screen's row says its next two showings after its name, the time's column only its first.
        self.assertIn(".day .headline > .later { display: inline; margin-left: .7em; color: #777;", page)
        self.assertIn(".day .row .clock small { display: none; }", page)
        self.assertIn("const LATER_SHOWN = 2;", page)
        self.assertIn('headline.querySelector(":scope > .title").after(line);', page)
        # One block at every width, not in a phone's rules alone: the time and the venue on a small line, the name
        # under it, no mark.
        block = page.index(".day > ul > li.row:not(.combined), .combined > details > summary {\n    display: flex;")
        self.assertNotIn("@media", page[page.rindex("}", 0, block) - 40:block], "outside any @media")
        self.assertIn(".clock { order: 1; display: flex;", page)
        self.assertIn(".day .row .source { order: 2; display: block; max-width: none;", page)
        self.assertIn(".day .headline { order: 3; flex-basis: 100%; }", page)
        # On a phone the name first, led by its mark; the time and venue under it, lined up with the name.
        self.assertIn("    .day .headline { order: 1; flex: 0 0 calc(100% - 15px - .5rem); min-width: 0; }\n"
                      "    .day .row > .when { order: 2; margin-left: calc(15px + .5rem); }\n"
                      "    .clock { order: 3; margin-left: calc(15px + .5rem); }", page)
        self.assertIn(".day > ul > li.row > .icon, .day > ul > li.combined > details > summary > .icon {\n"
                      "    display: block; order: 1; position: static; align-self: center; margin-right: .45em; }", page)
        # Wider than a phone, one column of a timetable's lines: the time, the name, the venue at the right.
        self.assertIn("@media not all and (max-width: 34rem) {\n    .day > ul > li.row:not(.combined), .combined > details > summary {\n"
                      "      display: grid; grid-template-columns: 7.8rem minmax(0, 1fr) auto;", page)
        self.assertNotIn("max-width: 64rem", page, "not two columns in a wider page")
        # The time grey, its kind's mark in its color before it, not the whole time in color; a wide screen's in
        # the time's own cell.
        self.assertIn(".clock b { color: #d4d4d4; font-weight: 400; }", page)
        self.assertNotIn(".clock::before", page, "the mark, not a dot")
        self.assertIn(".clock { grid-column: 1; grid-row: 1; font-size: .85rem; padding-left: calc(15px + .45em); }", page)
        # A listing opened drawn as the list is: its day a small line led by that dot, the name the list's weight,
        # no mark beside it.
        self.assertIn('<h2 class="event-title" id="event-title"><span class="event-name"></span></h2>\n'
                      '<p class="event-where"><span class="event-icon"></span><span class="event-day"></span></p>', page,
                      "the name first, at the edge, and its day under it led by its mark")
        self.assertIn(".event-where .icon { width: 14px; height: 14px; margin-right: .4em; vertical-align: -2px; }", page)
        self.assertNotIn(".event-where::before", page, "its kind's mark, not a dot")
        # The script says it again as what's shown changes, and puts each day in the column's order.
        self.assertIn("for (const li of allRows) clockOf(li);\n    inOrder();", build.INDEX_JS)
        self.assertIn('document.querySelectorAll(".day:not([data-added]) > ul")', build.INDEX_JS, "not Recently added's, newest first")


class SoldOut(unittest.TestCase):
    def test_marked_in_a_name(self):
        club = source("ics", "x")
        for name, clean in [("Yana – SOLD OUT!", "Yana"), ("SOLD OUT: The Bowery Presents ear", "The Bowery Presents ear"),
                            ("Jackie Evans (Sold Out)", "Jackie Evans")]:
            item = build.event(club, name, date(2026, 9, 13))
            self.assertEqual((item["title"], item["sold_out"]), (clean, True), name)
        self.assertFalse(build.event(club, "The Sold Out Crowd", date(2026, 9, 13))["sold_out"])

    def test_some_showings_or_all(self):
        coolidge = dict(source("coolidge", "x", "film", "Coolidge Corner"), public=True)
        day = date(2026, 9, 15)
        first, second = build.event(coolidge, "Union County", day, time(19, 15)), build.event(coolidge, "Union County", day, time(19, 45))
        second["sold_out"] = True
        merged = build.merge_showings([first, second])[0]
        self.assertEqual((merged["times"], merged["sold_out_times"], build.is_sold_out(merged)), ([time(19, 15), time(19, 45)], ["19:45"], False))
        page = build.render_index([merged], [coolidge], [], [], datetime(2026, 9, 13, tzinfo=timezone.utc), public=True)
        self.assertIn('<time data-time="19:15">7:15pm</time><span class="sep">, </span><time data-time="19:45" class="sold">7:45pm</time>', page)
        merged["sold_out_times"] = ["19:15", "19:45"]
        self.assertTrue(build.is_sold_out(merged))
        own = build.event_pages([coolidge], [merged])["e/2026-09-15-union-county-coolidge-corner/index.html"]
        self.assertIn("Coolidge Corner · Tue, Sep 15 · 7:15pm, 7:45pm · Sold out", own)

    def test_the_time_column_strikes_a_first_showing_sold_out(self):
        self.assertEqual(build.render_clock([time(19, 45), time(19, 15)], ["19:15"]),
                         '<span class="clock"><b class="sold">7:15pm</b><small title="1 more showtime">+1 more</small></span>')

    def test_coolidge_film_pages_are_fresher(self):
        page = ('<div class="film-showtime-list"><div class="datepicker "><span class="datepicker__day">Tue</span>'
                '<span class="datepicker__date">9/15</span></div><div class="views-row-inactive availability--individual '
                'sales-state--DisplayCustomMessage"><a href="x"><span class="showtime-ticket"><span class="showtime-ticket__time">7:15pm'
                '</span></span></a></div><div class="views-row-active-agiletix availability--individual sales-state--DuringSales">'
                '<a href="y"><span class="showtime-ticket"><span class="showtime-ticket__time">9:30pm</span></span></a></div></div>')
        with mock.patch.object(build, "fetch", lambda *args, **kwargs: page), mock.patch.object(build, "today", lambda: date(2026, 9, 14)):
            states = build.coolidge_film_states("https://coolidge.org/films/union-county")
        self.assertEqual(states, {(date(2026, 9, 15), "19:15"): "DisplayCustomMessage", (date(2026, 9, 15), "21:30"): "DuringSales"})


class SharedLinks(unittest.TestCase):
    def test_each_listing_has_a_page_with_its_own_preview(self):
        coolidge = dict(source("coolidge", "x", "film", "Coolidge Corner"), public=True)
        alamo = dict(source("alamo", "y", "film", "Alamo Drafthouse"), public=True)
        hidden = dict(source("ics", "z", "music", "Not Ours"), public=False)
        day = date(2026, 9, 15)
        items = [build.event(coolidge, "Akira (4K Restoration)", day, time(15, 30)),
                 build.event(coolidge, "Hope", day, time(12, 45)), build.event(alamo, "Hope", day, time(14, 15)),
                 build.event(hidden, "Theirs", day)]
        items[0]["times"] += [time(18, 45)]
        pages = build.event_pages([coolidge, alamo, hidden], items)
        self.assertEqual(set(pages), {"e/2026-09-15-akira-4k-restoration-coolidge-corner/index.html", "e/2026-09-15-hope/index.html",
                                      # And beside each, a calendar file for each showing, by place and time.
                                      "e/2026-09-15-akira-4k-restoration-coolidge-corner/coolidge-corner-1530.ics",
                                      "e/2026-09-15-akira-4k-restoration-coolidge-corner/coolidge-corner-1845.ics",
                                      "e/2026-09-15-hope/coolidge-corner-1245.ics", "e/2026-09-15-hope/alamo-drafthouse-1415.ics"})
        showing = pages["e/2026-09-15-hope/alamo-drafthouse-1415.ics"]
        self.assertTrue(showing.startswith("BEGIN:VCALENDAR\r\n") and showing.count("BEGIN:VEVENT") == 1)
        self.assertIn("DTSTART:20260915T181500Z\r\nDTEND:20260915T201500Z\r\n", showing, "2:15pm in Boston, for two hours")
        self.assertIn("SUMMARY:Hope\r\nLOCATION:Alamo Drafthouse", showing)
        akira = pages["e/2026-09-15-akira-4k-restoration-coolidge-corner/index.html"]
        self.assertIn('<meta property="og:title" content="Showtimes for Akira (4K Restoration) at Coolidge Corner · Tue, Sep 15">', akira)
        self.assertIn('<meta property="og:title" content="Showtimes for Hope · Tue, Sep 15">', pages["e/2026-09-15-hope/index.html"])
        self.assertIn('<meta property="og:description" content="Coolidge Corner · Tue, Sep 15 · 3:30pm, 6:45pm">', akira)
        self.assertIn(f'<meta property="og:image" content="{build.PUBLIC_URL}share/film.png?pin">', akira)
        self.assertIn(f'location.replace("{build.PUBLIC_URL}?event=2026-09-15-akira-4k-restoration-coolidge-corner")', akira)
        self.assertIn('<meta name="robots" content="noindex">', akira)
        self.assertIn("2 theaters (Alamo Drafthouse, Coolidge Corner) · Tue, Sep 15 · from 12:45pm", pages["e/2026-09-15-hope/index.html"])
        self.assertIn('<meta property="og:image:width" content="1200">', akira)

    def test_a_listings_own_picture_price_and_ages_in_its_preview(self):
        rockwell = dict(source("tribe", "x", "music", "The Rockwell"), public=True)
        show = build.event(rockwell, "Telescreens", date(2026, 9, 18), time(19, 0), image="https://therockwell.org/t.png",
                           price="$18–$20", ages="21+")
        page = build.event_pages([rockwell], [show])["e/2026-09-18-telescreens-the-rockwell/index.html"]
        self.assertIn('<meta property="og:image" content="https://therockwell.org/t.png">', page)
        self.assertNotIn("og:image:width", page, "its size isn't known")
        self.assertIn('content="The Rockwell · Fri, Sep 18 · 7pm · $18–$20 · 21+"', page)
        self.assertIn('<meta property="og:title" content="Telescreens at The Rockwell · Fri, Sep 18, 7pm">', page)
        armory = dict(source("armory", "x", "music", "Arts at the Armory"), public=True)
        spotlight = build.event(armory, "Arts at the Armory Spotlight Series Presents L. Shankar", date(2026, 9, 17), time(19, 0))
        self.assertEqual(build.share_title(spotlight, date(2026, 9, 17)), "Arts at the Armory Spotlight Series Presents L. Shankar · Thu, Sep 17, 7pm")

    def test_a_passed_listings_page_goes_to_its_view(self):
        missing = build.render_redirect(build.PUBLIC_URL, paths=True)
        self.assertIn(f'location.pathname.startsWith("{build.PUBLIC_ROOT}e/")', missing)
        self.assertIn('"?event=" + location.pathname', missing)


class Moving(unittest.TestCase):
    def test_redirects_keep_the_page_and_its_filters(self):
        page = build.render_redirect(build.PUBLIC_URL + "music/")
        self.assertIn(f'<meta http-equiv="refresh" content="0; url={build.PUBLIC_URL}music/">', page)
        self.assertIn(f'<link rel="canonical" href="{build.PUBLIC_URL}music/">', page)
        self.assertIn("location.search + location.hash", page, "?venue= and ?q= come along")
        missing = build.render_redirect(build.PUBLIC_URL, paths=True)
        self.assertIn("location.pathname.slice(1)", missing, "an old /music/ goes to /boston/music/")
        self.assertIn(f'location.pathname.startsWith("{build.PUBLIC_ROOT}")', missing, "and never /boston/boston/")


class Window(unittest.TestCase):
    def test_concerts_two_months_ahead_the_rest_one(self):
        with mock.patch.object(build, "today", lambda: date(2026, 9, 1)):
            self.assertEqual(build.window_end("music"), date(2026, 10, 31))
            self.assertEqual(build.window_end("film"), date(2026, 10, 1))
            self.assertEqual(build.window_end(), date(2026, 10, 1))


class Fetching(unittest.TestCase):
    def test_a_page_read_twice_is_downloaded_once(self):
        calls = []
        def download(url, *args):
            calls.append(url)
            return url, b"<html></html>"
        build._fetched.clear()
        self.addCleanup(build._fetched.clear)
        with mock.patch.object(build.shared, "fetch", download):
            build.fetch("https://www.icaboston.org/events/colin-stetson")
            build.fetch("https://www.icaboston.org/events/colin-stetson")
        self.assertEqual(calls, ["https://www.icaboston.org/events/colin-stetson"])

    def test_mit_asks_for_exhibits_and_lectures_only(self):
        asked = []
        with mock.patch.object(build, "fetch", lambda url: asked.append(url) or sample(url)):
            build.read_mit(source("mit", "https://calendar.mit.edu/api/2/events", "art", "MIT"))
        self.assertIn("type%5B%5D=102763&type%5B%5D=102764", asked[0])

    def test_ica_reads_event_pages_only_for_events_in_the_window(self):
        asked = []
        with mock.patch.object(build, "fetch", lambda url, **options: asked.append(url) or sample(url)), \
                mock.patch.object(build, "today", lambda: date(2026, 6, 1)):  # Its sample's events are all past the window then.
            build.read_ica(source("ica", "https://www.icaboston.org/calendar", "art", "ICA"))
        self.assertEqual(asked, ["https://www.icaboston.org/calendar"])


class About(unittest.TestCase):
    """What a source says about an event, for its preview."""

    def test_short_facts_run_together_and_links_go(self):
        self.assertEqual(
            build.about("<p>Doors 7pm</p><p>21+</p><p>$10 cover</p><p>Event page:</p><p>Buy tickets</p>"
                        "<p>Some Band</p><p>someband.bandcamp.com</p><p>https://example.com/show</p>"),
            ["Doors 7pm · 21+ · $10 cover"])

    def test_a_sentence_cut_by_a_line_break_is_whole(self):
        self.assertEqual(build.about("A folk singer redefining the genre through a<br>powerful blend of soul.<br>Doors 7"),
                         ["A folk singer redefining the genre through a powerful blend of soul.", "Doors 7"])

    def test_a_line_repeating_the_name_is_left_out(self):
        item = build.event(source("tribe", "x"), "The 4411", date(2026, 9, 13), about=["The 4411", "Ages: All Ages"])
        self.assertEqual(item["about"], ["Ages: All Ages"])

    def test_from_the_samples(self):
        with mock.patch.object(build, "fetch", sample):
            midway = build.read_ics(source("ics", "https://tockify.com/api/feeds/ics/midwaycafejp"))[0]
            brattle = build.read_jsonld(source("jsonld", "https://brattlefilm.org/coming-soon/", "film"))[0]
            coolidge = build.read_coolidge(source("coolidge", "https://coolidge.org/showtimes", "film"))[0]
            roadrunner = build.read_aeg(source("aeg", "https://aegwebprod.blob.core.windows.net/json/events/219/events.json"))[0]
        self.assertEqual(midway["about"], ["Doors at 9:30pm · Show at 10:15 pm · 21+ · $10 cover · cash only venue"])
        # The Brattle's own description is just the dates, so its film's credits stand in.
        self.assertEqual(brattle["about"], ["Directed by Rafael Manuel. With Carlos Siguion-Reyna, Jorrybell Agoto, Nour Hooshmand.",
                                            "Drama, Mystery · 1h 40m · Tagalog with English subtitles"])
        self.assertEqual(coolidge["about"][-1], "1hr 38mins")
        self.assertTrue(roadrunner["about"][0].startswith("For a while there, Charles Wesley Godwin"), "the bio, not the ticket note")


class ArtAndTalks(unittest.TestCase):
    """The art & talks readers, on a fixed day, since their samples' exhibitions open and close on real dates."""

    def setUp(self):
        for name, value in [("fetch", sample), ("today", lambda: date(2026, 9, 12))]:
            patcher = mock.patch.object(build, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def titles(self, found):
        return [item["title"] for item in found]

    def test_mit_keeps_public_art_and_humanities(self):
        found = Readers.read(self, "mit", "https://calendar.mit.edu/api/2/events", "art")
        titles = self.titles(found)
        self.assertEqual(titles, ["Overburden with Gregg Mitman", "TAKK—Mireia Luzárraga", "Art21 Screening with Josh Kline"])
        self.assertEqual(found[0]["times"], [time(16, 0)])
        # Left out: a virtual conference, a talk in New York, and a talk and an exhibition for MIT people only.

    def test_mit_exhibition_listed_once_when_it_opens(self):
        # The sample's running exhibition, which MIT lists for its own community, made public.
        data = __import__("json").loads(sample("calendar.mit.edu"))
        for entry in data["events"]:
            entry["event"]["filters"]["event_audience"] = [{"name": "Public", "id": 98747}]
        public = __import__("json").dumps(data)
        with mock.patch.object(build, "today", lambda: date(2026, 8, 1)), mock.patch.object(build, "fetch", lambda url: public):
            found = build.read_mit(source("mit", "https://calendar.mit.edu/api/2/events", "art", "MIT"))
        opening = [item for item in found if item["title"].startswith("Howe, Manning & Almy")]
        self.assertEqual(len(opening), 1)
        self.assertEqual((opening[0]["date"], opening[0]["times"], opening[0]["detail"]), (date(2026, 8, 19), [], "through May 27"))

    def test_library_talks_by_branch(self):
        found = Readers.read(self, "bibliocommons", "https://gateway.bibliocommons.com/v2/libraries/bpl/rss/events?types=test",
                             "art", "Boston Public Library")
        venues = {item["title"]: item["venue"] for item in found}
        self.assertEqual(venues["Author Talk: N.K. Jemisin on Revolutionary Ideas in Fantasy Fiction"], "Boston Public Library")
        self.assertEqual(venues["Author Talk: Ric Calleja - Making Dinner con Amor"], "Faneuil Library")
        self.assertIn("Great Decisions — Multilateral Institutions", venues)
        # Left out: a virtual business class, a teens' workshop, and an exhibition open since last year.
        self.assertFalse([title for title in venues if "Tech Talk" in title or "Adulting" in title or "Becoming Boston" in title])

    def test_a_library_exhibition_once_and_all_day_not_at_midnight(self):
        def day(n, title="Places Known and Remembered: An Art Exhibition by \ufeffLaura Gatzos", tag="Exhibitions"):
            start = datetime(2026, 11, n, 5, tzinfo=timezone.utc)  # Midnight in Boston, to the next midnight.
            return (f"<item><title><![CDATA[{title}]]></title><link>https://bpl.bibliocommons.com/events/{n}</link>"
                    f"<category><![CDATA[{tag}]]></category><bc:start_date>{start:%Y-%m-%dT%H:%M:%SZ}</bc:start_date>"
                    f"<bc:end_date>{start + timedelta(hours=23, minutes=59, seconds=59):%Y-%m-%dT%H:%M:%SZ}</bc:end_date>"
                    f"<bc:end_date_local>2026-11-{n}</bc:end_date_local><bc:location><bc:name>West Roxbury</bc:name>"
                    f"</bc:location></item>")
        feed = "<rss>" + day(21) + day(22) + day(23) + day(22, "Knitting Circle", "Visual Arts") + "</rss>"
        pages = lambda url: feed if url.endswith("page=1") else "<rss></rss>"
        with mock.patch.object(build, "today", lambda: date(2026, 11, 21)), mock.patch.object(build, "fetch", pages):
            found = build.read_bibliocommons(source("bibliocommons", "https://gateway.bibliocommons.com/x?types=t", "art", "Boston Public Library"))
        shown = {(item["title"], item["date"], tuple(item["times"]), item["detail"], item["venue"]) for item in found}
        self.assertEqual(shown, {
            ("Places Known and Remembered: An Art Exhibition by Laura Gatzos", date(2026, 11, 21), (), "through Nov 23",
             "West Roxbury Library"),  # Once, without the mark hidden in its name.
            ("Knitting Circle", date(2026, 11, 22), (), "", "West Roxbury Library"),  # All day, not 12am.
        })

    def test_mfa_programs_by_kind(self):
        # Each kind from its own page, which says what it is: no guided tours or studio classes to skip.
        found = build.read_mfa(source("mfa", "https://www.mfa.org/programs", "art", "MFA"))
        self.assertEqual({item["title"]: item["category"] for item in found}, {
            "The Road to Livres d’Artiste": "art",
            "Dalí and the Book": "art",
            "$5 Third Thursday": "art",
            "First Fridays": "art",
            "Deep Quiet Room (深度安靜)": "film",
            "Dust in the Wind (戀戀風塵)": "film",
            "Lucky Lu (幸福之路)": "film",
            "Camelia Latin-Jazz Trio": "music",
        })
        self.assertEqual(found[0]["times"], [time(13, 0)])

    def test_ica_by_kind(self):
        found = build.read_ica(source("ica", "https://www.icaboston.org/calendar", "art", "ICA"))
        self.assertEqual({item["title"]: item["category"] for item in found}, {
            "Gallery Talk: Erika Umali on To My Best Friend": "art",
            "Colin Stetson & Brìghde Chaimbeul": "music",
            "TCB – The Toni Cade Bambara School of Organizing": "film",
        })  # Not the kids' workshop, the members' opening, or the online series.
        talk = found[0]
        self.assertEqual((talk["date"], talk["times"]), (date(2026, 9, 20), [time(14, 0)]))
        # Its concert's own page gives what it's about and what tickets cost; the talk's, not saved here, nothing.
        concert = next(item for item in found if item["category"] == "music")
        self.assertTrue(concert["about"][0].startswith("Colin Stetson and Brìghde Chaimbeul come together"))
        self.assertEqual(concert["about"][-1], "$30 ICA members / $35 students / $40 nonmembers")
        self.assertEqual(talk["about"], [])

    def test_times_from_a_range(self):
        for when, start in [("12–4 PM", time(12, 0)), ("10 AM–5 PM", time(10, 0)), ("5:30–9:30 PM", time(17, 30)),
                            ("7 PM", time(19, 0)), ("11–1 PM", time(11, 0)), ("8 PM–12 AM", time(20, 0))]:
            self.assertEqual(build.clock_range_start(when), start, when)

    def test_harvard_art_museums(self):
        listings = __import__("json").loads((FIXTURES / "harvardart.json").read_text())
        with mock.patch.object(build, "harvard_art_listings", lambda url, months: listings):
            found = build.read_harvard_art(source("harvardart", "https://harvardartmuseums.org/calendar", "art", "Harvard Art Museums"))
        titles = self.titles(found)
        self.assertIn("Decompress with Rocky Mountains, “Lander’s Peak”", titles)
        self.assertIn("Exhibition Opening Program for The Way We Never Were: Barbara Norfleet and Photography at Harvard", titles)
        self.assertFalse([title for title in titles if "Spotlight Tour" in title or "Online" in title])
        conserving = next(item for item in found if item["title"].startswith("Art + Science"))
        self.assertEqual((conserving["date"], conserving["times"]), (date(2026, 9, 15), [time(12, 0)]))


class Films(unittest.TestCase):
    def test_film_key_matches_spellings(self):
        year = datetime.now(build.BOSTON).year
        self.assertEqual(build.film_key("Coyote vs. ACME"), build.film_key("Coyote vs. Acme"))
        self.assertEqual(build.film_key("The Odyssey (Digital)"), build.film_key("The Odyssey"))
        self.assertEqual(build.film_key("Akira (4K Restoration)"), build.film_key("Akira"))
        self.assertEqual(build.film_key(f"Tony ({year})"), build.film_key("Tony"))
        self.assertNotEqual(build.film_key("Hope (1987)"), build.film_key(f"Hope ({year})"))

    def test_combine_films(self):
        day = date(2026, 9, 20)
        showing = lambda title, venue, hour: {  # noqa: E731
            "title": title, "date": day, "times": [time(hour)], "link": "https://x", "detail": "",
            "venue": venue, "category": "film", "source": venue,
        }
        rows = build.combine_films([
            showing("Coyote vs. ACME", "Alamo Drafthouse", 15),
            showing("Coyote vs. Acme", "Coolidge Corner", 14),
            showing("Paris, Texas", "Brattle", 19),
        ])
        combined = [row for row in rows if "showings" in row]
        self.assertEqual(len(combined), 1)
        self.assertEqual(combined[0]["title"], "Coyote vs. Acme", "the plainer spelling")
        self.assertEqual(combined[0]["times"], [time(14)], "from its earliest showing")
        self.assertEqual(len(rows), 2)


class OneNight(unittest.TestCase):
    """Films there's one chance to see, in all of what's listed, and only where the listing can say so."""

    built = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)

    def film(self, title, venue, days_ahead, times=(19,)):
        return {"title": title, "date": date(2026, 9, 20) + timedelta(days=days_ahead), "times": [time(h) for h in times],
                "link": "x", "detail": "", "venue": venue, "source": venue, "category": "film", "about": []}

    def schedule(self, venue, through, gaps=()):
        """The rest of a theater's listing: a film on every day through a day, but for some days dark."""
        return [self.film(f"Long Run at {venue}", venue, day) for day in range(through + 1) if day not in gaps]

    # Remembering since well before any of these, with nothing remembered of them.
    REMEMBERED = {"since": "2026-08-01", "films": {}}

    def test_a_film_on_once_at_a_theater_that_has_published_well_past_it(self):
        events = [self.film("Bullitt", "Brattle", 2)] + self.schedule("Brattle", 14)
        self.assertEqual(build.one_nights(events, self.REMEMBERED), {"2026-09-22-bullitt-brattle"})

    def test_not_the_last_showing_of_a_run(self):
        """A film listed on the days before its one showing still to come was on for a run, not one night."""
        events = [self.film("Long Film", "Brattle", 2)] + self.schedule("Brattle", 14)
        ran = {"since": "2026-08-01", "films": {"long film": ["2026-09-10", "2026-09-15", "2026-09-19"]}}
        self.assertEqual(build.one_nights(events, ran), set())
        # A revival weeks after an earlier run is a night of its own.
        revived = {"since": "2026-08-01", "films": {"long film": ["2026-08-20", "2026-08-21"]}}
        self.assertEqual(build.one_nights(events, revived), {"2026-09-22-long-film-brattle"})

    def test_not_so_soon_after_the_remembering_began_that_what_came_before_is_unknown(self):
        just_begun = {"since": "2026-09-20", "films": {}}
        soon = [self.film("Bullitt", "Brattle", 2)] + self.schedule("Brattle", 20)
        later = [self.film("Bullitt", "Brattle", 9)] + self.schedule("Brattle", 20)
        self.assertEqual(build.one_nights(soon, just_begun), set(), "the week before it went unwatched")
        self.assertEqual(build.one_nights(later, just_begun), {"2026-09-29-bullitt-brattle"}, "the week before is listed")

    def test_not_where_the_theater_hasnt_published_far_enough_to_know(self):
        """A theater listing a week ahead hasn't said whether Thursday's new release is on again Monday."""
        events = [self.film("New Release", "Kendall", 4)] + self.schedule("Kendall", 8)
        self.assertEqual(build.one_nights(events, self.REMEMBERED), set())

    def test_a_gala_a_month_off_doesnt_count_as_publishing_that_far(self):
        events = [self.film("New Release", "Cinema", 2)] + self.schedule("Cinema", 6) + [self.film("Gala", "Cinema", 30)]
        self.assertNotIn("2026-09-22-new-release-cinema", build.one_nights(events, self.REMEMBERED))
        # Dark a few days a week, as a repertory house is, is still publishing.
        events = [self.film("Bullitt", "Archive", 2)] + self.schedule("Archive", 16, gaps={5, 6, 7, 12, 13, 14})
        self.assertIn("2026-09-22-bullitt-archive", build.one_nights(events, self.REMEMBERED))

    def test_not_a_film_on_twice_anywhere(self):
        twice_a_day = [self.film("Bullitt", "Brattle", 2, times=(16, 19))] + self.schedule("Brattle", 14)
        two_theaters = [self.film("Bullitt", "Brattle", 2), self.film("Bullitt", "Coolidge", 9)] + self.schedule("Brattle", 14)
        self.assertEqual(build.one_nights(twice_a_day, self.REMEMBERED), set())
        self.assertEqual(build.one_nights(two_theaters, self.REMEMBERED), set())

    def test_tagged_from_the_whole_listing_on_every_page(self):
        """Tonight's page has only today's showing of a film on all week; it isn't its one night."""
        brattle = dict(source("aeg", "x", "film", "Brattle"), public=True)
        week = [build.event(brattle, "On All Week", date(2026, 9, 20) + timedelta(days=d), time(19)) for d in range(15)]
        once = build.event(brattle, "Bullitt", date(2026, 9, 20), time(21))
        tonight = build.render_index(week + [once], [brattle], [], [], self.built, public=True, tonight=True,
                                     days_seen=self.REMEMBERED)
        self.assertEqual(tonight.count('<span class="once-tag">One night</span>'), 1)
        self.assertLess(tonight.index(">Bullitt<"), tonight.index('<span class="once-tag">'))
        # Its row marked for One night only, a switch in the Filters chip's panel, which this page has, having a film
        # showing once; not Free, having nothing free.
        self.assertIn('data-sources="Brattle" data-once>', tonight)
        self.assertIn('<button class="filters-open" type="button" popovertarget="filters" aria-haspopup="dialog">', tonight)
        self.assertIn('<label class="filters-choice" data-key="once"><input type="checkbox" name="once" data-mark="once" data-kinds="film">'
                      '<span>One night only<small>Films showing just once</small></span></label>', tonight)
        self.assertNotIn('data-key="free"', tonight)
        self.assertIn("&& [...chosen].every(key => KEEPS[key](li))", tonight)

    def test_the_film_pages_lead_lists_them_beside_its_biggest_film(self):
        """Over the film page, the films showing once in the announcements' place, soonest first, its heading a
        way to all of them (?once=1); the home page has it too, hidden, for its films shown in place."""
        brattle = dict(source("aeg", "x", "film", "Brattle"), public=True)
        sinclair = dict(source("aeg", "x", "music", "The Sinclair"), public=True)
        week = [build.event(brattle, "On All Week", date(2026, 9, 20) + timedelta(days=d), time(19)) for d in range(15)]
        once = [build.event(brattle, "The Matrix", date(2026, 9, 24), time(21)), build.event(brattle, "Bullitt", date(2026, 9, 22), time(21))]
        band = [build.event(sinclair, "A Band", date(2026, 9, 22), time(20))]
        film = build.render_index(week + once, [brattle], [], [], self.built, public=True, category="film", days_seen=self.REMEMBERED)
        start = film.index('<div class="lead')
        lead = film[start:film.index("</div>\n<script>", start)]
        self.assertIn("One night only</a>", lead)
        self.assertIn(f'href="{R}film/?once=1">See all →</a>', lead)
        self.assertLess(lead.index(">Bullitt<"), lead.index(">The Matrix<"), "soonest first")
        self.assertNotIn("On All Week", lead.split('class="fresh"')[1])
        # On film's own page, the Filters chip, with One night only in its panel.
        self.assertIn('class="filters-open"', film)
        self.assertIn('data-key="once"', film)
        home =build.render_index(week + once + band, [brattle, sinclair], [], [], self.built, public=True, days_seen=self.REMEMBERED)
        self.assertNotIn("One night only</a>", home, "the home page's lead stays as it is whatever kind it shows")
        self.assertNotIn('data-kind=', home)
        music = build.render_index(band, [sinclair], [], [], self.built, public=True, category="music", days_seen=self.REMEMBERED)
        self.assertNotIn('data-key="once"', music, "no films there to narrow to")


class FilmDays(unittest.TestCase):
    """What's remembered of each city's films from build to build."""

    def test_today_added_to_what_was_remembered_and_the_old_let_go(self):
        built = datetime(2026, 11, 20, 16, 0, tzinfo=timezone.utc)
        brattle = dict(source("aeg", "x", "film", "Brattle"), city="boston")
        before = {"boston": {"since": "2026-08-01", "films": {"bullitt": ["2026-08-15", "2026-11-10"], "gone": ["2026-08-02"]}}}
        today = [build.event(brattle, "Bullitt", date(2026, 11, 21), time(19)),
                 build.event(brattle, "Paris, Texas", date(2026, 11, 22), time(19))]
        kept = build.film_days(before, today, [brattle], built)["boston"]
        self.assertEqual(kept["films"], {"bullitt": ["2026-11-10", "2026-11-21"], "paris texas": ["2026-11-22"]},
                         "past FILM_DAYS_KEPT let go, and a film with nothing left forgotten")
        self.assertEqual(kept["since"], "2026-09-21", "remembered only as far back as what's kept")

    def test_remembering_begins_with_the_first_build_that_does(self):
        built = datetime(2026, 11, 20, 16, 0, tzinfo=timezone.utc)
        brattle = dict(source("aeg", "x", "film", "Brattle"), city="boston")
        kept = build.film_days({}, [build.event(brattle, "Bullitt", date(2026, 11, 21), time(19))], [brattle], built)
        self.assertEqual(kept, {"boston": {"since": "2026-11-20", "films": {"bullitt": ["2026-11-21"]}}})


class VenueMenu(unittest.TestCase):
    """The venues under the towns they're in, a town with more than one led by the whole of it."""

    def test_grouped_by_town_the_busiest_first(self):
        towns = {"The Sinclair": "Cambridge", "The Brattle": "Cambridge", "Paradise": "Boston", "Deep Cuts": "Medford"}
        events = [{"source": name} for name in ("The Sinclair", "The Brattle", "The Brattle", "Paradise", "Deep Cuts")]
        menu = build.venue_menu(set(towns) | {"Somewhere"}, towns, events)
        self.assertTrue(menu.startswith('<select class="pick" aria-label="Venue"><option value="">All venues</option>'
                                        '<optgroup label="Cambridge"><option value="town:Cambridge">All of Cambridge</option>'
                                        '<option value="The Brattle" data-name="The Brattle">Brattle</option>'
                                        '<option value="The Sinclair" data-name="The Sinclair">Sinclair</option></optgroup>'),
                        "filed under what follows its The, so typing its name finds it")
        self.assertIn("name = option.dataset.name || option.textContent.trim();", build.INDEX_JS, "shown whole once chosen")
        self.assertIn('<optgroup label="Medford"><option value="Deep Cuts">Deep Cuts</option></optgroup>', menu,
                      "no All of Medford, with one venue in it")
        self.assertTrue(menu.endswith('<option value="Somewhere">Somewhere</option></select>'), "no known town, last")

    def test_choosing_a_town_shows_all_of_it(self):
        self.assertIn('venue.value.startsWith("town:")', build.INDEX_JS)
        self.assertIn("TOWNS[source] === venue.value.slice(5)", build.INDEX_JS)


class HomePage(unittest.TestCase):
    """How the home page reads: its line beside the site's name, and each day one list in the order of the day."""

    built = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)

    def page(self, **kinds):
        venue = dict(source("aeg", "x", "music", "The Sinclair"), public=True)
        day = date(2026, 9, 21)
        events = [build.event(dict(venue, category="film"), "Matinee", day, time(12)),
                  build.event(venue, "Late Show", day, time(21)),
                  build.event(dict(venue, category="art"), "A Talk", day, time(18)),
                  build.event(venue, "Early Show", day, time(19))]
        return build.render_index(events, [venue], [], [], self.built, public=True, **kinds)

    def test_a_day_is_one_list_in_the_order_of_the_day(self):
        """Every kind together, a film beside a concert beside a talk, by when each is."""
        page = self.page()
        section = page[page.index('<section class="day"'):page.index("</section>")]
        self.assertEqual(section.count("<ul"), 1)
        order = [section.index(f">{name}<") for name in ("Matinee", "A Talk", "Early Show", "Late Show")]
        self.assertEqual(order, sorted(order))

    def test_tonight_and_this_weekend_beside_the_kinds(self):
        """In the filter on every page, not just the footer, as a When menu beside Where's, which says the page's
        own where it's one of them. Their links are still in the page, unseen, which the menu works through."""
        R = build.PUBLIC_ROOT
        home = self.page()
        self.assertIn('<span class="pick-box"><span class="pick-said" aria-hidden="true">When</span>'
                      '<select class="pick when-pick" aria-label="When"><option value="">Any day</option>'
                      '<option value="tonight">Tonight</option><option value="tomorrow">Tomorrow</option>'
                      '<option value="0">This weekend</option><option value="1">Next weekend</option>', home)
        # And under Pick a day, each day after tomorrow with listings, in the menu itself: no calendar of its own.
        # Here there's only tomorrow, so no days to pick.
        self.assertIn('<option value="1">Next weekend</option><option value="picked" hidden></option></select></span>', home)
        self.assertNotIn('type="date"', home)
        venue = dict(source("aeg", "x", "music", "The Sinclair"), public=True)
        later = build.render_index([build.event(venue, "Later Show", date(2026, 9, 25), time(20)),
                                    build.event(venue, "Tomorrow's", date(2026, 9, 21), time(20))], [venue], [], [], self.built, public=True)
        self.assertIn('<optgroup label="Pick a day"><option value="date:2026-09-25">Fri, Sep 25</option></optgroup>', later,
                      "the days after tomorrow with something on, each by its name")
        # Tomorrow and a day picked have no page: the home page shows them in place, in its address as the rest
        # (?when=tomorrow, ?date=2026-12-05), from another page too; and Where has only that day's venues.
        self.assertIn('if (which === "tomorrow") return [plusDays(today, 1), plusDays(today, 1)];', build.INDEX_JS)
        self.assertIn('if (when.dataset.when.startsWith("date:")) kept.set("date", when.dataset.when.slice(5));', build.INDEX_JS)
        self.assertIn("option.disabled = option.hidden = !on;", build.INDEX_JS)
        self.assertLess(home.index('aria-label="When"'), home.index('aria-label="Venue"'), "When beside Where, before it")
        self.assertIn(f'<span class="when-links" hidden><a href="{R}tonight/" data-when="tonight" tabindex="-1">Tonight</a>'
                      f'<a href="{R}weekend/" data-when="0" tabindex="-1">This weekend</a>'
                      f'<a class="later" href="{R}weekend/next/" data-when="1" tabindex="-1">Next weekend</a></span>', home)
        tonight = self.page(tonight=True)
        self.assertIn(f'<a href="{R}tonight/" data-when="tonight" aria-current="page" tabindex="-1">Tonight</a>', tonight)
        self.assertIn('<option value="tonight" selected>Tonight</option>', tonight)
        self.assertIn('<option value="0" selected>This weekend</option>', self.page(weekend=0))
        following = self.page(weekend=1)
        self.assertNotIn('<option value="0" selected>', following, "next weekend's isn't this one")
        self.assertIn(f'<a class="later" href="{R}weekend/next/" data-when="1" aria-current="page" tabindex="-1">Next weekend</a>', following)
        self.assertIn('if (inPlace) { showWhen(link || (day ? dayWhen(key) : null)); return; }', build.INDEX_JS)
        # The home page shows them in place, Just announced and the film still over the list, and a weekend with
        # the way to the other one under it, hidden until then.
        self.assertIn(f'<nav class="weekends" data-on="0" hidden><span></span><a href="{R}weekend/next/" data-to="1">', home)
        self.assertIn(f'<nav class="weekends" data-on="1" hidden><a href="{R}weekend/" data-to="0">', home)
        self.assertNotIn("data-on=", self.page(weekend=0))
        self.assertIn("if (w) { event.preventDefault(); showWhen(w === when ? null : w); return; }", build.INDEX_JS)
        self.assertIn(".when-links { display: none; }", home)
        # The one the page is goes back to every day when it's pressed again.
        self.assertIn('filter.querySelectorAll(".when-links a[aria-current]")) a.dataset.href = new URL(SHARE_URL).pathname;',
                      build.INDEX_JS)
        # And a phone's row goes back to its start, where When, Where and Filters say what's chosen.
        self.assertIn("if (row.scrollWidth > row.clientWidth) row.scrollLeft = 0;", build.INDEX_JS)

    def test_the_bars_shadow_is_never_over_a_days_heading(self):
        """A heading right under the bar but not held there yet (a phone's first day as the bar sticks, where the
        page goes back to when a kind is chosen) counts as the bar's heading, so the bar's shadow doesn't dim it."""
        self.assertIn("const near = h2.offsetParent !== null && box.bottom > under && box.top - under < 22;", build.INDEX_JS)
        self.assertIn("pinned ||= on || near;", build.INDEX_JS)

    def test_a_venue_chosen_leads_a_phones_chips_and_a_chip_is_pressed_over_44_pixels(self):
        """What's chosen at the end of a row that's swiped along would be off the screen: a venue chosen is the
        row's first chip. And a chip takes a press over more than is drawn of it, in the row's own padding."""
        home = self.page()
        self.assertIn(".filter .chips .pick-box.chosen { order: -1; }", home)
        self.assertIn(".filter .chips::before { order: -2; }", home, "the margin before the row stays before it")
        self.assertIn('.filter .chips [data-show]::after, .filter .when-links a::after, .filter .filters-open::after {\n      content: ""; position: absolute; '
                      "inset: -7px -.2rem; }", home)
        self.assertIn("margin: -6px -1rem;\n                     padding: 6px 0;", home, "32 pixels drawn, 44 to press")
        # The bar is measured from a chip, not the row, whose padding isn't the bar's.
        self.assertIn('filter.querySelector(".chips [data-show]").getBoundingClientRect().top', build.INDEX_JS)

    def test_each_kind_in_the_filter_is_led_by_its_mark(self):
        """In its color, which the list's times are in: the filter is the key to them. All has none."""
        home, R = self.page(), build.PUBLIC_ROOT
        self.assertIn(f'<a data-show="all" href="{R}" aria-current="page">All</a>', home)
        self.assertIn(f'<a data-show="film" href="{R}film/"><svg class="icon" aria-hidden="true"><use href="#icon-film"/></svg>Film</a>', home)
        tonight = self.page(tonight=True)
        self.assertIn('<button data-show="music"><svg class="icon" aria-hidden="true"><use href="#icon-music"/></svg>Music</button>', tonight)
        self.assertIn(".filter [data-show] > .icon { width: 13px; height: 13px; margin-right: .4em; vertical-align: -1px; }", home)

    def test_on_a_phone_the_filter_is_a_search_box_over_a_row_of_chips(self):
        """The kinds, when and where are wrapped together, to be one row a phone swipes along; the search after
        them, which a phone puts above. When is a menu as Where is, beside it."""
        home = self.page()
        bar = home[home.index('<nav class="filter"'):home.index("</nav>", home.index('<nav class="filter"'))]
        chips, finders = bar.index('<span class="chips">'), bar.index('<span class="finders">')
        self.assertLess(chips, bar.index('data-show="all"'))
        self.assertLess(bar.index('class="when-links"'), bar.index('aria-label="Venue"'))
        self.assertLess(bar.index('aria-label="Venue"'), finders, "the venue's menu with the chips, not with the search")
        self.assertLess(finders, bar.index('class="search"'))
        self.assertIn('<span class="pick-box"><span class="pick-said" aria-hidden="true">Where</span><select class="pick" aria-label="Venue">', bar)
        self.assertLess(bar.index('class="pick when-pick"'), bar.index('aria-label="Venue"'))
        self.assertIn("@media (max-width: 34rem) { .filter .chips .pick-box, .filter .chips .filters-open { order: -1; } }", home,
                      "on a phone, When, Where and Filters first, where they're seen without swiping")
        self.assertIn(".chips { display: contents; gap: inherit; }", home, "a wide screen's bar holds them itself")

    def test_the_search_says_what_can_be_searched_for(self):
        """The page says "Search"; the script, what for, the box having the width on a phone and a wide screen."""
        self.assertIn('<input class="search" type="search" placeholder="Search" data-hint="Search artists, films, venues" '
                      'aria-label="Search"', self.page())
        self.assertIn('search.closest(".finders").clientWidth > 280 ? search.dataset.hint : "Search"', build.INDEX_JS,
                      "where its box has the room for it")

    def test_a_wide_screens_filter_is_a_phones(self):
        """The search's box over a row of chips at every width, and its line put away on the way down as a phone's is."""
        home = self.page()
        self.assertIn("@media all {\n    /* Two rows, each a shape of its own", home)
        # But a wide screen's search at the end of the chips' line, not a row the page's width.
        self.assertIn("body .filter .finders { order: 1; flex: 1 0 9rem; max-width: 16rem; margin-left: auto; }", home)
        self.assertIn("const lift = Math.max(0, Math.ceil(", build.INDEX_JS)
        self.assertNotIn("on = on && phone.matches;", build.INDEX_JS)

    def test_the_home_pages_line_is_in_its_header_and_a_kind_pages_under_it(self):
        home = self.page()
        header = home[home.index("<header>"):home.index("</header>")]
        self.assertIn('<h1 class="tagline">Concerts, films, and talks around Boston.</h1>', header, "beside the name")
        self.assertEqual(home.count("<h1"), 1, "still the page's one heading")
        film = self.page(category="film")
        self.assertNotIn("<h1", film[film.index("<header>"):film.index("</header>")], "a sentence, on a line of its own")
        self.assertIn('<h1 class="tagline">', film)


# A poster from one of the places films' own art comes from (PICTURE_HOSTS).
POSTER = "https://image.tmdb.org/t/p/w342/poster.jpg"


class PictureSize(unittest.TestCase):
    """The build can't make a picture smaller, so one too big to copy (a megabyte for a box 160 pixels wide)
    isn't used at all."""

    class Answer:
        def __init__(self, size):
            self.size = size

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, most):
            return b"\xff\xd8\xff" + b"x" * (min(self.size, most) - 3)

    def setUp(self):
        build._pictures.clear()
        self.addCleanup(build._pictures.clear)

    def test_up_to_the_most_is_kept_and_past_it_isnt(self):
        with mock.patch.object(build.urllib.request, "urlopen", return_value=self.Answer(build.PICTURE_MOST)):
            self.assertEqual(len(build.picture_bytes("https://x/fits.jpg")), build.PICTURE_MOST)
        with mock.patch.object(build.urllib.request, "urlopen", return_value=self.Answer(build.PICTURE_MOST + 1)):
            self.assertIsNone(build.picture_bytes("https://x/too-big.jpg"))
            self.assertIsNone(build.picture_shape("https://x/too-big.jpg"), "so it has no shape, and isn't shown")

    def test_a_webps_shape_whichever_kind_it_is(self):
        """Quad Cinema's stills are WebP's plain kind, which says its size differently from the extended one."""
        plain = b"RIFF\x00\x00\x00\x00WEBPVP8 \x00\x00\x00\x00\x00\x00\x00\x9d\x01\x2a" + (640).to_bytes(2, "little") + (372).to_bytes(2, "little")
        lossless = b"RIFF\x00\x00\x00\x00WEBPVP8L\x00\x00\x00\x00\x2f" + ((640 - 1) | ((372 - 1) << 14)).to_bytes(4, "little")
        for name, data in (("plain", plain), ("lossless", lossless)):
            with mock.patch.object(build, "picture_bytes", return_value=data + b"\x00" * 16):
                self.assertEqual(build.picture_shape(f"https://x/{name}.webp"), (640, 372), name)

    def test_tmdbs_smaller_poster(self):
        self.assertEqual(build.lighter("https://image.tmdb.org/t/p/w780/a.jpg"), "https://image.tmdb.org/t/p/w342/a.jpg")
        self.assertEqual(build.lighter("https://image.tmdb.org/t/p/w342/a.jpg"), "https://image.tmdb.org/t/p/w342/a.jpg")


class Biggest(unittest.TestCase):
    """The week's biggest film: the one the most of a city's theaters have taken."""

    built = datetime(2026, 9, 20, 16, 0, tzinfo=timezone.utc)

    def setUp(self):
        # A picture's shape is read from the picture itself, which a test doesn't go and fetch; nor does it fetch
        # the picture to copy it, so the page points at the theater's.
        for name, value in (("picture_shape", (780, 1170)), ("picture_bytes", None)):
            patch = mock.patch.object(build, name, return_value=value)
            patch.start()
            self.addCleanup(patch.stop)
        build.KEPT_PICTURES.clear()

    def showing(self, title, venue, days_ahead=0, hour=19, image=""):
        return {"title": title, "date": date(2026, 9, 20) + timedelta(days=days_ahead), "times": [time(hour)],
                "link": "https://x", "detail": "", "venue": venue, "source": venue, "category": "film",
                "about": [], "image": image}

    def biggest(self, events, before=""):
        film = build.biggest_film(events, self.built, before)
        return film["title"] if film else None

    def test_the_film_at_the_most_theaters(self):
        events = [self.showing("Wide Release", f"Theater {n}") for n in range(5)]
        events += [self.showing("Smaller", f"Theater {n}") for n in range(3)]
        film = build.biggest_film(events, self.built)
        self.assertEqual((film["title"], film["theaters"], film["day"]), ("Wide Release", 5, date(2026, 9, 20)))
        self.assertEqual(film["id"], "2026-09-20-wide-release", "its row's address on the page")

    def test_its_day_is_a_date_the_page_names(self):
        """Today as of the build, written in so it's there as the page first shows rather than swapped in once the
        script has run; the script names the day again by the reader's clock, as it does the days' headings, and
        goes back to the date itself (data-said) for a page read after midnight."""
        events = [self.showing("Wide Release", f"Theater {n}") for n in range(4)]
        lead, _ = build.render_lead(events, self.built)
        self.assertIn('<span class="biggest-facts"><span class="lead-day" data-date="2026-09-20" data-said="Sun, Sep 20">Today</span>'
                      ' · 4 theaters</span>', lead, "the day first, as a listing's small line has it")
        self.assertIn(f'<b class="biggest-title">{build.FILM_MARK}Wide Release</b>', lead, "its kind's mark before its name, as a row's")
        later, _ = build.render_lead(events, self.built - timedelta(days=2))
        self.assertIn('data-said="Sun, Sep 20">Sun, Sep 20</span>', later, "not today or tomorrow: the date")
        self.assertIn('document.querySelectorAll(".lead-day")', build.INDEX_JS)
        self.assertIn("when.dataset.said", build.INDEX_JS)
        # Not a <time datetime>, which the shared script would take for a timestamp and show as an age ("18h").
        self.assertNotIn("datetime=", lead)

    def test_a_tie_goes_to_the_one_shown_more_and_never_to_the_order_read(self):
        busy = [self.showing("Busy Film", f"Theater {n}", hour=hour) for n in range(4) for hour in (13, 16, 19)]
        quiet = [self.showing("Quiet Film", f"Theater {n}") for n in range(4)]
        self.assertEqual(self.biggest(quiet + busy), "Busy Film")
        self.assertEqual(self.biggest(busy + quiet), "Busy Film")
        # Shown as often, too: by name, the same whichever is read first.
        twins = [self.showing(title, f"Theater {n}") for title in ("Beta", "Alpha") for n in range(4)]
        self.assertEqual(self.biggest(twins), "Alpha")
        self.assertEqual(self.biggest(twins[::-1]), "Alpha")

    def test_it_stays_until_something_is_bigger(self):
        """What leads the page changes when a bigger film turns up, not when another draws level with it."""
        level = [self.showing(title, f"Theater {n}") for title in ("Old Favorite", "Newcomer") for n in range(4)]
        self.assertEqual(self.biggest(level, before="old favorite"), "Old Favorite", "a tie keeps it")
        self.assertEqual(self.biggest(level, before="newcomer"), "Newcomer", "either way round")
        bigger = level + [self.showing("Newcomer", "Theater 9")]
        self.assertEqual(self.biggest(bigger, before="old favorite"), "Newcomer", "one more theater, and it's bigger")
        gone = [self.showing("Newcomer", f"Theater {n}") for n in range(4)]
        self.assertEqual(self.biggest(gone, before="old favorite"), "Newcomer", "and when it's no longer on")

    def test_the_bar_is_a_share_of_the_citys_own_theaters(self):
        """Three theaters is the week's biggest in a city with seven, and nothing much in one with twelve."""
        film = [self.showing("A Film", f"Theater {n}") for n in range(3)]
        small = film + [self.showing(f"Other {n}", f"Theater {n + 3}") for n in range(4)]
        large = film + [self.showing(f"Other {n}", f"Theater {n + 3}") for n in range(9)]
        self.assertEqual(self.biggest(small), "A Film")
        self.assertIsNone(self.biggest(large), "twelve theaters want four")
        # Never fewer than the floor, however few theaters a city has: two of five isn't everywhere.
        tiny = [self.showing("A Film", f"Theater {n}") for n in range(2)] + [self.showing("B", f"Theater {n}") for n in (2, 3, 4)]
        self.assertEqual(self.biggest(tiny), "B")

    def test_the_theaters_are_counted_a_day_at_a_time(self):
        """A film at two theaters a night all week isn't bigger than one at four tonight."""
        spread = [self.showing("All Week", f"Theater {n}", days_ahead=day) for day in range(5) for n in range(2)]
        tonight = [self.showing("Tonight Only", f"Big {n}") for n in range(4)]
        self.assertEqual(self.biggest(spread + tonight), "Tonight Only")

    def test_its_best_day_the_soonest_of_a_tie(self):
        events = [self.showing("Wide Release", f"Theater {n}", days_ahead=day) for day in (0, 3) for n in range(4)]
        self.assertEqual(build.biggest_film(events, self.built)["id"], "2026-09-20-wide-release")

    def test_a_quiet_week_has_none(self):
        self.assertIsNone(self.biggest([self.showing("A Revival", "Brattle"), self.showing("A Revival", "Coolidge Corner")]))
        self.assertIsNone(self.biggest([]))

    def test_a_films_own_art_beats_a_theaters_photograph(self):
        events = [self.showing("Wide Release", "Coolidge Corner", image="https://coolidge.org/lobby.jpg"),
                  self.showing("Wide Release", "Lexington Venue", image="https://image.tmdb.org/t/p/w780/a.jpg")]
        events += [self.showing("Wide Release", f"Theater {n}") for n in range(2)]
        self.assertEqual(build.biggest_film(events, self.built)["image"], "https://image.tmdb.org/t/p/w342/a.jpg",
                         "TMDB's smaller size of it")

    def test_a_poster_before_a_still_from_wherever_it_comes(self):
        """Alamo's still is the more preferred host, but West Newton's poster is the one shown."""
        still, poster = "https://img-assets.drafthouse.com/still.jpg", "https://img.vwassets.com/x/vertical_poster.jpg"
        shapes = {still: (1920, 1080), poster: (675, 1000)}
        events = [self.showing("Wide Release", "Alamo", image=still), self.showing("Wide Release", "West Newton", image=poster)]
        events += [self.showing("Wide Release", f"Theater {n}") for n in range(2)]
        with mock.patch.object(build, "picture_shape", side_effect=lambda url: shapes.get(url)):
            film = build.biggest_film(events, self.built)
        self.assertEqual((film["image"], film["standing"]), (poster, True))
        # With no poster, the still; and one that won't load or is too big to copy (no shape) is passed over.
        shapes[poster] = None
        with mock.patch.object(build, "picture_shape", side_effect=lambda url: shapes.get(url)):
            film = build.biggest_film(events, self.built)
        self.assertEqual((film["image"], film["standing"]), (still, False))

    def test_new_yorks_cinemas_own_stills_are_a_films_art(self):
        """Their pictures are each film's still, so the film has one there too: BAM's before the others, and
        Nitehawk's by its uploads' folder, not everything at Amazon."""
        bam = "https://www.bam.org/globalassets/programs/cinema/still.jpg?width=800&mode=crop&heightratio=0.5625&quality=80"
        nitehawk = "https://s3.amazonaws.com/nightjarprod/content/uploads/sites/3/2026/09/a-still-scaled.jpeg"
        quad = "https://quadcinema.com/wp-content/uploads/2026/10/you3-640x372.webp"
        events = [self.showing("Wide Release", "Nitehawk Williamsburg", image=nitehawk), self.showing("Wide Release", "Quad Cinema", image=quad),
                  self.showing("Wide Release", "BAM", image=bam), self.showing("Wide Release", "Elsewhere", image="https://s3.amazonaws.com/other/x.jpg")]
        shapes = {bam: (800, 450), nitehawk: None, quad: (640, 372), "https://s3.amazonaws.com/other/x.jpg": (800, 450)}
        with mock.patch.object(build, "picture_shape", side_effect=lambda url: shapes.get(url)):
            film = build.biggest_film(events, self.built)
            self.assertEqual((film["image"], film["standing"]), (bam, False))
            shapes[bam] = None  # BAM's won't load: Quad's, and never Nitehawk's, too big to copy.
            self.assertEqual(build.biggest_film(events, self.built)["image"], quad)
            shapes[quad] = None
            self.assertEqual(build.biggest_film(events, self.built)["image"], "", "not what else is at Amazon")

    def test_a_poster_borrowed_from_another_city_before_a_still_of_its_own(self):
        """New York's theaters give You Can See Everything only stills; Boston's give its poster."""
        quad = "https://quadcinema.com/wp-content/uploads/2026/10/you3-640x372.webp"
        poster, boston_still = "https://img.vwassets.com/x/vertical_poster.jpg", "https://img-assets.drafthouse.com/still.jpg"
        shapes = {quad: (640, 372), poster: (675, 1000), boston_still: (1920, 1080)}
        events = [self.showing("Wide Release", f"Theater {n}", image=quad) for n in range(4)]
        elsewhere = {build.film_key("Wide Release (2026)"): [boston_still, poster], build.film_key("Another Film"): ["https://img.vwassets.com/y/other.jpg"]}
        with mock.patch.object(build, "picture_shape", side_effect=lambda url: shapes.get(url)), \
                mock.patch.dict(build.FILM_PICTURES, elsewhere, clear=True):
            film = build.biggest_film(events, self.built)
            self.assertEqual((film["image"], film["standing"]), (poster, True), "the same film by its key, its poster")
            del shapes[poster]  # Another city's still is no better than its own.
            self.assertEqual(build.biggest_film(events, self.built)["image"], quad)
        self.assertEqual(build.film_pictures([dict(self.showing("Wide Release", "Brattle", image=poster), category="film"),
                                              dict(self.showing("A Band", "Sinclair", image="x"), category="music")]),
                         {"wide release": [poster]}, "only films' pictures, by film_key")

    def test_no_picture_rather_than_a_theaters_photograph_or_a_cropped_one(self):
        """Only a film's own art, and only where its shape is known: otherwise the film is words alone."""
        lobby = [self.showing("Wide Release", f"Theater {n}", image="https://coolidge.org/lobby.jpg") for n in range(4)]
        self.assertEqual(build.biggest_film(lobby, self.built)["image"], "")
        self.assertNotIn("<img", build.render_lead(lobby, self.built)[0])
        poster = [self.showing("Wide Release", f"Theater {n}", image=POSTER) for n in range(4)]
        with mock.patch.object(build, "picture_shape", return_value=None):  # It wouldn't load, so no shape.
            self.assertNotIn("<img", build.render_lead(poster, self.built)[0])

    def test_tonights_and_a_weekends_are_of_those_nights(self):
        """Over tonight's listings or a weekend's, the film and the announcements of those nights: one that's on
        another night isn't what's on then. Neither where there's nothing then; the home page's, hidden, for its
        script to show in place."""
        built = datetime(2026, 9, 17, 12, tzinfo=build.PUBLIC_ZONE)  # A Thursday: the weekend's the 18th to the 20th.
        tonight = (date(2026, 9, 17),) * 2
        weekend = build.weekend_days(date(2026, 9, 17))
        films = [self.showing("Saturday Film", f"Theater {n}", days_ahead=-1) for n in range(4)]
        announced = [dict(build.event(source("aeg", "x", "music", "The Sinclair"), "Tonight's Show", date(2026, 9, 17), time(21)),
                          added="2026-09-16"),
                     dict(build.event(source("aeg", "x", "music", "The Sinclair"), "Sunday Show", date(2026, 9, 20), time(20)),
                          added="2026-09-16")]
        week, _ = build.render_lead(films + announced, built)
        self.assertIn("Saturday Film", week)
        self.assertIn("Sunday Show", week)
        night, _ = build.render_lead(films + announced, built, days=tonight)
        self.assertIn("Tonight&#x27;s Show", night)
        self.assertNotIn("Saturday Film", night, "not tonight's")
        self.assertNotIn("Sunday Show", night)
        saturday, _ = build.render_lead(films + announced, built, days=weekend, when="0")
        self.assertIn('<div class="lead one" data-when="0">', saturday)
        self.assertIn("Saturday Film", saturday)
        self.assertNotIn("Sunday Show", saturday, "a weekend's has its film alone, nothing announced")
        self.assertNotIn('class="fresh"', saturday)
        self.assertEqual(build.render_lead(films, built, days=tonight), ("", ""))
        # The home page's: only the one chosen, taking no room for the others, which left a blank over tonight's
        # listings once its evening had gone by.
        self.assertIn('lead.classList.toggle("away", lead.dataset.when !== when?.dataset.when);', build.INDEX_JS)
        self.assertIn(".leads > .lead.away { display: none; }", build.render_index([], [], [], [], built, public=True))

    def test_the_film_a_card_beside_whats_announced(self):
        """The film a card with its poster, first; what's announced in words after it: on its right on a wide
        screen, under it on a phone."""
        films = [self.showing("Wide Release", f"Theater {n}", image=POSTER) for n in range(4)]
        announced = [dict(build.event(source("aeg", "x", "music", "The Sinclair"), "A show", date(2026, 9, 22), time(20),
                                      image="https://x/band.jpg"), added="2026-09-19")]
        lead, film = build.render_lead(films + announced, self.built)
        self.assertEqual(film, "wide release", "what the next build keeps, unless something's bigger")
        self.assertIn('<div class="lead">', lead)
        self.assertLess(lead.index('class="biggest-part"'), lead.index('class="fresh"'), "the film first, what's announced after")
        self.assertNotIn("Widest release", lead, "no heading: its count of theaters says why it's there")
        self.assertIn("4 theaters</span>", lead)
        self.assertEqual(lead.count("<img"), 1, "the film's poster, and no picture of what's announced")
        self.assertNotIn("band.jpg", lead)
        self.assertNotIn("setInterval", lead, "and nothing that turns")
        # Its days and what's started put right as it's read, before it's painted, not when the page's script runs.
        self.assertTrue(lead.endswith(build.LEAD_NOW.replace("ZONE", '"America/New_York"')))

    def test_a_batch_from_one_venue_takes_one_line(self):
        """A hall that puts up a season at once gets a line, as every other venue does, before it gets a second."""
        announce = lambda title, venue, day: dict(build.event(source("aeg", "x", "art", venue), title, date(2026, 9, day), time(19)),
                                                  added="2026-09-19")
        batch = [announce(f"Capstone {n}", "Boston Conservatory", 22 + n) for n in range(5)]
        others = [announce("A reading", "Brookline Booksmith", 28), announce("A band", "The Sinclair", 29)]
        lead, _ = build.render_lead(batch + others, self.built)
        names = re.findall(r'<span class="fresh-name">([^<]+)</span>', lead)
        self.assertEqual(names[:3], ["Capstone 0", "A reading", "A band"], "the hall's soonest, then the others")
        self.assertEqual(names[3:], ["Capstone 1", "Capstone 2", "Capstone 3"], "the rest of its batch as spares")

    def test_a_poster_and_a_still_each_get_their_own_shape(self):
        """A poster stands on its end, a still lies on its side: cut to a poster's shape, a still lost its scene."""
        events = [self.showing("Wide Release", f"Theater {n}", image=POSTER) for n in range(4)]
        standing, _ = build.render_lead(events, self.built)
        self.assertIn('class="biggest standing"', standing)
        self.assertIn('width="81" height="122"', standing)
        with mock.patch.object(build, "picture_shape", return_value=(1920, 1080)):
            lying, _ = build.render_lead(events, self.built)
        self.assertIn('class="biggest" data-category="film"', lying)
        self.assertIn('width="153" height="122"', lying)


class Fallback(unittest.TestCase):
    built = datetime(2026, 9, 20, 16, 0, tzinfo=timezone.utc)
    venue = source("aeg", "https://example.com", name="Roadrunner")

    def listing(self, days_ahead, title="Show"):
        return build.event(self.venue, title, date(2026, 9, 20) + timedelta(days=days_ahead), time(20))

    def previous(self, hours_old, days_ahead=2):
        fetched = (self.built - timedelta(hours=hours_old)).isoformat()
        return {"sources": {"Roadrunner": {"fetched": fetched, "events": [build.saved(self.listing(days_ahead, "Kept"))]}}}

    def test_fresh(self):
        events, failed, stale, listings, errors, seen = build.gather([(self.venue, [self.listing(1)], None)], {}, self.built)
        self.assertEqual(([e["title"] for e in events], failed, stale, errors), (["Show"], [], [], {}))
        self.assertEqual(listings["Roadrunner"]["fetched"], self.built.isoformat())

    def test_error_uses_recent_listings(self):
        events, failed, stale, listings, errors, _ = build.gather([(self.venue, [], OSError("520"))], self.previous(6), self.built)
        self.assertEqual([e["title"] for e in events], ["Kept"])
        self.assertEqual([name for name, _ in stale], ["Roadrunner"])
        self.assertEqual(listings["Roadrunner"]["fetched"], (self.built - timedelta(hours=6)).isoformat(),
                         "the copy keeps its age, so it still expires")
        self.assertIn("Roadrunner", errors)

    def test_error_with_old_listings_fails(self):
        events, failed, stale, *_ = build.gather([(self.venue, [], OSError("520"))], self.previous(72), self.built)
        self.assertEqual((events, failed, stale), ([], ["Roadrunner"], []))

    def test_empty_after_having_shows_uses_listings(self):
        events, failed, stale, _, errors, _ = build.gather([(self.venue, [], None)], self.previous(3), self.built)
        self.assertEqual([e["title"] for e in events], ["Kept"])
        self.assertEqual(errors["Roadrunner"], "returned no listings")

    def test_empty_and_nothing_before_is_just_empty(self):
        events, failed, stale, _, errors, _ = build.gather([(self.venue, [], None)], {}, self.built)
        self.assertEqual((events, failed, stale, errors), ([], [], [], {}))

    def test_past_listings_are_not_restored(self):
        events, *_ = build.gather([(self.venue, [], OSError("520"))], self.previous(6, days_ahead=-1), self.built)
        self.assertEqual(events, [])

    def test_status_page_problems_first_and_out_of_search(self):
        built = self.built.isoformat()
        sources = [dict(source("aeg", "x", name=name), city="boston") for name in ("Roadrunner", "Paradise", "Sinclair", "Brattle")]
        record = {"sources": {"Roadrunner": {"fetched": built, "events": [{}] * 3}, "Paradise": {"fetched": "2026-09-20T01:00:00+00:00", "events": [{}] * 9},
                              "Brattle": {"fetched": built, "events": [{}] * 40}},
                  "failing": {"Paradise": {"since": "2026-09-20T01:00:00+00:00", "error": "HTTP Error 403"},
                              "Sinclair": {"since": "2026-09-19T01:00:00+00:00", "error": "timed out"}},
                  "shrinking": {"Roadrunner": {"since": built, "count": 3, "usual": 30}},
                  "counts": {"Roadrunner": [30] * 8, "Brattle": [40] * 3}}
        page = build.render_status(sources, record, self.built)
        order = [page.index(f"<td>{name}</td>") for name in ("Sinclair", "Paradise", "Roadrunner", "Brattle")]
        self.assertEqual(order, sorted(order), "failed with nothing to show, failing, shrinking, then fine")
        self.assertIn('<meta name="robots" content="noindex">', page)
        self.assertIn("HTTP Error 403", page)
        row = page[page.index("<td>Roadrunner</td>"):].split("</tr>")[0]
        self.assertIn('<td class="num">3</td><td class="num muted">30</td>', row, "now, and its usual")
        brattle = page[page.index("<td>Brattle</td>"):].split("</tr>")[0]
        self.assertIn('<td class="num muted">–</td>', brattle, "no usual yet without a day's counts")

    def test_failing_since_carries_over(self):
        earlier = {"failing": {"Roadrunner": {"since": "2026-09-20T01:00:00+00:00", "error": "520"}}}
        failing = build.still_failing({"Roadrunner": "timed out", "Paradise": "403"}, earlier, self.built)
        self.assertEqual(failing["Roadrunner"], {"since": "2026-09-20T01:00:00+00:00", "error": "timed out"})
        self.assertEqual(failing["Paradise"]["since"], self.built.isoformat())


R = build.PUBLIC_ROOT  # The public site's root, which its links start from.


class Page(unittest.TestCase):
    def test_renders_rows_and_filters(self):
        with mock.patch.object(build, "fetch", sample):
            found = build.read_aeg(source("aeg", "https://aegwebprod.blob.core.windows.net/json/events/219/events.json"))
        page = build.render_index(found, [source("aeg", "x", name="Roadrunner")], [], [], datetime.now(timezone.utc))
        self.assertEqual(len(re.findall(r'<li class="row" data-id="[^"]+" data-series="[^"]+" data-category="music" data-sources="Somewhere"[^>]*>', page)), len(found))
        self.assertEqual(page.count('<div class="preview">'), sum(bool(item["about"]) for item in found))
        for key in build.CATEGORIES:
            self.assertIn(f'data-show="{key}"', page)
        self.assertIn("[hidden] {{ display: none !important; }}".replace("{{", "{").replace("}}", "}"), page)

    def test_public_page(self):
        with mock.patch.object(build, "fetch", sample):
            found = build.read_aeg(source("aeg", "https://aegwebprod.blob.core.windows.net/json/events/219/events.json", name="Roadrunner"))
            kept = build.read_jsonld(source("jsonld", "https://brattlefilm.org/coming-soon/", "film", "Private Theater"))
        sources = [dict(source("aeg", "x", name="Roadrunner"), public=True),
                   dict(source("jsonld", "y", "film", "Private Theater"), public=False)]
        built = datetime.now(timezone.utc)
        public = build.render_index(found + kept, sources, [], [], built, public=True)
        mine = build.render_index(found + kept, sources, [], [], built)
        self.assertNotIn("Newsfeed", public)
        footer = public.split("<footer>")[1]
        for label, href in [("All events", R), ("Music", R + "music/"), ("Film", R + "film/"), ("Art &amp; talks", R + "talks/"),
                            ("This weekend", R + "weekend/"), ("Next weekend", R + "weekend/next/"), ("About", R + "about/"), ("Contact", "/contact/")]:
            self.assertIn(f'<a href="{href}"', footer, label)
        self.assertIn(f'<a href="{R}" aria-current="page">All events</a>', footer, "this page marked")
        self.assertIn("Listings from Roadrunner, aggregated", footer)
        self.assertNotIn(f'href="{R}about/"', public.split("<footer>")[0], "not in the header")
        self.assertNotIn("Add a source", public)
        self.assertIn('content="index, follow"', public)
        self.assertIn('content="noindex, nofollow"', mine)
        self.assertNotIn("Private Theater", public, "a source marked public=no stays off it")
        self.assertIn("Private Theater", mine)
        listings = lambda page: page.split("</style>")[1].split("<footer>")[0]  # Not the styles, which differ.
        self.assertLess(len(listings(public)), len(listings(mine)), "shorter previews, and not the private listings")
        about = build.render_about(sources, built)
        self.assertIn("Roadrunner", about)
        self.assertNotIn("Private Theater", about)
        self.assertIn('<a href="/contact/">Contact</a>', about.split("<footer>")[1], "the site's own form, shared by its cities")
        self.assertIn('<a href="/contact/">Get in touch</a>', about)
        self.assertIn(f'content="{build.PUBLIC_URL}share/home.png?pin"', about, "the home page's card: About has none")

    def test_public_page_tells_search_engines_what_it_is(self):
        with mock.patch.object(build, "fetch", sample):
            found = build.read_aeg(source("aeg", "https://aegwebprod.blob.core.windows.net/json/events/219/events.json", name="Roadrunner"))
        page = build.render_index(found, [dict(source("aeg", "x", name="Roadrunner"), public=True)], [], [],
                                  datetime.now(timezone.utc), public=True)
        self.assertIn(f"<title>{build.PUBLIC_TITLE}</title>", page)
        self.assertIn(f'<link rel="canonical" href="{build.PUBLIC_URL}">', page)
        self.assertIn('<meta property="og:title"', page)
        self.assertIn('<h1 class="tagline">', page)
        data = __import__("json").loads(page.split('<script type="application/ld+json">')[1].split("</script>")[0])["@graph"]
        self.assertEqual(data[0]["@type"], "WebSite")
        show = data[1]
        self.assertEqual(show["@type"], "MusicEvent")
        self.assertEqual(show["location"]["address"]["streetAddress"], "89 Guest St")  # Roadrunner's.
        self.assertRegex(show["startDate"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00-0[45]:00$")
        self.assertEqual(len(data), len(found) + 1)

    def test_category_pages(self):
        with mock.patch.object(build, "fetch", sample):
            music = build.read_aeg(source("aeg", "https://aegwebprod.blob.core.windows.net/json/events/219/events.json", name="Roadrunner"))
            films = build.read_jsonld(source("jsonld", "https://brattlefilm.org/coming-soon/", "film", "Brattle"))
        sources = [dict(source("aeg", "x", name="Roadrunner"), public=True), dict(source("jsonld", "y", "film", "Brattle"), public=True)]
        built = datetime.now(timezone.utc)
        home = build.render_index(music + films, sources, [], [], built, public=True)
        film = build.render_index(music + films, sources, [], [], built, public=True, category="film")
        mine = build.render_index(music + films, sources, [], [], built)
        # The home page's filter links to each kind's page, and marks All; the film page marks Film.
        self.assertIn('data-pages data-current="all"', home)
        self.assertIn(f'<a data-show="film" href="{R}film/">', home)
        self.assertIn(f'<a data-show="all" href="{R}" aria-current="page">All</a>', home)
        self.assertIn('data-current="film"', film)
        self.assertIn(f'<link rel="canonical" href="{build.PUBLIC_URL}film/">', film)
        self.assertNotIn('class="here"', film, "no breadcrumb: the line under the header and the chips say which page")
        self.assertNotIn('class="here"', home)
        self.assertIn(f'<meta property="og:image" content="{build.PUBLIC_URL}share/film.png?pin">', film)
        self.assertIn(f'<meta property="og:image" content="{build.PUBLIC_URL}share/home.png?pin">', home)
        for city in build.CITIES:
            for card in ("home", "music", "film", "talks", "tonight", "weekend"):
                self.assertTrue((build.ROOT / "share" / city.slug / f"{card}.png").exists(), f"share/{city.slug}/{card}.png")
        self.assertTrue((build.ROOT / "share" / "site" / "home.png").exists(), "pushpin.city's own")
        self.assertIn(f"<title>{build.PUBLIC_PAGES['film'][1]}</title>", film)
        # The film page has only films, and says which sources they're from.
        self.assertEqual(film.count('class="row" data-category="music"'), 0)
        self.assertGreater(film.count('data-category="film" data-sources='), 0)
        # Its venue menu has every venue, whatever its kind: a choice goes to the home page, which has them all.
        menu = film.split('<select class="pick" aria-label="Venue">')[1].split("</select>")[0]
        self.assertIn('<option value="Roadrunner">', menu)
        self.assertNotIn("Roadrunner", film.split("<footer>")[1])
        # Your own page keeps its buttons.
        self.assertIn('<button data-show="film">', mine)
        self.assertIn('<nav class="filter" aria-label="Show"><span class="chips"><button', mine)
        self.assertIn(f"<loc>{build.PUBLIC_URL}talks/</loc>", build.render_sitemap(built))

    def test_weekend_days(self):
        # Monday to Thursday, the weekend coming; Friday to Sunday, the one it's in.
        for day, friday in [(date(2026, 9, 14), date(2026, 9, 18)), (date(2026, 9, 17), date(2026, 9, 18)),
                            (date(2026, 9, 18), date(2026, 9, 18)), (date(2026, 9, 20), date(2026, 9, 18))]:
            self.assertEqual(build.weekend_days(day), (friday, friday + timedelta(days=2)), day)
        self.assertEqual(build.weekend_days(date(2026, 9, 13), 1), (date(2026, 9, 18), date(2026, 9, 20)))
        self.assertEqual(build.weekend_span(date(2026, 10, 30), date(2026, 11, 1)), "Oct 30–Nov 1")

    def test_weekend_page(self):
        venue = dict(source("tribe", "x", name="Somewhere"), public=True)
        events = [build.event(venue, f"On the {day.day}th", day, time(20, 0)) for day in
                  (date(2026, 9, 17), date(2026, 9, 18), date(2026, 9, 20), date(2026, 9, 21))]
        built = datetime(2026, 9, 14, 12, tzinfo=timezone.utc)  # A Monday.
        page = build.render_index(events, [venue], [], [], built, public=True, weekend=0)
        self.assertEqual([title for title in ("On the 17th", "On the 18th", "On the 20th", "On the 21th") if title in page],
                         ["On the 18th", "On the 20th"])
        # The line over it just its dates, two lines on a phone.
        self.assertIn('<h1 class="tagline">September 18–20 around Boston, Cambridge, and Somerville.</h1>', page)
        self.assertIn(f'<link rel="canonical" href="{build.PUBLIC_URL}weekend/">', page)
        self.assertIn('<nav class="filter" aria-label="Show" data-here data-one-page><span class="chips"><button', page)
        self.assertIn(f'<meta property="og:image" content="{build.PUBLIC_URL}share/weekend.png?pin">', page)
        self.assertIn(f'<a href="{R}about/" aria-current="page">About</a>', build.render_about([venue], built))
        self.assertIn(f'<a href="{R}weekend/" aria-current="page">This weekend</a>', page)
        self.assertIn(f"<loc>{build.PUBLIC_URL}weekend/</loc>", build.render_sitemap(built))
        self.assertIn(f'<a href="{R}weekend/next/">Next weekend, Sep 25–27 →</a>', page)
        following = build.render_index(events, [venue], [], [], built, public=True, weekend=1)
        self.assertNotIn("On the 18th", following)
        self.assertIn('<h1 class="tagline">September 25–27 around Boston, Cambridge, and Somerville.</h1>', following)
        # A weekend across two months names both.
        across = build.render_index(events, [venue], [], [], datetime(2026, 10, 26, 12, tzinfo=timezone.utc),
                                    public=True, weekend=0)
        self.assertIn('<h1 class="tagline">October 30 – November 1 around Boston, Cambridge, and Somerville.</h1>', across)
        self.assertIn(f'<a href="{R}weekend/">← This weekend, Sep 18–20</a>', following)
        self.assertIn(f'<link rel="canonical" href="{build.PUBLIC_URL}weekend/next/">', following)
        self.assertIn(f'<meta property="og:image" content="{build.PUBLIC_URL}share/weekend.png?pin">', following)
        self.assertIn(f"<loc>{build.PUBLIC_URL}weekend/next/</loc>", build.render_sitemap(built))

    def test_tonight_page(self):
        venue = dict(source("tribe", "x", name="Somewhere"), public=True)
        events = [build.event(venue, f"On the {day.day}th", day, time(21, 0)) for day in
                  (date(2026, 9, 14), date(2026, 9, 15), date(2026, 9, 16))]
        built = datetime(2026, 9, 14, 20, tzinfo=timezone.utc)  # 4pm on Monday, Sep 14, in Boston.
        page = build.render_index(events, [venue], [], [], built, public=True, tonight=True)
        # Today's, and tomorrow's for after midnight (the script shows only the day it is), not later.
        self.assertIn("On the 14th", page)
        self.assertIn("On the 15th", page)
        self.assertNotIn("On the 16th", page)
        self.assertIn('<nav class="filter" aria-label="Show" data-here data-one-page data-today><span class="chips"><button', page)
        self.assertIn(f"<title>{build.PUBLIC_TONIGHT[1]}</title>", page)
        self.assertIn(f'<link rel="canonical" href="{build.PUBLIC_URL}tonight/">', page)
        self.assertIn(f'<meta property="og:image" content="{build.PUBLIC_URL}share/tonight.png?pin">', page)
        self.assertIn(f'<a href="{R}tonight/" aria-current="page">Tonight</a>', page)
        self.assertIn(f"<loc>{build.PUBLIC_URL}tonight/</loc>", build.render_sitemap(built))

    def test_event_data_uses_an_events_own_address(self):
        item = build.event(source("bibliocommons", "x", "art", "Boston Public Library"), "A Talk", date(2026, 9, 20),
                           time(18, 0), venue="Faneuil Library", address=("419 Faneuil Street", "Brighton", "02135"))
        address = build.event_data(item)["location"]["address"]
        self.assertEqual((address["streetAddress"], address["addressLocality"], address["postalCode"]),
                         ("419 Faneuil Street", "Brighton", "02135"))

    def test_postal(self):
        self.assertEqual(build.postal("134 MEMORIAL DR, Cambridge, MA 02139"), ("134 MEMORIAL DR", "Cambridge", "02139"))
        self.assertEqual(build.postal(" 3496 Washington St, Boston, MA 02130, USA"), ("3496 Washington St", "Boston", "02130"))
        self.assertIsNone(build.postal("355 W 16th St, Manhattan, New York, New York, 10011"))
        self.assertIsNone(build.postal(""))

    def test_about_lists_venues_by_kind_with_links_and_counts(self):
        mfa = dict(source("mfa", "x", "art", "MFA"), public=True)
        sinclair = dict(source("axs", "y", "music", "The Sinclair"), public=True)
        quiet = dict(source("ics", "z", "music", "Lizard Lounge"), public=True)  # Nothing coming up.
        hidden = dict(source("jsonld", "w", "film", "Not Ours"), public=False)
        day = date(2026, 9, 20)
        items = [build.event(sinclair, "A", day), build.event(sinclair, "B", day), build.event(mfa, "Talk", day),
                 dict(build.event(mfa, "A Film", day), category="film"), build.event(hidden, "Theirs", day)]
        about = build.render_about([mfa, sinclair, quiet, hidden], datetime(2026, 9, 13, tzinfo=timezone.utc), items)
        sections = {h: body for h, body in re.findall(r"<h2 data-category=\"\w+\"><svg class=\"icon\" aria-hidden=\"true\"><use href=\"#icon-\w+\"/></svg>([^<]+)</h2>\n<ul class=\"venues\">(.*?)</ul>", about)}
        self.assertIn(f'<a href="{R}?venue=The+Sinclair">The Sinclair</a> <span class="count">2</span>', sections["Music"])
        self.assertLess(sections["Music"].index("Lizard Lounge"), sections["Music"].index("The Sinclair"), "The Sinclair among the S's")
        self.assertIn(f'<a href="{R}?venue=Lizard+Lounge">Lizard Lounge</a></li>', sections["Music"], "listed, with no count")
        self.assertIn("MFA</a> <span class=\"count\">1</span>", sections["Film"], "under each kind it has")
        self.assertIn("MFA</a> <span class=\"count\">1</span>", sections["Art &amp; talks"])
        self.assertNotIn("Not Ours", about)
        self.assertIn("How to use it", about)
        # The questions, each opening to its answer, and told to search engines as an FAQ.
        self.assertEqual(about.count("<details><summary>"), len(build.FAQS))
        self.assertIn("<summary>Why isn’t my favorite venue here?</summary>", about)
        data = json.loads(about.split('<script type="application/ld+json">')[1].split("</script>")[0])
        self.assertEqual(data["@type"], "FAQPage")
        self.assertEqual([q["name"] for q in data["mainEntity"]], [q for q, _ in build.FAQS])
        self.assertNotIn("<a", json.dumps(data), "answers as plain text there")

    def test_sitemap(self):
        built = datetime(2026, 9, 13, tzinfo=timezone.utc)
        sitemap = build.render_sitemap(built)
        for path in ("", "about/", "new/", "tonight/"):
            self.assertIn(f"<loc>{build.PUBLIC_URL}{path}</loc>", sitemap)
        self.assertNotIn("contact/", sitemap, "the site's own, in its own sitemap")
        site = build.render_site_sitemap(built)
        self.assertIn(f"<loc>{build.PUBLIC_SITE}cities/</loc>", site)
        self.assertNotIn(f"<loc>{build.PUBLIC_SITE}</loc>", site, "the root is Boston's, in its sitemap")
        self.assertIn(f"<loc>{build.PUBLIC_SITE}contact/</loc>", site)

    def test_notices_come_last_with_their_mark(self):
        venue = dict(source("tribe", "x", name="Lizard Lounge"), public=True)
        items = [build.event(venue, "A Show", date(2026, 9, 20), time(20, 0))]
        stale = [("Lizard Lounge", datetime(2026, 9, 13, 12, tzinfo=timezone.utc))]
        built = datetime(2026, 9, 13, 13, tzinfo=timezone.utc)
        for page in (build.render_index(items, [venue], [], stale, built, public=True),
                     build.render_index(items, [venue], [], stale, built)):
            footer = page.split("<footer>")[1]
            self.assertIn('<p class="notice"><svg class="icon" aria-hidden="true"><use href="#icon-notice"/></svg><span>Couldn’t reach Lizard Lounge', footer)
            self.assertLess(footer.index("rom Lizard Lounge"), footer.index('class="notice"'), "under the list of venues")

    def test_public_previews_are_shorter(self):
        long = ["A" * 150 + " " + "b" * 150, "Doors 7 · 21+"]
        self.assertLessEqual(len(" ".join(build.shorter(long))), build.PUBLIC_ABOUT_CHARS + 1)
        self.assertEqual(build.shorter(["Short.", "Doors 7"]), ["Short.", "Doors 7"])

    def test_public_no_in_sources(self):
        with mock.patch.object(build, "SOURCES_FILE", mock.Mock(read_text=lambda: "tribe  https://a  art  Somewhere Nice  public=no\n"
                                                                                  "tribe  https://b  art  Elsewhere\n")):
            sources = build.read_sources()
        self.assertEqual([(s["name"], s["public"]) for s in sources], [("Somewhere Nice", False), ("Elsewhere", True)])




if __name__ == "__main__":
    unittest.main()


class Evenings(unittest.TestCase):
    """A listing on both before and after the evening starts is listed again at its first evening showing."""

    def at(self, *clocks):
        return [datetime(2026, 11, 21, int(c[:2]), int(c[3:])) for c in clocks]

    def test_split_at_the_evening(self):
        film = {"title": "I Play Rocky", "times": self.at("12:15"), "showings": [
            {"venue": "Coolidge Corner", "times": self.at("12:15", "15:15", "18:15", "21:00")},
            {"venue": "Capitol Theatre", "times": self.at("13:30", "19:30")}]}
        day, evening = build.split_evenings([film])
        self.assertEqual((day["part"], evening["part"]), ("day", "evening"))
        self.assertEqual(day["part_times"], self.at("12:15", "13:30", "15:15"))
        self.assertEqual(evening["part_times"], self.at("18:15", "19:30", "21:00"))
        self.assertEqual(build.part_attribute(evening), ' data-part="evening"')

    def test_only_one_part_stays_one_row(self):
        late = {"title": "Late show", "times": self.at("19:00", "21:30")}
        early = {"title": "Matinee", "times": self.at("11:00", "14:00")}
        self.assertEqual(build.split_evenings([late, early]), [late, early])
        self.assertEqual(build.part_times(late), self.at("19:00", "21:30"))

    def test_the_page_counts_a_rows_own_part(self):
        self.assertIn('const inPart = (li, time) => !li.dataset.part || (li.dataset.part === "evening") === (time.dataset.time >= "17:00");',
                      build.INDEX_JS)
        self.assertEqual(build.EVENING, 17, "the page's 17:00 is the build's EVENING")
        self.assertIn("other.dataset.id !== li.dataset.id)", build.INDEX_JS, "its own other row isn't another day")

    def test_evening_is_headed_where_it_starts(self):
        timed = lambda title, *clocks: {"title": title, "times": self.at(*clocks)}
        untimed = {"title": "All day", "times": []}
        rows = [untimed, timed("Noon", "12:00"), timed("Six", "18:00"), timed("Eight", "20:00")]
        self.assertEqual(build.evening_start(rows), 2)
        self.assertIsNone(build.evening_start([untimed, timed("Six", "18:00")]), "nothing before the evening")
        self.assertIsNone(build.evening_start([timed("Noon", "12:00")]), "nothing in the evening")
        self.assertEqual(build.row_class(dict(rows[2], evening_starts=True)), " evening-starts")
        self.assertIn('for (const li of lis) li.classList.toggle("evening-starts", li === starts);', build.INDEX_JS)




class Fetch(unittest.TestCase):
    def test_a_page_in_windows_1252_is_read_as_one(self):
        page = "Fat n’ Gristle".encode("cp1252")
        with mock.patch.object(build.shared, "fetch", return_value=("", page)):
            self.assertEqual(build.fetch("https://example.com/windows-1252", encoding="cp1252"), "Fat n’ Gristle")
            self.assertEqual(build.fetch("https://example.com/said-to-be-utf-8"), "Fat n\ufffd Gristle")
