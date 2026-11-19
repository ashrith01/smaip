# Issue tracker: GitHub

Issues and specs for this repo live in GitHub Issues at `ashrith01/smaip`.
Use `gh` from this repo for issue operations. Before the first issue
creation in a session, verify the target with `gh repo view --json nameWithOwner`.

Create with `gh issue create`; read with `gh issue view`; list with
`gh issue list`; update labels with `gh issue edit`; comment with
`gh issue comment`; and close with `gh issue close`. Use native GitHub
sub-issues and dependencies when available. If unavailable, record
`Part of #<parent>` or `Blocked by: #<number>` in the issue body.

PRs as a request surface: no.

When a skill says "publish to the issue tracker," create a GitHub issue.
When it says "fetch the relevant ticket," read the GitHub issue.
