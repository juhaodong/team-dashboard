# The tick in detail

Keep a tick cheap. Run the queries in one parallel batch with concise output, and read details only for hits. Compare against `seen.txt` and `dispatched.txt` so nothing is handled twice.

## 1. Slack

- `slack_search_public_and_private` with query `<@{slack.userId}> after:{yesterday}`, `sort: timestamp`, concise.
- The same with `to:<@{slack.userId}>`. Ignore Jira-bot and calendar DMs.
- `slack_read_channel` on `slack.teamChannel` with `oldest` = last tick. This catches review requests without an @-mention ("PRs for review: …").
- What counts:
  - a review request to the person, or to "anyone" in a lot they own;
  - a question to them;
  - a complaint or decision that affects their work;
  - a teammate's message that changes a session's task.
- Casual chat the person already replied to is not reported.

## 2. GitLab

From the primary checkout (glab picks the host from the repo):
```
glab api --hostname {gitlab.host} "merge_requests?scope=all&state=opened&author_username={u}&updated_after={iso}"
glab api --hostname {gitlab.host} "merge_requests?scope=all&state=opened&reviewer_username={u}&updated_after={iso}"
glab api --hostname {gitlab.host} "merge_requests?scope=all&state=merged&author_username={u}&updated_after={iso}"
```
For each hit, check the new head sha, the notes (`notes?sort=desc`), approvals, `detailed_merge_status` and the head pipeline.
- **New review request for the person**, not in `dispatched.txt`: dispatch it (see SKILL.md, Dispatching work), add 👀 to the Slack ask, and log it.
- **New push on an MR they already reviewed**: if the push answers their findings, dispatch a re-review of the delta since the reviewed commit (`git range-diff`). Report only.
- **Their own MR**: new reviewer comments go to the session that owns the MR. Merged: move its tickets to QA (see Consistency). A conflict or need-rebase goes to the owner session.
- **The person's updated_at** sometimes reflects their own note. Check the author before reporting.

## 3. Jira

- `scripts/jira GET "/rest/api/3/search/jql?jql=(assignee=currentUser() OR watcher=currentUser()) AND updated >= -30m&fields=summary,status"`.
- Partner defects: `scripts/jira --site partner GET "/rest/api/3/search/jql?jql={partner.defectJql}"`. New ones for the person's area: read them, check them against the latest code and QA, and offer one mirror ticket on your own board per batch, never one per defect.

## 4. Sessions (hourly)

- `list_sessions` (non-archived, recently active), then `list_events` (limit 6–10) on sessions whose activity moved.
- Report:
  - waiting on the person: a question, an approval or a login;
  - finished a deliverable: an MR opened or merged, a QA verdict;
  - stuck: running more than 90 minutes with no progress, or a repeated error;
  - idle with work left.
- Idle with work left and nothing needed from the person: nudge it with a one-line SendMessage.
- Logins that expire (cluster CLIs, cloud logins, admin consoles) are the person's to do. Put them in "Needs you" with the exact command.

## Consistency (twice a day)

For each ticket key in the person's open and recently merged MRs:
- An open, non-draft MR means the ticket should be in Code Review, assigned to the reviewer.
- Only draft MRs means the ticket should not be in Code Review.
- All its MRs merged means QA or later, assigned to the person. Do this move yourself, with no comment.
- Accepted or Released while an MR is still open means stale: report it.
Report every other mismatch. Mark intentional deviations in `board-groups.json` → `jiraKnown`, so they stop showing as warnings.

## Reply

Write only what changed, grouped by what the person must do, then FYIs. Use their language, short lines, and no ticket keys without a description. If nothing changed: exactly `config.quietReply`.
