# Bug reports from the site

## Goal

A visitor reports a bug from any page without seeing or needing an account on the project's forge.
The server files the report as an issue on GitHub; GitLab can replace GitHub later by adding one
adapter and changing configuration, with no change to the form, routes or tests.

## Decisions

- **Server-side.** The browser posts to this app; the app calls the forge API with a token from the
  environment. The token never reaches the browser, a log or a page.
- **Standalone page.** A "Report a bug" button in the top bar of every page links to
  `/report?from=<current path>`. The form is a server-rendered page, with no overlay and no new
  JavaScript.
- **No abuse protection.** No rate limit, honeypot or captcha: visitors are trusted. A script could
  open many issues until the token is revoked.
- **Fenced description.** The visitor's description goes into the issue inside a fenced code block, so
  `@mentions`, images and links in it do nothing on the forge.
- **Off by default.** Without a token the feature is disabled: the button is hidden and `/report`
  answers 404, so local development needs no credentials.

## Behaviour

### Button and form

- The top bar (see `templates/base.html` and the home page header) shows "Report a bug" next to
  "Sources" when the feature is enabled, except on the report pages themselves. It links to `/report?from=<path and query of the current page>`.
- `GET /report` renders the form: title, description, a hidden `page` field filled from `from`.
  `from` is accepted only when it starts with a single `/`; anything else becomes the empty string.
- `POST /report` (form fields `title`, `description`, `page`) validates, files the issue and renders a
  thank-you page: "Thanks, your report was filed as #<number>", with a link back to `page`
  (or to `/` when it is empty). The page shows the number but does not link to the issue.

### The issue

- Title: `[site] <title>`.
- Body, in this order: a "Description" heading and the description in a fenced block (the fence is
  longer than any backtick run inside the text), then a "Context" heading and a second fenced block
  with the page path (the app's `/…` path as the visitor sent it), the browser's `User-Agent` header
  and the UTC time. Both blocks are fenced because the visitor controls all of those values. The
  visitor's IP is not recorded.
- No labels and no assignees: a fine-grained token limited to issues cannot create labels.

### Limits and errors

- Title 1 to 120 characters and description 1 to 5000 characters after trimming. Violations answer
  422 and file nothing; the form carries the same `required` and `maxlength`.
- A forge failure (network error, timeout of 10 s, any non-success status) shows a plain "We could not
  send your report, please try again later" page with status 502. The real status and body go to the
  server log, never to the page, and the token is never part of a log line.
- A malformed forge response (success status without an issue number) is treated as a failure.

## Configuration

| Variable | Meaning |
|---|---|
| `ORGESTRA_ISSUES_PROVIDER` | `github` (default). Any other value fails at startup with a clear message. |
| `ORGESTRA_ISSUES_REPO` | `owner/name`, for example `Djaygo/orgestra` |
| `ORGESTRA_ISSUES_TOKEN` | GitHub fine-grained token, "Issues: read and write" on that one repository |

The feature is enabled when both the repository and the token are set. `Settings` keeps the token out
of its `repr`.

## Components

| Unit | Responsibility | Depends on |
|---|---|---|
| `reports/tracker.py` | `IssueTracker` protocol: `create_issue(title, body) -> Issue`; `Issue(number)`; `TrackerError` | none |
| `reports/github.py` | `GitHubIssues(repo, token, client)` implements the protocol over the REST API | `httpx2` |
| `reports/body.py` | builds the issue title and body (fenced description, metadata) | none |
| `reports/routes.py` | `/report` routes, validation, the thank-you and failure pages | `IssueTracker`, templates |
| `templates/report.html`, `report_sent.html`, `report_failed.html`; `base.html` | the form, the two result pages, the top-bar button | route contexts |
| `app.py` | settings, builds the tracker (or none) and exposes it on `Services` | `reports` |

Boundaries: `IssueTracker` knows nothing about HTTP routes or templates; routes know nothing about
GitHub. GitLab later is `reports/gitlab.py` (`POST /projects/:id/issues`, `PRIVATE-TOKEN` header) plus
one branch where the provider is chosen. Nothing is added for it today.

### GitHub adapter

`POST https://api.github.com/repos/{repo}/issues` with headers `Authorization: Bearer <token>`,
`Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28` and a JSON body
`{"title", "body"}`. Success is status 201 with the issue `number` in the JSON. The `httpx2.Client` (the client Starlette 1.7 already requires; `httpx` is not installed) is
created once at startup with a 10 s timeout and passed in, so tests can inject a mock transport.

## Testing

- `GitHubIssues` with `httpx2.MockTransport`: request URL, headers and JSON body; a 201 response gives
  the issue number; a 401, a 422, a 500, a timeout, invalid JSON and a 201 without `number` all raise
  `TrackerError`.
- `body.py`: the description is fenced, a description containing backticks gets a longer fence,
  `@mentions` stay inside the fence, and the metadata list is present.
- Routes with a fake tracker injected through `Services`: form renders with `from` preserved; an
  external or malformed `from` is dropped; success shows the issue number; a failing tracker shows the
  502 page with no secret; blank and over-long fields give 422 and file nothing; with no tracker the
  button is absent and `/report` is 404 for both methods.
- The token never appears in any rendered page or in `repr(settings)`.
- The demo tour gains a step that opens the form from the top bar and fills it in without submitting,
  so a demo never creates a real issue (the demo server is started with a placeholder repository and token
  so the button shows).

## Out of scope

Rate limiting and captcha, screenshots or file attachments, labels, a second forge implementation,
showing the visitor a link to the issue, reading issues back, and any use of the SQLite database.
