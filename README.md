# team-dashboard

A Claude Code skill that turns one session into your personal work dashboard. On a schedule it:
- watches Slack, Jira and GitLab;
- routes work to your other Claude sessions;
- dispatches and posts code reviews by your rules;
- keeps Jira in step with your merge requests;
- keeps a private claude.ai artifact board with everything you need to act on.

## Install

Copy this folder to `~/.claude/skills/team-dashboard/` (or into a repo's `.claude/skills/`). Then ask Claude "set up my dashboard".

You need:
- the Claude desktop app's Code tab: sessions, artifacts, the Slack connector;
- `glab`, logged in to your GitLab;
- an Atlassian API token in the macOS keychain (`security add-generic-password -a <email> -s atlassian-api-token -w`);
- Python 3.

## Team profile

What is the same for the whole team goes into a small JSON file that you share inside the team. Never commit it here. `assets/team.example.json` shows the shape: GitLab host, Jira sites, team Slack channel, repo remotes.

Setup detects everything else about the person:
- name and email;
- GitLab user and Jira account;
- local checkouts and timezone;
- Slack id.

## Layout

- `SKILL.md`: the role, the tick, the approval matrix, the rules.
- `references/`: setup, tick details, the board, the starting rules.
- `scripts/`: `detect_config.py`, `check_config.py`, `board_build.py`, a `jira` curl wrapper and `md2adf.py`.
- `assets/`: the board page and example config files.
