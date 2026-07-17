# last30days-skill — issue teardown → ZBS differentiation map

_Mined 2026-07-17 from mvanhorn/last30days-skill (52.5k★, 67 open issues). Each pain point below is a documented user complaint, not speculation — and a concrete place ZBS Research can be visibly better._

## The 7 differentiation points (ranked by leverage)

### 1. Works on Windows out of the box — theirs is broken (~30 Windows issues)
Their biggest structural weakness. `signal.SIGALRM` / `os.killpg` not on Windows (#97, #156), subprocess-timeout cleanup breaks (#110), `UnicodeEncodeError` writing reports (#167), latin-1 URL crash (#819). last30days effectively **does not run on Windows** — and most non-developer clients are on Windows. Our engine is stdlib + threading (no SIGALRM), so this is a near-free win. **Verify ZBS runs clean on Windows and say so loudly.**

### 2. Clean security posture — theirs flags 🔴 High Risk (#565)
A user installed it and the installer's own scan (Gen / Socket / Snyk) all returned **High Risk** — "runs with full agent permissions," pulls from many sources. For a **client** install this is a hard stop: a client sees "High Risk" and backs out. ZBS edge: least-privilege, a transparent "here's exactly what it does / what it sends where," and a clean scan. Plan-first transparency is the trust story here.

### 3. One key / $0 core — their key-zoo annoys people (#772, #149, #511, #524, #443)
Repeated demand: #772 "Single cheap api provider for all your keys," #149 "free sources zero API keys," #511 "Web UI, no CLI, no API keys." Users are irritated by wiring many keys. ZBS's **$0-first tier + one-Google-key-covers-many-channels** hits this dead-on. Their multiple ScrapeCreators-key-minting fixes (#524/#443/#401) show the setup friction is real and recurring.

### 4. Install that doesn't fail (#237, #362, #166)
Their marketplace install throws "Path escapes plugin directory: ./ (skills)" (#237, 4💬) and fails the Claude Code validator (#362, 4💬); startup crashes on a None config (#166). Our plugin already uses the correct `skills/<name>/SKILL.md` layout and **passes `claude plugin validate`**. Clean install is already an edge — keep it.

### 5. Smarter ranking — theirs is vote-count-only (#641)
#641: "Top Community Comments ranked by vote count only — off-topic comments dominate on niche topics." Their engagement ranking is naive, so on niche topics (exactly Nik's use cases) noise floats to the top. ZBS ideation idea #4 (comment-evidence ranking + relevance floor + anti-bot) is the direct answer — and niche topics are where it matters most.

### 6. Reddit that actually works — theirs is a patch parade (#825, #657, #696, #589)
Reddit fixed over and over: "stop reddit enrichment poisoning web results" (#825), arctic-shift scores (#696), ScrapeCreators-as-primary-backend pins (#657/#589). Confirms Nik's own experience — Reddit is claimed-working but fragile. ZBS defaults to Arctic Shift and is honest about score-field limits; don't repeat their fragility.

### 7. **Telegram** — nobody, the moat (from competitive scan)
Not in their issues because it's simply absent. The one edge no competitor contests.

## The money signal — #532 (this is the important one)

> "sometimes I just want to directly read or **subscribe to high-quality, pre-generated reports** … rather than setting up everything and running the pipeline entirely by myself every time."

A user, unprompted, asking to **pay-with-attention/subscribe to finished reports instead of running the tool.** This directly:
- **validates the done-for-you / managed layer** — demand for the *result*, not the tool, is documented in a competitor's own issues;
- **partially answers Nik's fear "people will just build it themselves via an agent"** — a real segment explicitly does NOT want to set it up. They want the output. That segment is the paying one.

## What this means for Nik's plan

- The **free skill** competes on: Windows-works, clean-security, one-key/$0, no-fail-install, smarter-ranking — all documented pains. That's a real "why switch from last30days" list, brand aside.
- The **paid hypothesis** now has evidence (#532): sell finished reports / managed Telegram-inclusive research to people who don't want to run the pipeline. Test cheaply: publish a few free ZBS reports, watch if "how do I subscribe / can you run this for X" shows up.
- **Reddit stays free-tier only** (GummySearch lesson + last30days' own Reddit fragility).
