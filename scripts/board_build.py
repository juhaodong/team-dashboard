#!/usr/bin/env python3
"""Build the dashboard board's panels as JSON files, one per panel.

Usage: board_build.py <out_dir>
Reads the config (~/.config/team-dashboard/config.json or $TEAM_DASHBOARD_CONFIG), open MRs (glab on
config.gitlab.host), Jira (scripts/jira) and board-groups.json / board-notes.json from the state directory.
"""
import json, os, re, subprocess, sys, datetime, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.environ.get("TEAM_DASHBOARD_CONFIG", os.path.expanduser("~/.config/team-dashboard/config.json"))))
STATE = os.path.expanduser(CFG["stateDir"])
REPO = os.path.expanduser(CFG["repos"][CFG["primaryRepo"]]["path"])
HOST = CFG["gitlab"]["host"]
JIRA_BROWSE = CFG["jira"]["sites"]["main"] + "/browse/"
REPO_ORDER = {name: i for i, name in enumerate(CFG["repos"])}
JIRA = os.path.join(HERE, "jira")
ME = CFG["jira"]["accountId"]
GITLAB_USER = CFG["gitlab"]["username"]
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def glab(path):
    for attempt in range(3):
        r = subprocess.run(["glab", "api", "--hostname", HOST, path],
                           cwd=REPO, capture_output=True, text=True)
        if r.returncode == 0:
            return json.loads(r.stdout)
    r.check_returncode()


def jira(path):
    out = subprocess.run([JIRA, "GET", path], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def jql(q, fields="summary,status,assignee"):
    return jira("/rest/api/3/search/jql?jql=" + urllib.parse.quote(q) + "&fields=" + fields + "&maxResults=100")["issues"]


def ticket_of(title):
    m = re.findall(r"\b((?:APP|BUG)-\d+)\b", title)
    return m[0] if m else None


def main(out_dir):
    cfg = json.load(open(os.path.join(STATE, "board-groups.json")))
    notes_path = os.path.join(STATE, "board-notes.json")
    notes = json.load(open(notes_path)) if os.path.exists(notes_path) else {}
    names = cfg.get("reviewerNames", {})
    waiting = notes.get("waiting", {})

    mrs = glab(f"merge_requests?scope=all&state=opened&author_username={GITLAB_USER}&per_page=100")
    rows = []
    for m in mrs:
        ref = m["references"]["full"]
        if ref in cfg.get("exclude", []):
            continue
        pid = urllib.parse.quote(ref.split("!")[0], safe="")
        detail = glab(f"projects/{pid}/merge_requests/{m['iid']}")
        appr = glab(f"projects/{pid}/merge_requests/{m['iid']}/approvals")
        rows.append({
            "ref": ref, "url": m["web_url"], "title": m["title"], "ticket": ticket_of(m["title"]), "tickets": re.findall(r"\b((?:APP|BUG)-\d+)\b", m["title"]),
            "draft": m["draft"], "status": "mergeable" if m["detailed_merge_status"] in ("unchecked", "checking") else m["detailed_merge_status"],
            "ci": (detail.get("head_pipeline") or {}).get("status"),
            "reviewers": [r["username"] for r in m["reviewers"]],
            "approved": [a["user"]["username"] for a in appr.get("approved_by", [])],
        })

    def repo_order(r):
        return REPO_ORDER.get(
            r["ref"].split("!")[0].split("/")[-1], 4)

    grouped, used = [], set()
    for g in cfg["groups"]:
        items = sorted([r for r in rows if r["ref"] not in used and (r["ref"] in g.get("refs", []) or any(t in g["tickets"] for t in r["tickets"])) and not r["draft"]], key=repo_order)
        if items:
            used.update(r["ref"] for r in items)
            grouped.append((g, items))
    other = [r for r in rows if r["ref"] not in used and not r["draft"]]
    if other:
        grouped.append(({"label": "Other", "tickets": []}, other))

    by_rev = {}
    for g, items in grouped:
        rev = items[0]["reviewers"][0] if items[0]["reviewers"] else "unassigned"
        by_rev.setdefault(rev, []).append((g, items))

    not_green = [r for _, items in grouped for r in items if r["ci"] not in (None, "success")]
    unmergeable = [r for _, items in grouped for r in items if r["status"] != "mergeable"]
    head = "Morning! Review requests, grouped by lot."
    state = []
    state.append("All mergeable" if not unmergeable else "All mergeable except " + ", ".join("!" + r["ref"].split("!")[1] for r in unmergeable))
    state.append("CI green" if not not_green else "CI green except " + ", ".join("!" + r["ref"].split("!")[1] + " " + (r["ci"] or "") for r in not_green))
    lines = ["Morning! Review requests:", ""]
    rev_order = sorted(by_rev, key=lambda k: -sum(len(i) for _, i in by_rev[k]))
    for rev in rev_order:
        lines.append("@" + names.get(rev, rev))
        for g, items in by_rev[rev]:
            lines.append(g["label"])
            for r in items:
                lines.append(r["url"])
            if g.get("footer"):
                lines.append(g["footer"])
            lines.append("")
    slack = "\n".join(lines).rstrip() + "\n"

    total = sum(len(i) for _, i in grouped)
    per = ", ".join(f"{names.get(k, k)} {sum(len(i) for _, i in by_rev[k])}" for k in rev_order)
    panels = {}
    panels["slack"] = {"order": 2, "title": "Slack review message", "updatedAt": NOW,
                       "note": f"{total} MRs: {per}." + ("" if not cfg.get("excludeReason") else " Not listed: " + "; ".join(f"{k} ({v})" for k, v in cfg["excludeReason"].items())),
                       "copy": slack}

    review_items = []
    for rev in rev_order:
        for g, items in by_rev[rev]:
            bad = [r for r in items if r["status"] != "mergeable" or r["ci"] not in (None, "success")]
            appr = sorted({a for r in items for a in r["approved"]})
            review_items.append({
                "title": g["label"],
                "tags": [names.get(rev, rev)] + (["approved by " + ", ".join(names.get(a, a) for a in appr)] if appr else []),
                "state": "ok" if appr and not bad else ("warn" if bad else "wait"),
                "detail": " · ".join(x for x in [("Waiting: " + waiting[g["tickets"][0]]) if g.get("tickets") and g["tickets"][0] in waiting else None, "; ".join(f"{r['ref'].split('/')[-1]} {r['status'].replace('_', ' ')}, CI {r['ci'] or 'none'}" for r in bad)] if x) or None,
                "links": [{"label": r["ref"].split("/")[-1], "url": r["url"]} for r in items],
            })
    drafts = [r for r in rows if r["draft"]]
    for r in drafts:
        review_items.append({"title": r["title"], "tags": ["draft"], "state": "info",
                             "links": [{"label": r["ref"].split("/")[-1], "url": r["url"]}]})
    panels["reviews"] = {"order": 3, "title": "Open MRs by reviewer", "updatedAt": NOW, "items": review_items}

    tickets = sorted({r["ticket"] for r in rows if r["ticket"]})
    jira_items = []
    if tickets:
        for i in jql("key in (" + ",".join(tickets) + ")"):
            k, f = i["key"], i["fields"]
            st = f["status"]["name"]
            mine = [r for r in rows if r["ticket"] == k]
            open_ready = [r for r in mine if not r["draft"]]
            expect = "Code Review" if open_ready else None
            if expect and st != expect:
                known = cfg.get("jiraKnown", {}).get(k)
                jira_items.append({"title": f"{k} is {st}, MRs in review", "state": "info" if known else "warn",
                                   "tags": [(f.get("assignee") or {}).get("displayName") or "unassigned"] + (["known, left as is"] if known else []),
                                   "detail": known or f["summary"][:120],
                                   "links": [{"label": k, "url": JIRA_BROWSE + k}] +
                                            [{"label": r["ref"].split("/")[-1], "url": r["url"]} for r in open_ready]})
    panels["jira"] = {"order": 4, "title": "Jira ↔ MR mismatches", "updatedAt": NOW, "items": jira_items,
                      "emptyText": "Every ticket with an open MR is in Code Review."}

    qa = jql(f"project in (APP,BUG) AND status = QA AND assignee = {ME} ORDER BY key", "summary")
    panels["qa"] = {"order": 5, "title": "In QA, assigned to you", "updatedAt": NOW,
                    "note": notes.get("qaNote"),
                    "items": [{"title": i["key"] + " · " + i["fields"]["summary"][:110], "state": "info",
                               "links": [{"label": i["key"], "url": JIRA_BROWSE + i["key"]}]} for i in qa]}

    for key, order, title in (("attention", 1, "Needs you"), ("updates", 1.5, "Updates"), ("sessions", 6, "Sessions")):
        n = notes.get(key, {})
        panels[key] = {"order": order, "title": title, "updatedAt": n.get("updatedAt", NOW),
                       "note": n.get("note"), "items": n.get("items", []),
                       "emptyText": {"attention": "Nothing waiting on you.", "updates": "No updates yet."}.get(key, "No session activity recorded.")}

    os.makedirs(out_dir, exist_ok=True)
    for k, v in panels.items():
        v = {a: b for a, b in v.items() if b is not None}
        json.dump(v, open(os.path.join(out_dir, k + ".json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: len(v.get("items", [])) for k, v in panels.items()}))


if __name__ == "__main__":
    main(sys.argv[1])
