# POC findings log

Tracks issues found while iterating on the isolated `/poc/generate` writer
(`app/poc/prompt.py`, `app/poc/writer.py`). Separate from `docs/logbook.md` —
that file is the record for the real, shipped pipeline; this POC is a
throwaway experiment that hasn't touched it. Entries here follow the same
shape in spirit (symptom, what's known, status) but only cover this isolated
code path.

---

## 1. OPEN, DEFERRED — anchor repetition across unrelated topics, no dedup mechanism

**What was found:** in a 4-trial round run across Career and Relationships
topics (Office Politics, Pay-scale, Attachment Styles, Quirky/Fun — all
distinct, unrelated topics), 3 of 4 independently converged on the same
anchor: kintsugi (Japanese gold-seam pottery repair). Each call is a fresh,
independent Sonnet request with no shared state, so this isn't a bug in the
mechanical sense — it's kintsugi being a strong, generically-applicable
metaphor (brokenness/repair/visible-seams maps onto almost any
self-worth-adjacent topic) that the model reaches for by default absent any
pressure not to.

**Why it isn't fixed:** the real pipeline has a non-repetition mechanism for
exactly this shape of problem — `MemoryRecord.fingerprint`
(`topic+angle+approach`) checked by the angle engine before a combination is
reused (blueprint.md Section 5/11). This POC has no equivalent: it's
stateless by design (one topic in, one Sonnet call, one JSON out — no
angle/approach sampling, no memory read/write, per the POC's own explicit
scope). Building a fix would mean adding cross-call state to something
deliberately built to have none, which is real, non-trivial scope creep for
a POC still validating whether the core writing style is any good.

**Status: explicitly deferred, per direct instruction — core content quality
takes priority over duplication handling while this is still a POC.** Not
forgotten, not silently absorbed into "the POC works fine" — if this line of
work continues past the POC stage, real repetition handling would need
either its own lightweight fingerprint check or a promotion into the real
pipeline's existing `MemoryRecord`/angle-engine machinery, not a bespoke
second mechanism.

**Not a `docs/logbook.md` entry** — that log's discipline rule is scoped to
the shipped pipeline; this file is this POC's equivalent for as long as the
POC stays a POC.

**Addendum — stronger evidence, same finding, still deferred (same session,
after the rule-2 anchor-verification rewrite):** attempted to run a
kintsugi-free trial round per direct instruction. 3 of 4 topics (Self-Doubt,
Imposter Syndrome, Reproductive Health) landed on kintsugi again on the first
call; up to 3 fresh retries each (4 attempts total per topic) still returned
kintsugi every single time — 12/12 attempts across those 3 topics. This is a
sharper version of the original finding: it isn't just that unrelated topics
*happen* to converge on the same anchor sometimes, it's that for a real
subset of topics kintsugi is close to the model's unconditional default,
strong enough that independent resampling doesn't escape it. This is
consistent with, not contradictory to, the rule-2 rewrite working as
intended — rule 2 only screens for *fabricated* anchors, and kintsugi is
genuinely real and well-documented, so it correctly passes that check every
time. The rewrite was never going to fix repetition; it isn't the same bug.
Still explicitly deferred, unchanged from above.

**Addendum 2 — a test-harness stopgap added, not a resolution (same session):**
`run_poc_writer()` gained an optional `recent_anchors: list[str] | None`
parameter (threaded through both `scripts/poc_writer.py` via `--exclude-anchors`
and `POST /poc/generate` via `recent_anchors` on the request body). When
provided, it's appended as one line to the user turn: "Do not use any of these
anchors, they've been used recently: {list}". **This is a manual, in-memory,
per-call exclusion list — there is still no persistence, no database, no
automatic tracking of what's been used.** It exists purely to let a human
running a test batch hand-feed known-recent anchors so a given round's read
isn't drowned in repeats, the way the round before this one was. It does not
solve the underlying problem: nothing stops the model from converging on
kintsugi (or anything else) again the moment a caller forgets to pass the
list, and nothing here would scale past a manually-curated handful of
exclusions. The real fix — state-aware, mirroring the production pipeline's
`MemoryRecord.fingerprint` check in the angle engine — is still open and still
not attempted.

---

## 2. RESOLVED — real "Failed to fetch" on the live `/poc` button, caused by a missing Railway env var, compounded by a CORS-masking bug

**Symptom:** clicking "Generate POC" on the live app (`wgs-studio.vercel.app/poc`)
after `gpt-5.5` became the default provider produced a generic browser
"Failed to fetch" — no HTTP status, no error detail, the kind of message
`fetch()` throws on a genuine network-level failure, not a clean HTTP error
response (same category of symptom as logbook #11 in the main pipeline).

**Investigation:** CORS preflight (`OPTIONS /poc/generate`) checked first and
was clean — `200`, correct `Access-Control-Allow-Origin`. A real, timed
`POST` with a matching `Origin` header returned a fast (~0.45s) `500
Internal Server Error` with **no CORS headers at all** on the response.
Two separate problems, found in this order:

1. **Root cause: `OPENAI_API_KEY_POC` was never set on Railway.** It was
   added to the local `backend/.env` file when `openai_provider.py` was
   built, but — same failure class as logbook #6 in the main pipeline
   ("Railway env vars only partially applied") — never propagated to the
   actual production service. `openai_provider._build_client()` correctly
   raised `RuntimeError("OPENAI_API_KEY_POC is not set...")` exactly as
   designed, but since `provider` now defaults to `"openai"` and the
   frontend always omits the field, every real click hit this path in
   production.
2. **Compounding bug: the resulting 500 had no CORS headers, so the browser
   reported "Failed to fetch" instead of a real error.** `routes/poc.py`'s
   `run_poc_writer(...)` call wasn't wrapped in `try/except` — an unhandled
   exception there propagates past `CORSMiddleware` (added via
   `app.add_middleware`, inside the stack) up to Starlette's
   `ServerErrorMiddleware` (outside it, added automatically), which returns
   a bare 500 with no CORS headers. The browser's CORS check then fails on
   the response itself, so `fetch()` never even resolves with the real
   status — it throws a generic network error instead. This would mask
   *any* future error on this route the same way, not just a missing key.

**Fix:**
1. `railway variables --service wgs-backend --set "OPENAI_API_KEY_POC=..."`
   — set directly against production. Confirmed present by name (not by
   printing the value) before considering it done. Triggered an automatic
   Railway redeploy, polled to `SUCCESS`.
2. `routes/poc.py`: wrapped the `run_poc_writer(...)` call in `try/except
   Exception`, converting any failure into a proper `HTTPException(502,
   ...)`. FastAPI's normal exception handling for `HTTPException` runs
   inside the middleware stack (unlike a truly unhandled exception), so the
   response correctly carries CORS headers regardless of what actually
   failed underneath.

**Verified, in this order:**
- Mocked failure through the full middleware stack (`TestClient`, an
  `Origin` header matching the real `FRONTEND_ORIGIN`) — confirmed the fixed
  route now returns `502` with `access-control-allow-origin` correctly
  present, versus the bare unheaded `500` from before the fix.
- Full backend suite: **127/127 passing**, unaffected.
- **Real, live, unmocked `POST` to production** using the exact frontend
  request shape (`{"topic_id": "mindset-self-doubt"}`, no `provider` field)
  — `200 OK` in 27.8s, real `gpt-5.5` content returned, correct
  `access-control-allow-origin: https://wgs-studio.vercel.app` on the
  response.

**Not a `docs/logbook.md` entry** — same reasoning as every other entry in
this file: scoped to the isolated POC, not the shipped pipeline. The
underlying *pattern* (env var never pushed to Railway; unhandled exceptions
losing CORS headers) mirrors two separate real incidents already documented
there (#6, #11/#12) — worth knowing if either resurfaces in the main
pipeline, but this specific incident is POC-only.
