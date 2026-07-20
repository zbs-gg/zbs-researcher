# Onboarding-wizard patterns (build reference)

_From this session's fact-checks on PostHog/Sentry wizards + Claude-skill mechanics + last30days NUX. Feeds U1 (SessionStart hook) and U2 (wizard flow)._

## PostHog wizard — the "magic" mechanics (what Nik loves)
`npx -y @posthog/wizard@latest` is an **agentic** CLI (uses Claude to read source), not a template engine. Flow:
1. **Autodetects** the framework across 16+ stacks (`--integration nextjs` override if needed).
2. **Browser OAuth mints the API key** — no copy-paste (`--api-key` escape hatch for CI).
3. **Edits real code** following the project's own patterns (not a boilerplate snippet).
4. **Secret-vault**: env/secret values aliased to opaque `secret:<uuid>` when file content is sent to the model, resolved back only at file-write time.
5. **Closes the loop**: walks the user to a first populated dashboard in-browser — payoff visible in the same session.
6. Stays useful after day one: audit / migrate / doctor.

**Why it lands** (three together): writes *working code* not instructions · browser auth removes all key handling · the reward (real data) appears before the session ends.

## Sentry's wizard spec (the industry checklist)
precondition check → auth + resource picker via API (DSN auto-fills, never typed) → short feature picklist (booleans) → SDK install + config gen → **secrets isolated into gitignored files**, never inlined → **a verification step that proves success** (example page with a test button). Rules: "one shell command + minimal simple inputs," **never silently re-enable a feature the user declined**, cover the 80%. Prisma/Clerk/Vercel echo the same: ask almost nothing, scaffold obviously-named files, sensible defaults.

**Shared ingredients:** autodetect → ask only what can't be inferred → sensible defaults → browser key retrieval over copy-paste → write config/code directly → one provable verification → secrets fenced from both app code and any AI/telemetry context.

## Replicating for a Claude Code SKILL (our case — simpler)
We're already inside the agent, so **the conversation IS the wizard** — no separate binary.
- **SessionStart hook** (Claude Code) runs before the session, detects which keys/accounts exist, injects that state so the agent knows what's configured before speaking. (There's also a Setup hook, Jan 2026.)
- Drive steps via `AskUserQuestion` (modal) with a **prose fallback** for non-modal hosts (Codex/Cursor/Gemini-CLI).
- **Key lookup priority:** process env → project config → global config → OS keychain — ask only for the missing.
- `--diagnose`/`--preflight` self-report shows state with **no network call**.
- **Proof before ask (most important for a paid-key prompt):** run the free tier first and show a real result before ever prompting for a costly key.

## last30days NUX — two directly reusable lessons
- Ships a **dual wizard**: "Claude Code Modal Flow" (Auto/Manual/Skip → consent → signup offer → source opt-in → first-topic picker, via `AskUserQuestion`) + an identical **Non-Modal Prose Flow** for Codex/Cursor/Gemini-CLI.
- **#750:** embed the welcome pitch **inside the first setup-modal question** — Claude Code folds standalone tool output behind "ctrl+o to expand" and a standalone welcome gets buried unread.
- **#524:** the maintainer **rejected silently auto-minting** a 3rd-party API key on first run — "explicit opt-in is the intended model." Directly relevant to our "just host it for me" tier: make it an **explicit named button**, never a silent default.

## Tiered-onboarding prior art (per rung)
- **Tier 0** (zero keys, works now): last30days keyless floor; **Vercel** `npx vercel` deploys to a live URL with no account, pitches signup only *after* it worked ("keep building," not "pay to start").
- **Tier 1** (paste a key): Sentry/PostHog `--api-key` flags; Stripe ships live test keys so code runs before signup.
- **Tier 2** (personal-risk account, strongly warned): Telegram userbot convention (Pyrogram/Telethon docs) — automating a *personal* account risks a ban; standard advice is a **dedicated/secondary account**. Reuse that warning language.
- **Tier 3** ("host it for me"): the safe version is one explicit, named signal — not an invisible default (per #524).
- **Pattern:** gate each tier behind one visible decision; show what's already unlocked free before pitching the next; keep the paid/connect ask cleanly separable so a zero-risk user stops at Tier 0 with real value.

## Sources
[PostHog/wizard](https://github.com/PostHog/wizard) · [PostHog AI wizard docs](https://posthog.com/docs/ai-engineering/ai-wizard) · [Sentry setup-wizard spec](https://develop.sentry.dev/sdk/expected-features/setup-wizards/) · [Claude Code hooks](https://code.claude.com/docs/en/hooks) · [last30days #750](https://github.com/mvanhorn/last30days-skill/issues) · [Pyrogram FAQ (account-ban warning)](https://docs.pyrogram.org/faq/)
