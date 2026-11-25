#!/usr/bin/env python3
"""Open a GitHub issue for each source that has been failing for a while, or listing far fewer than it usually
does (shrinking), and close it once it's back.

Runs on GitHub after each build (see .github/workflows/deploy.yml), reading the failures and shrinkage each site's
build recorded in the JSON it publishes:

    python3 -m shared.alerts news=dist/news/feeds.json events=dist/events/listings.json

GitHub emails the repo's owner about new issues, so a source that breaks for good doesn't go unnoticed. A
short hiccup doesn't count: a source must fail, or list too few, every build for ALERT_AFTER first. Only the
sites built this run are checked; one that wasn't (the events page skips most runs) keeps its issues as they are.
"""

import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ALERT_AFTER = timedelta(hours=6)
# Each kind of trouble: its key in the record, and its issues' title.
KINDS = {"failing": "Source failing", "shrinking": "Source shrinking"}
TITLE = re.compile(r"(?P<kind>Source failing|Source shrinking): (?P<name>.+) \((?P<site>\w+)\)$")


def gh(*args):
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def describe(name, site, failure, now):
    hours = round((now - datetime.fromisoformat(failure["since"])).total_seconds() / 3600)
    fix = "its line in news/feeds.txt" if site == "news" else "its reader in events/build.py or its line in events/sources.txt"
    return (
        f"{name}, on the {site} page, has failed every build for about {hours} hours, since "
        f"{failure['since'][:16].replace('T', ' ')} UTC.\n\n"
        f"Last error: `{failure['error']}`\n\n"
        "Until it loads again, the page shows its last good copy for up to two days, then says it couldn't load "
        f"it. If the site changed, update {fix}. This issue closes itself once it loads again."
    )


def describe_shrinking(name, site, shrunk, now):
    hours = round((now - datetime.fromisoformat(shrunk["since"])).total_seconds() / 3600)
    return (
        f"{name}, on the {site} page, still loads, but for about {hours} hours (since "
        f"{shrunk['since'][:16].replace('T', ' ')} UTC) it has listed {shrunk['count']} coming up, where it "
        f"usually lists about {shrunk['usual']}.\n\n"
        "That's often a site that changed in a way its reader still half reads: only its first page, one room's "
        "calendar, or most of its dates misread. Check the venue's own calendar against the page. If it really "
        "has less on (a season ending), there's nothing to do: after two weeks at the new level it's taken as "
        "its usual and this issue closes itself, as it does if the listings come back."
    )


DESCRIBE = {"failing": describe, "shrinking": describe_shrinking}


def main():
    troubles = {}  # (kind, site, name) → its record, for each site built this run.
    for argument in sys.argv[1:]:
        site, path = argument.split("=", 1)
        if Path(path).exists():
            record = json.loads(Path(path).read_text())
            for kind in KINDS:
                for name, trouble in (record.get(kind) or {}).items():
                    troubles[(kind, site, name)] = trouble
        else:
            print(f"{path} wasn't written, so the {site} page wasn't checked (not built this run, or its build failed).")
    checked = {argument.split("=", 1)[0] for argument in sys.argv[1:] if Path(argument.split("=", 1)[1]).exists()}
    now = datetime.now(timezone.utc)

    open_issues = {}
    for kind, title in KINDS.items():
        listed = json.loads(gh("issue", "list", "--state", "open", "--search", f'"{title}" in:title',
                               "--json", "number,title", "--limit", "100"))
        for issue in listed:
            match = TITLE.match(issue["title"])
            if match and match["kind"] == title:
                open_issues[(kind, match["site"], match["name"])] = issue["number"]

    for (kind, site, name), trouble in troubles.items():
        if (kind, site, name) not in open_issues and now - datetime.fromisoformat(trouble["since"]) >= ALERT_AFTER:
            gh("issue", "create", "--title", f"{KINDS[kind]}: {name} ({site})", "--body", DESCRIBE[kind](name, site, trouble, now))
            print(f"Opened an issue: {name} ({site}) has been {kind} since {trouble['since']}")
    for (kind, site, name), number in open_issues.items():
        if site in checked and (kind, site, name) not in troubles:
            back = ("loading again" if kind == "failing" else
                    "no longer listing far fewer than usual: back to its usual, or two weeks at a new level taken as its usual")
            gh("issue", "close", str(number), "--comment", f"{name} is {back}.")
            print(f"Closed the issue for {name} ({site}): it's {back}")


if __name__ == "__main__":
    main()
