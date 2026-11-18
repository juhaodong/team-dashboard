#!/usr/bin/env python3
"""Build the dashboard config from a team profile plus what this machine already knows.

The team profile (JSON, shared inside the team, never committed here) holds what is the same for everyone:
  {"gitlab": {"host": …}, "jira": {"sites": {"main": …, "partner": …}}, "slack": {"teamChannel": …},
   "repos": {"<name>": {"remote": "<group/project>"}, …}, "primaryRepo": "<name>", "partner": {…}}
Detected per person: name and email (git config), local checkouts (by origin URL), GitLab username (glab),
Jira account id (Atlassian /myself, if the keychain token exists), timezone.
Slack user id needs the Slack connector, so the agent fills it afterwards.

Usage: detect_config.py --team team.json [--write]
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.environ.get("TEAM_DASHBOARD_CONFIG", os.path.expanduser("~/.config/team-dashboard/config.json"))


def run(*cmd, cwd=None, env=None):
    try:
        return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        return ""


def find_repos(wanted):
    found = {}
    for root in [os.path.expanduser(p) for p in ("~/dev", "~/src", "~/code", "~/work", "~")]:
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, _ in os.walk(root):
            if dirpath[len(root):].count(os.sep) > 4 or "node_modules" in dirpath or "/.claude/" in dirpath:
                dirnames[:] = []
                continue
            if os.path.isdir(os.path.join(dirpath, ".git")):
                url = run("git", "-C", dirpath, "remote", "get-url", "origin").rstrip("/").removesuffix(".git")
                for name, slug in wanted.items():
                    if name not in found and url.endswith(slug):
                        found[name] = dirpath.replace(os.path.expanduser("~"), "~", 1)
                dirnames[:] = []
        if len(found) == len(wanted):
            break
    return found


def main():
    if "--team" not in sys.argv:
        sys.exit("usage: detect_config.py --team team.json [--write]")
    team = json.load(open(sys.argv[sys.argv.index("--team") + 1]))
    wanted = {name: r["remote"] for name, r in team["repos"].items()}
    paths = find_repos(wanted)
    primary = team.get("primaryRepo") or next(iter(wanted))
    gl_user = ""
    if primary in paths:
        out = run("glab", "api", "--hostname", team["gitlab"]["host"], "user", cwd=os.path.expanduser(paths[primary]))
        try:
            gl_user = json.loads(out).get("username", "")
        except ValueError:
            pass
    tz = run("/usr/bin/readlink", "/etc/localtime").split("zoneinfo/")[-1] or "UTC"
    cfg = {
        "name": run("git", "config", "--global", "user.name"),
        "email": run("git", "config", "--global", "user.email"),
        "language": "en", "quietReply": "Nothing new",
        "slack": {"userId": "", "teamChannel": team.get("slack", {}).get("teamChannel", "")},
        "gitlab": {"host": team["gitlab"]["host"], "username": gl_user},
        "jira": {"accountId": "", "reviewerDefault": "", "sites": team["jira"]["sites"]},
        "partner": team.get("partner", {}),
        "workingHours": {"days": "Mon-Fri", "from": "09:00", "to": "18:00", "tz": tz},
        "stateDir": "~/.config/team-dashboard/state/",
        "repos": {name: {"path": paths.get(name, ""), "remote": slug} for name, slug in wanted.items()},
        "primaryRepo": primary,
        "board": {"url": ""},
    }
    if cfg["email"]:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        tmp = PATH + ".detect"
        json.dump(cfg, open(tmp, "w"))
        out = run(os.path.join(HERE, "jira"), "GET", "/rest/api/3/myself", env=dict(os.environ, TEAM_DASHBOARD_CONFIG=tmp))
        os.remove(tmp)
        try:
            cfg["jira"]["accountId"] = json.loads(out).get("accountId", "")
        except ValueError:
            pass
    missing = [k for k, v in (("name", cfg["name"]), ("email", cfg["email"]), ("gitlab.username", gl_user),
                              ("jira.accountId", cfg["jira"]["accountId"])) if not v]
    missing += [f"repos.{k}" for k in wanted if k not in paths]
    if "--write" in sys.argv and not os.path.exists(PATH):
        json.dump(cfg, open(PATH, "w"), indent=2)
        os.chmod(PATH, 0o600)
    print(json.dumps({"config": cfg, "notDetected": missing}, indent=2, ensure_ascii=False))


main()
