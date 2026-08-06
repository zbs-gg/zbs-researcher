# Releasing the `zbs-researcher` installer to npm

The package is the thin `npx` shim in this directory. The plugin itself is
installed by the `claude` CLI, not by npm — so this package stays tiny and its
only job is to run two commands.

## One-time: move ownership to the ZBS organization

`zbs-researcher@0.1.0` was published on 2026-07-21 from a personal account.
npm organizations can own **unscoped** packages, so the package name — and
therefore the install command `npx -y zbs-researcher@latest` — does not change.

1. Create the organization at <https://www.npmjs.com/org/create> (free plan
   covers unlimited public packages).
2. Open the organization → **Packages** → **Add Existing Package** → type
   `zbs-researcher` → add it.
3. Confirm ownership moved: <https://www.npmjs.com/package/zbs-researcher>
   should list the organization as maintainer.

Steps 1–2 require being signed in to npm in a browser. They cannot be done
from the CLI.

## Every release

```bash
npm whoami
```

```bash
cd installer && npm publish --dry-run
```

Read the dry-run file list: it must be exactly three files — `bin/cli.js`,
`package.json`, `README.md` (about 4.5 kB packed). Anything else means `files`
in `package.json` drifted. The dry run must also print no `npm warn publish`
lines; a warning there means npm silently rewrote a field.

```bash
cd installer && npm publish
```

Then verify the published metadata rather than trusting the upload:

```bash
npm view zbs-researcher version description maintainers
```

## Retiring the old 0.1.0

Prefer **deprecate** over unpublish:

```bash
npm deprecate zbs-researcher@0.1.0 "Superseded by 0.5.0 — npx -y zbs-researcher@latest"
```

Why not `npm unpublish`: the free 72-hour unpublish window closed on
2026-07-24, and unpublishing a version burns that exact version number
permanently — `0.1.0` could never be republished. Since the package name is
being kept either way, removal buys nothing that deprecation does not, and
deprecation is reversible (`npm deprecate <pkg>@<ver> ""` clears it).

## Version agreement

Four files carry the version and the selftest enforces that three of them
agree:

- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json` (the `deep-research` entry)
- `installer/package.json`
- `CHANGELOG.md` (needs a matching `## <version>` heading)

`skills/deep-research/scripts/selftest.sh` step 3 pins the expected version —
bump it there too, or the smoke test fails on the next run.
