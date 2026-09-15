# Agent guide — asta-autodiscovery

Instructions for AI coding agents working in this repository. Human contributors
should read [`README.md`](README.md) and [`docs/`](docs/index.md) first.

## This repository is PUBLIC — treat everything you write here as published

`allenai/asta-autodiscovery` is a public repository. Code, commit messages, issue
and pull-request titles and bodies, review comments, branch names, test fixtures,
and docs are all world-readable and indexed the moment they are pushed — and they
stay readable after a delete, via forks, caches, and the events API. There is no
"take it back."

Agents commonly reach this repo carrying context from somewhere non-public: an
internal chat thread, an internal ticket, an incident channel, another repository
that is private or internal. **Before you write anything here, strip the context
that does not belong in public.** Describe the change and its rationale at the
minimum detail a public reader needs; do not paste, quote, or summarize the
private discussion that led to it.

Do not put any of the following into this repository:

- **Credentials or secrets** of any kind — tokens, API keys, connection strings,
  signed URLs, `.env` contents. See [`.gitguardian.yaml`](.gitguardian.yaml);
  treat a scanner hit as a stop-and-rotate event, not a lint error.
- **Links to, or contents of, non-public sources** — internal chat threads and
  message text, internal docs and dashboards, private/internal repository names,
  internal ticket contents.
- **Internal infrastructure detail** — internal hostnames, private endpoints,
  cluster/account identifiers, IPs, internal service topology, and internal
  deployment specifics that are not already documented publicly here.
- **Personal data** — names, emails, or identifiers of users; user queries,
  datasets, feedback text, or logs that originated from real people. Never use
  real user data as a test fixture; synthesize one.
- **Unannounced plans** — roadmap, embargoed research, partner or vendor names,
  or organizational detail that has not been published elsewhere.

Naming a person is the one deliberate exception, and only in the narrow form
below.

**When in doubt, leave it out**, or ask the human who asked for the change. A
vaguer public artifact is cheap; a disclosure is not reversible.

### Crediting a human contributor

When someone's guidance materially shaped a change, credit them in the pull
request body by their **verified GitHub handle only** — `Suggested-by: @handle`,
or `Co-authored-by:` when the input rises to authorship. Never substitute a name
or handle from another system, never guess an identity from a name match, and
never add a link to the non-public thread the guidance came from.

## Development

See [`README.md`](README.md) for the full workflow. In short:

```sh
make sync   # install all packages (incl. test + docs deps)
make test   # main test suite (excludes Modal tests)
make lint   # Ruff lint + format checks
```

Run `make test` and `make lint` locally before pushing; do not push a change
whose checks you have not run.

## Pull requests

- Branch and open a pull request — never commit or push directly to `main`.
- Request a reviewer on the pull request; do not assign a human as the assignee
  of work you authored, and never merge your own pull request.
- Keep the pull-request body scoped to what changed and why, subject to the
  disclosure rules above.
