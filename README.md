# team-dashboard

A [Claude Code](https://claude.com/claude-code) skill that turns one Claude session into your personal work dashboard. It runs on a schedule, and on each run it:

- watches Slack, Jira and GitLab, and reports only what changed;
- routes work to your other Claude sessions and nudges the ones that stall;
- dispatches code reviews (three-way: itself, a subagent and Codex), posts the approvals and drafts the rest for you;
- keeps Jira tickets in step with their merge requests;
- maintains a private claude.ai page, **"<Your name> Dashboard"**, whose "Needs you" tab holds only what you have to do or decide.

It never posts on Slack as you, never merges without asking, and never posts the same Jira comment on several tickets.

## Requirements

- The Claude desktop app, Code tab. The skill uses sessions, artifacts, cron and the Slack connector.
- macOS. The Jira token is read from the keychain.
- [`glab`](https://gitlab.com/gitlab-org/cli), logged in to your GitLab.
- An Atlassian API token for your Jira (see [Install](#install)).
- Python 3.
- Optional: Codex, for the third reviewer; and the `review-mr` and `story` skills, if your team has them.

## Install

```sh
git clone https://github.com/juhaodong/team-dashboard ~/.claude/skills/team-dashboard
```

Store your Atlassian API token once (create it at id.atlassian.com → Security → API tokens):

```sh
security add-generic-password -a <your work email> -s atlassian-api-token -w
```

The command prompts for the token. Never paste the token into a chat.

## Team profile

Everything that is the same for your whole team goes into a small JSON file, kept somewhere private to the team. Don't put it in this repo. `assets/team.example.json` shows the shape:

```json
{
  "gitlab": { "host": "gitlab.example.com" },
  "jira": { "sites": { "main": "https://your-org.atlassian.net", "partner": "https://partner-org.atlassian.net" } },
  "slack": { "teamChannel": "C0XXXXXXXXX" },
  "repos": { "backend": { "remote": "group/backend" }, "frontend": { "remote": "group/frontend" } },
  "primaryRepo": "backend",
  "partner": { "defectJql": "project = PARTNER AND created >= -1d", "qaStories": [] }
}
```

One person writes it, and everyone else gets it from them.

## First run

Open a new session in the Code tab and say:

> Set up my dashboard. The team profile is at ~/team.json.

Claude then:
1. detects who you are: name, email, GitLab user, Jira account, your local checkouts, timezone and Slack id;
2. shows you the result in a few lines and asks once if it is right;
3. publishes your dashboard page (you approve the publish in the app);
4. schedules the checks: every 20 minutes during working hours, plus a Jira ↔ MR consistency check twice a day.

It replies in the language you write to it in. Everything it writes for others (Jira, GitLab, Slack drafts) stays in English.

## Day to day

Leave the session open; the checks only run while it is. Things you can say:

| You say | It does |
|---|---|
| "What's new?" / "进度如何" | A short status: what needs you, then FYIs |
| "Review it" | Runs the three-way review on the MR you mean, posts an APPROVE, and shows you anything else first |
| "Give me the Slack review message" | Points you to the board's Copy button, with the text in the reply |
| "Send it" / "发" | Posts the draft it just showed you |
| "From now on, …" | Adds the rule, with today's date, to your `rules.md` |
| "Stop the checks" | Deletes the schedules |

The cron schedules expire after 7 days. When you come back after a break, say "restart the checks".

## The dashboard page

Tabs: **Needs you**, **Updates**, **Slack review message** (copyable), **Open MRs by reviewer**, **Jira ↔ MR mismatches**, **In QA**, **Sessions**. The page is private to you and lives on claude.ai. It updates on every check.

## What it may do without asking

| Action | Default |
|---|---|
| Read anything, refresh the board, message your own sessions | Yes |
| 👀 / 📝 / ✅ reactions on review requests | Yes |
| Post a verified APPROVE review and approve the MR | Yes |
| Post a REQUEST_CHANGES or COMMENT review | Shows you first |
| Move a ticket to QA once its MRs are merged | Yes |
| Any other Jira change | Asks |
| Post on Slack as you | Never: it drafts, and you paste |
| Merge | Always asks |

Change any row by telling it. The change is stored in your `rules.md` and overrides the defaults.

## Files

```
SKILL.md                 the role, the check loop, the approval matrix, the rules
references/setup.md      first-run setup
references/tick.md       what each check queries and how it reports
references/board.md      dashboard panels and refresh
references/rules.md      starting rules, copied to your rules.md
scripts/detect_config.py fills your config from the team profile and this machine
scripts/check_config.py  validates the config
scripts/board_build.py   builds the dashboard panels from GitLab, Jira and your notes
scripts/jira             a small curl wrapper for Jira and Confluence REST (token from the keychain)
scripts/md2adf.py        Markdown → Atlassian Document Format
assets/                  the dashboard page and example configs
```

Your own state lives in `~/.config/team-dashboard/`: the config, `rules.md`, and what was already reported and dispatched. Nothing personal goes into this repo.

## Troubleshooting

- **The checks stopped.** The session was closed, or 7 days passed. Say "restart the checks".
- **`glab` talks to gitlab.com.** It has to run inside one of your team's checkouts. The scripts take care of this.
- **A Jira call answers 401.** The keychain token is missing or expired. Store a new one (see Install).
- **A cluster or cloud login expired.** It shows up under "Needs you" with the command to run. Logins are always yours to do.

## License

MIT
