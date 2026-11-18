# The board

A private claude.ai artifact (`assets/board-page.html`) with the `db` capability. Each panel is one document in collection `panels`, and the page shows them as tabs, ordered by `order`.

## Panels

| doc id | order | title | Source |
|---|---|---|---|
| `attention` | 1 | Needs you | `board-notes.json` → `attention`: **only** what the person must do or decide (a decision, a login, a reply only they can send). Remove an item the moment it's answered |
| `updates` | 1.5 | Updates | `board-notes.json` → `updates`: everything else worth knowing, newest first. Drop items older than a day |
| `slack` | 2 | Slack review message | Built: a copyable "Morning! Review requests:" message grouping the person's open MRs by reviewer and topic. Links only, no CI or merge status |
| `reviews` | 3 | Open MRs by reviewer | Built from GitLab, plus `board-notes.json` → `waiting` (per group: what it waits for) |
| `jira` | 4 | Jira ↔ MR mismatches | Built (see the Consistency section in `tick.md`). `jiraKnown` turns a warning into "known" |
| `qa` | 5 | In QA, assigned to you | Built from Jira |
| `sessions` | 6 | Sessions | `board-notes.json` → `sessions`: one row per working session |

Panel document shape: `{order, title, updatedAt, note?, copy?, emptyText?, items: [{title, state: crit|warn|wait|ok|info, tags: [..], detail?, links: [{label, url}]}]}`.

## Inputs

- `board-groups.json`:
  - `groups`: `[{tickets: [keys], refs?: ["group/project!iid"], label, footer?}]`. An MR joins the first group whose `refs` lists it or whose `tickets` share a key with its title. Use `refs` for bundle MRs whose title carries no key.
  - `exclude`: MR refs never listed, with `excludeReason`.
  - `reviewerNames`: GitLab username → first name, for the Slack message.
  - `jiraKnown`: ticket → reason a mismatch is intentional.
- `board-notes.json`: `attention`, `updates`, `sessions` (each `{updatedAt, items}`), `waiting` (first ticket of a group → text), `qaNote`.

## Refresh (every tick)

1. Update `board-notes.json`. Add new items with the right `state`, and remove answered or stale ones.
2. `python3 scripts/board_build.py <scratch>/board` writes one JSON file per panel.
3. One `ArtifactData` call with `action: batch`, one `set` per panel (all seven, every time: GitLab and Jira panels go stale otherwise), with `file_path` and `if_version` from `board-versions.txt`.
4. Append the new versions to `board-versions.txt`. On a version conflict, `list` the collection with `out_dir`, take the versions and retry.

## Slack review message

The person posts it themselves. The panel's Copy button copies it. Keep it plain:
```
Morning! Review requests:

@Reviewer
<group label>
<MR url>
<MR url>
```
No status lines ("CI running", "mergeable"). The reviewer opens the MR anyway.
