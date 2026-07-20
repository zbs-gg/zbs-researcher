# Publishing the `zbs-researcher` npm installer

Nik's guide. Publication is a manual action under Nik's npm login — never done
from an agent session. The package lives in `installer/` (name `zbs-researcher`,
verified free on the registry 2026-07-21).

## 0. One-time account hardening (REQUIRED before first publish)

Enable npm 2FA for auth **and** writes before the first `npm publish`:

```bash
npm profile enable-2fa auth-and-writes
```

Alternative (for CI/automation later, not needed for the first manual publish):
publish with provenance using a **package-scoped** automation token —
`npm publish --provenance` from a GitHub Actions workflow. Never use a
user-wide classic token for this package.

## 1. Publish steps

```bash
cd installer
npm login                      # Nik's npm account (2FA prompt)
npm pack --dry-run             # tarball review — see checklist below
npm publish --access public
```

### `npm pack --dry-run` checklist

The tarball must contain **exactly** these files, nothing more:

```
package.json
bin/cli.js
README.md
```

Anything else in the list (secrets, logs, .env, stray scripts) = STOP, fix
`files` in `package.json`, re-check.

## 2. Verify after publish

```bash
npx -y zbs-researcher@latest --dry-run   # prints the two claude commands, executes nothing
```

Cache gotcha: unpinned `npx` can serve a stale cached version right after a
publish. To verify a specific fresh version, pin it:

```bash
npx -y zbs-researcher@0.1.0 --dry-run
```

## 3. Incident response (one-liner)

If a token leaks or a bad version ships: **rotate the npm token immediately**
(revoke on npmjs.com → Access Tokens), then
`npm deprecate zbs-researcher@<bad> "compromised"` — deprecate, do not unpublish
(unpublish breaks pinned installs and has a 72-hour policy window anyway).

## 4. Version discipline

- The installer version (`installer/package.json`, currently `0.1.0`) is
  **independent** of the plugin version (`.claude-plugin/plugin.json`). Do not
  bump them in lockstep.
- Bump the installer only when the installer itself changes (copy, flags,
  commands it runs): patch for copy/robustness fixes, minor for new flags or
  behavior. The plugin updates flow through the marketplace — users do NOT need
  a new installer release for a new plugin version.
- Every publish = version bump first; npm refuses to republish an existing
  version, and that is a feature.
