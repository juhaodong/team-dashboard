# First-time setup

Detect everything you can, then show the person one summary to confirm. Ask a question only for what detection could not find.

## 1. Detect the config

```
python3 scripts/detect_config.py --team <team profile> --write
```
The team profile (`assets/team.example.json` shows the shape) holds what is the same for everyone: GitLab host, Jira sites, team channel, repo remotes. Keep it in a private team place, not in this repo. Detection takes a few seconds. It reads:
- name and email from `git config`;
- the GitLab username from `glab api user`, run inside their primary checkout;
- the Jira account id from Atlassian `/myself`, if the keychain token exists;
- the team's checkouts, found by their origin URL under `~/dev`, `~/src`, `~/code`, `~/work` and `~`;
- the timezone from the system.

It writes `~/.config/team-dashboard/config.json` (mode 0600) and prints anything it could not detect under `notDetected`.

Then fill the rest yourself:
- **Slack user id**: `slack_search_users` with their email, the `U…` id.
- **Team channel**: from the team profile. If missing, find it with `slack_search_channels`.
- **Language**: the language the person writes to you in. Set `quietReply` to match: `无新事项` for zh, `Nothing new` for en, `Nichts Neues` for de. Everything you produce for others stays English.
- **Default reviewer**: the latest reviewer agreement in the team channel, if one exists. Otherwise leave it empty.
- **Partner QA**: if the team works with a partner's Jira, its defect query comes from the team profile (`partner.defectJql`).

Show the person the finished config in a few lines (name, Slack, GitLab, Jira, repos, language, working hours) and ask once: "Does this look right?" Then run `python3 scripts/check_config.py`.

## 2. What only the person can do

- **Jira token, only if `jira.accountId` was not detected.** They create an API token at id.atlassian.com → Security → API tokens, then store it themselves: `security add-generic-password -a <email> -s atlassian-api-token -w` (it prompts for the value). Never ask for the token in chat. One Atlassian token works on every site the account can see (`scripts/jira --site partner`). Then re-run step 1.
- **glab, only if the GitLab username is missing.** `glab auth login --hostname <gitlab host>`.
- **Slack connector, only if the Slack tools fail.** Enable the Slack connector for the session.

## 3. Publish the board

1. Copy `assets/board-page.html` and replace `{{NAME}}` with their first name.
2. Load the `artifact-capabilities` skill. Publish the page with the Artifact tool, `capabilities: {db: {}}`, `icon: "dashboard"`. The person approves the publish in the app. Save the URL to `config.board.url`.
3. Copy `assets/board-groups.example.json` and `assets/board-notes.example.json` into `stateDir` as `board-groups.json` and `board-notes.json`. Fill the groups from their open MRs: one group per ticket or topic, labelled by what it does.
4. Run `python3 scripts/board_build.py <scratch>/board`, then write every panel with one `ArtifactData` batch (`set`, collection `panels`, doc id = file name). Record the versions in `board-versions.txt`.
5. Offer once to pin it.

## 4. Schedules

Create the ticks with `CronCreate` without asking. Tell the person what you scheduled and how to stop it.
- **Working-hours tick:** `7,27,47 8-18 * * 1-5`. Prompt: "Dashboard tick. Follow the team-dashboard skill and <stateDir>/rules.md. If nothing new, reply exactly <quietReply>."
- **Jira ↔ MR consistency check:** at `7 9,15 * * 1-5`.

Cron jobs live only while this session is open and expire after 7 days. Say so, and re-create them when the person returns after a break.

## 5. Rules

Copy `references/rules.md` to `<stateDir>/rules.md`. From then on, append every instruction the person gives, dated and in their words.
