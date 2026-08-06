# Releasing the installer to npm

The package is the thin `npx` shim in this directory. The plugin itself is
installed by the `claude` CLI, not by npm — so this package stays tiny and its
only job is to run two commands.

Published name: **`@zbs-gg/zbs-researcher`** — a scoped package, owned by the
`zbs-gg` npm organization. The scope is what makes the org visible in the name,
matching the GitHub slug `zbs-gg/zbs-researcher`.

> npm has no `org/name` form. A package is either unscoped (`zbs-researcher` —
> the name shows nothing about who owns it) or scoped (`@zbs-gg/zbs-researcher`).
> Only the scoped form displays the organization, and only the scoped form can
> be published entirely from the CLI — moving an *unscoped* package to an org
> requires the npmjs.com web UI.

## Publish

```bash
npm whoami
```

Must print the account that owns the `zbs-gg` org. Check the org itself:

```bash
npm org ls zbs-gg
```

A non-existent org answers `E404 Scope not found`, so a real listing is proof.
Then inspect what would ship:

```bash
cd installer && npm publish --dry-run
```

The file list must be exactly three files — `bin/cli.js`, `package.json`,
`README.md` (about 4.5 kB packed). Anything else means `files` in
`package.json` drifted. There must be no `npm warn publish` lines; a warning
means npm silently rewrote a field.

```bash
cd installer && npm publish --access public
```

`--access public` is required on the **first** publish of a scoped package:
scoped packages default to private, and a private publish fails on the free
plan. `publishConfig.access` in `package.json` already sets it, so the flag is
belt-and-braces.

Verify from the registry rather than trusting the upload:

```bash
npm view @zbs-gg/zbs-researcher version maintainers
```

## The old unscoped package

`zbs-researcher@0.1.0` was published on 2026-07-21 from the personal account.
It is superseded, not deleted — point people at the new name:

```bash
npm deprecate zbs-researcher "Moved to @zbs-gg/zbs-researcher — npx -y @zbs-gg/zbs-researcher@latest"
```

Why not `npm unpublish`: the free 72-hour unpublish window closed on
2026-07-24, and unpublishing burns that version number permanently — `0.1.0`
could never be republished under that name. Deprecation shows a warning on
every install, is reversible (`npm deprecate <pkg> ""` clears it), and keeps
anyone who already depends on the old name working.

## Version agreement

Four files carry the version and the selftest enforces that three of them
agree:

- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json` (the `deep-research` entry)
- `installer/package.json`
- `CHANGELOG.md` (needs a matching `## <version>` heading)

`skills/deep-research/scripts/selftest.sh` step 3 pins the expected version —
bump it there too, or the smoke test fails on the next run.
