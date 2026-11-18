#!/usr/bin/env python3
"""Validate ~/.config/team-dashboard/config.json (or $TEAM_DASHBOARD_CONFIG). Exit 1 with the missing fields."""
import json, os, sys

path = os.environ.get("TEAM_DASHBOARD_CONFIG", os.path.expanduser("~/.config/team-dashboard/config.json"))
REQUIRED = ["name", "email", "language", "quietReply", "slack.userId", "slack.teamChannel",
            "gitlab.host", "gitlab.username", "jira.accountId", "jira.sites", "workingHours", "stateDir", "repos", "primaryRepo"]


def get(d, dotted):
    for part in dotted.split("."):
        if not isinstance(d, dict) or part not in d:
            return None
        d = d[part]
    return d


try:
    cfg = json.load(open(path))
except FileNotFoundError:
    sys.exit(f"no config at {path}: copy assets/config.example.json there and fill it in")
missing = [f for f in REQUIRED if get(cfg, f) in (None, "", [])]
if missing:
    sys.exit("missing: " + ", ".join(missing))
os.makedirs(os.path.expanduser(cfg["stateDir"]), exist_ok=True)
for repo, r in (cfg.get("repos") or {}).items():
    p = r["path"]
    if not os.path.isdir(os.path.expanduser(p)):
        print(f"warning: repo {repo} not found at {p}")
print(f"ok: {cfg['name']} — state in {cfg['stateDir']}, board {get(cfg, 'board.url') or '(not published yet)'}")
