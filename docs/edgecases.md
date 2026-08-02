# Edge Cases and Failure-State Specification: Instamart Discovery Engine

## 1. Purpose

This document defines the expected system behaviour for unusual, incomplete, conflicting, unsafe, or failure-prone conditions in the **Instamart Discovery Engine**.

It should be used together with:

- `problemstatement.md`
- `context.md`
- `architecture.md`
- `datamodel.md`
- `design.md`
- `ai_evals.md` — evaluation fixtures should reference the stable edge-case IDs defined here.

The goal is not to anticipate every possible production incident. The goal is to ensure that the first demonstrable version:

- does not silently corrupt evidence;
- does not present unsupported AI output as fact;
- remains usable during partial failures;
- exposes meaningful recovery actions;
- preserves lineage and auditability;
- handles external-source instability;
- gives Claude Code a testable definition of expected behaviour.

---

## 2. Scope

This specification covers edge cases across:

1. source configuration and ingestion;
2. raw artifact storage;
3. normalization, language, privacy, relevance, and deduplication;
4. thread reconstruction;
5. taxonomy classification and model calls;
6. embeddings and semantic search;
7. theme discovery;
8. insight synthesis and opportunity scoring;
9. research questions, RAG, answers, and citations;
10. human review and validation;
11. frontend interaction and responsive behaviour;
12. report generation and exports;
13. jobs, retries, caching, and infrastructure;
14. security and abuse;
15. data retention and evidence removal;
16. observability, cost, and operational controls.

---

## 3. Edge-Case Handling Principles

### 3.1 Never fail silently

Every failed or skipped item must have:

- a stable reason code;
- a safe human-readable explanation;
- a persisted status;
- an associated run, record, or request ID;
- an explicit retryability decision.

### 3.2 Preserve partial success

When safe, a run should complete as `partially_completed` rather than discard successful work because some records failed.

### 3.3 Raw evidence is immutable

Malformed or unsuitable source content may be excluded from analysis, but the raw artifact and collection result should remain available for audit according to retention rules.

### 3.4 Derived artifacts must not outlive their support invisibly

If evidence is removed, invalidated, or superseded, dependent themes, insights, answers, and reports must display a warning or be recalculated.

### 3.5 Counts are deterministic

No LLM-provided count is authoritative. Counts, percentages, distributions, and opportunity-score components must be calculated from stored data.

### 3.6 Absence of evidence is not evidence of absence

When the dataset cannot answer a question, the system should say so rather than manufacture a weak conclusion.

### 3.7 Contradiction is a normal research outcome

Conflicting evidence should be preserved and surfaced, not treated as a system failure.

### 3.8 Low confidence is usable when clearly qualified

Low-confidence classifications or findings may remain inspectable, but must not be included in default aggregates unless the configured threshold permits it.

### 3.9 Retries must be bounded and idempotent

A retry must not:

- duplicate paid jobs;
- duplicate source records;
- overwrite earlier research history;
- create duplicate theme or insight sets;
- continue forever.

### 3.10 The UI must represent degraded states honestly

The frontend must distinguish:

- loading;
- partial completion;
- stale data;
- unavailable source;
- unavailable model;
- low confidence;
- unsupported answer;
- hard failure.

---

## 4. Priority Levels

| Priority | Meaning | Required timing |
|---|---|---|
| `P0` | Evidence corruption, security, privacy, false claims, unrecoverable data loss, or paid-job duplication | Must be handled before demonstration |
| `P1` | Core workflow failure, misleading state, broken recovery, or unusable primary surface | Must be handled in MVP |
| `P2` | Important resilience, quality, accessibility, and unusual-data behaviour | Should be handled in MVP or immediately after |
| `P3` | Low-frequency polish, future scale, or advanced collaboration behaviour | May be deferred with documentation |

---

## 5. Standard Edge-Case Response Contract

Every handled edge case should define these six outcomes:

```text
Detection
    How the system identifies the condition.

Persisted state
    Which entity status, warning, failure code, or audit event is stored.

System behaviour
    Whether processing stops, skips, retries, degrades, or continues.

User experience
    What the researcher sees and which actions are available.

Recovery
    Whether automatic retry, manual retry, correction, or recalculation is possible.

Test
    The minimum automated or evaluation test proving the behaviour.
```

Recommended failure object:

```json
{
  "code": "SOURCE_RATE_LIMITED",
  "message": "The source temporarily rejected additional requests.",
  "retryable": true,
  "scope": "ingestion_run",
  "object_id": "run-uuid",
  "details": {
    "source": "reddit",
    "records_stored": 684
  }
}
```

Do not expose:

- stack traces;
- API keys;
- raw authorization headers;
- proxy credentials;
- internal network paths;
- unredacted personal information.

---

# Part I — Source Configuration and Ingestion

## 6. Source Configuration Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `SRC-001` | P1 | Required source target is missing | Reject run creation with `INVALID_SOURCE_CONFIG`; identify the missing field |
| `SRC-002` | P1 | Target identifier has only whitespace | Normalize to empty and reject |
| `SRC-003` | P0 | Configuration contains an API key or password in a JSON field | Reject or redact before persistence; secrets must use environment or secret storage |
| `SRC-004` | P1 | Unsupported connector type is requested | Reject with supported connector list |
| `SRC-005` | P2 | Disabled connector is selected | Prevent new run; existing historical data remains accessible |
| `SRC-006` | P1 | Requested record limit is zero or negative | Reject validation |
| `SRC-007` | P2 | Requested record limit exceeds system cap | Clamp only if product explicitly allows it; otherwise require correction |
| `SRC-008` | P1 | `date_from` is after `date_to` | Reject validation |
| `SRC-009` | P2 | Date range starts before source supports historical access | Continue with effective range warning |
| `SRC-010` | P2 | Date range ends in the future | Use current collection time as upper bound and record adjustment |
| `SRC-011` | P2 | Unsupported country or locale is requested | Reject or fall back only when fallback is explicit |
| `SRC-012` | P1 | Source URL uses unsupported protocol | Reject all protocols except permitted `https` and controlled `http` |
| `SRC-013` | P0 | Source URL resolves to internal or private network | Block as SSRF risk |
| `SRC-014` | P1 | Same paid collection request is submitted twice | Use idempotency key and return existing run |
| `SRC-015` | P2 | Source config is edited while a run is active | Active run uses immutable configuration snapshot; edits affect later runs only |
| `SRC-016` | P2 | Deleted source configuration has historical runs | Preserve historical run relationships; hide config from new-run selection |
| `SRC-017` | P2 | Connector implementation version changes | New runs record new implementation version; do not rewrite prior lineage |
| `SRC-018` | P1 | Estimated collection cost exceeds configured cap | Block launch unless an authorized override is provided |

### Required tests

- schema validation tests;
- secret-field rejection test;
- SSRF allowlist test;
- idempotent run-creation test;
- immutable configuration-snapshot test.

---

## 7. Source Availability and Access Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `ING-001` | P1 | Source returns `401` or `403` | Stop connector, mark non-retryable until access configuration changes |
| `ING-002` | P1 | Source returns `404` for target | Mark target unavailable; do not retry repeatedly |
| `ING-003` | P1 | Source returns `429` | Respect retry headers, apply bounded backoff, preserve checkpoint |
| `ING-004` | P1 | Source repeatedly returns `5xx` | Retry with backoff; mark partial or failed after limit |
| `ING-005` | P2 | DNS resolution fails | Retry as transient; preserve progress |
| `ING-006` | P2 | TLS certificate validation fails | Do not bypass certificate verification; fail safely |
| `ING-007` | P2 | Network disconnects mid-page | Discard incomplete response artifact unless checksum and parser validation pass |
| `ING-008` | P1 | Apify actor completes with partial dataset | Store available records and actor status; mark run `partially_completed` |
| `ING-009` | P1 | Apify actor times out but continues remotely | Prevent duplicate rerun until actor status is reconciled |
| `ING-010` | P2 | Official API and scraper return different counts | Preserve provenance; do not silently merge as equivalent coverage |
| `ING-011` | P2 | Source robots or terms disallow collection | Disable connector path and record compliance reason |
| `ING-012` | P1 | Page requires login or challenge | Do not bypass authentication controls; mark source unsupported |
| `ING-013` | P1 | Playwright receives CAPTCHA | Stop automated collection; no automated bypass |
| `ING-014` | P2 | Source layout changes and extraction returns zero records | Trigger parser-health warning before declaring legitimate empty result |
| `ING-015` | P1 | Source returns valid page with unexpected content type | Reject parsing and retain raw metadata |
| `ING-016` | P2 | Source is extremely slow | Enforce timeout and bounded retries |
| `ING-017` | P1 | Connector is rate limited after partial success | Keep collected records, checkpoint last successful page, surface partial coverage |
| `ING-018` | P2 | Provider status is unknown after client timeout | Reconcile by provider request or actor ID before resubmission |

---

## 8. Pagination and Checkpoint Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `CHK-001` | P1 | Source repeats the same page cursor | Detect repeated checkpoint and stop infinite loop |
| `CHK-002` | P1 | Cursor becomes invalid during resume | Start from last safe checkpoint or require full controlled restart |
| `CHK-003` | P2 | Page has fewer records than expected but provides next cursor | Continue while respecting limits |
| `CHK-004` | P2 | Final page has no explicit terminal signal | Infer terminal only using connector-specific validated rule |
| `CHK-005` | P1 | Checkpoint persisted after records but before artifact commit | Transaction or reconciliation must prevent skipped records |
| `CHK-006` | P1 | Artifact persisted but checkpoint commit fails | Resume must deduplicate by source-native ID |
| `CHK-007` | P2 | Checkpoint format changes between connector versions | Version checkpoint schema and migrate or restart safely |
| `CHK-008` | P1 | Two workers process the same checkpoint | Acquire distributed lock or use database uniqueness |
| `CHK-009` | P2 | Resume request uses a completed terminal checkpoint | Return completed state rather than launching new work |
| `CHK-010` | P2 | Source order changes between pages | Source-native uniqueness prevents duplicates; coverage warning may be recorded |
| `CHK-011` | P2 | Date-filtered pagination includes older records | Stop only using validated publication-date boundary logic |
| `CHK-012` | P1 | Clock or timezone mismatch causes records to cross date boundary | Store source timestamp and normalized UTC separately |

---

## 9. Source Record Integrity Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `REC-001` | P1 | Source-native ID is missing | Generate connector-scoped deterministic surrogate ID from stable fields and checksum |
| `REC-002` | P1 | Same native ID returns modified content | Preserve latest source item version or source edit metadata; do not silently overwrite raw artifact |
| `REC-003` | P2 | Record has no publication date | Store null; use ingestion date only for operational sorting, not publication trend |
| `REC-004` | P2 | Publication date is far in the future | Flag quality warning and exclude from trend until reviewed |
| `REC-005` | P2 | Publication date is earlier than platform existence | Flag invalid source timestamp |
| `REC-006` | P2 | Rating exists but rating-scale maximum is missing | Preserve native rating and exclude from normalized-rating calculations |
| `REC-007` | P1 | Rating exceeds rating scale | Flag malformed record and avoid normalized rating |
| `REC-008` | P2 | Engagement count is negative | Treat as malformed metadata and set null |
| `REC-009` | P2 | Post title exists but body is empty | Use title if sufficient; otherwise mark insufficient content |
| `REC-010` | P2 | Body exists but title is duplicated into body | Normalize without changing original text |
| `REC-011` | P2 | Text is only emojis | Retain raw record; mark low information unless research rules support emotion-only content |
| `REC-012` | P2 | Text contains only a URL | Mark insufficient content unless linked content is explicitly collected |
| `REC-013` | P2 | Record contains deleted-user placeholder | Preserve content; author hash remains null |
| `REC-014` | P1 | Record exceeds maximum safe size | Preserve raw object, truncate only analysis copy with explicit warning |
| `REC-015` | P2 | Record contains invalid Unicode | Repair normalization while retaining original bytes in raw artifact |
| `REC-016` | P2 | HTML entities remain encoded | Decode in normalized text; preserve original |
| `REC-017` | P0 | Source text contains executable HTML or scripts | Store as text; never render unsanitized HTML |
| `REC-018` | P2 | Comment is quoted entirely from another post | Detect quote-only or duplicate relation where possible |
| `REC-019` | P2 | Source returns the same record in multiple locales | Use native ID and source provenance to avoid duplicate canonical records |
| `REC-020` | P1 | Record source URL is malformed | Preserve source item but mark external-link unavailable |

---

# Part II — Raw Storage and Canonicalization

## 10. Raw Artifact Storage Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `RAW-001` | P0 | Object write fails after DB row creation | Roll back row or mark artifact unavailable; do not create canonical records |
| `RAW-002` | P0 | Object stored but DB transaction fails | Reconciliation job detects orphan object |
| `RAW-003` | P0 | Stored object checksum differs from recorded checksum | Quarantine artifact and stop downstream processing |
| `RAW-004` | P1 | Two objects attempt same storage key | Storage key must include run and item uniqueness; reject collision |
| `RAW-005` | P2 | Object storage temporarily unavailable | Retry boundedly; API remains responsive |
| `RAW-006` | P1 | Raw artifact exceeds configured storage size | Abort item or chunk only through connector-specific strategy |
| `RAW-007` | P2 | Storage retention expires while analysis is active | Delay deletion until dependent job completes |
| `RAW-008` | P0 | Raw artifact is mutated after creation | Immutable-object or checksum validation must detect it |
| `RAW-009` | P1 | Media type is missing | Infer cautiously from content; mark metadata warning |
| `RAW-010` | P2 | Compression is unsupported | Preserve original where possible; mark parsing failure |
| `RAW-011` | P0 | Path traversal characters appear in source identifier | Sanitize storage key and never use source value directly as path |
| `RAW-012` | P2 | Filesystem development storage runs out of space | Stop ingestion safely, preserve DB consistency, show actionable error |
| `RAW-013` | P2 | Artifact retention date is before creation date | Reject invalid retention metadata |
| `RAW-014` | P1 | Raw object is deleted manually outside application | Detect on access and mark lineage integrity warning |

---

## 11. Normalization Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `NRM-001` | P2 | Excessive whitespace and newlines | Collapse for normalized text while preserving original |
| `NRM-002` | P2 | Repeated punctuation carries sentiment | Do not remove all punctuation; normalize conservatively |
| `NRM-003` | P2 | Hashtags concatenate meaningful words | Preserve original and optionally derive tokenized analysis form |
| `NRM-004` | P2 | Mixed English and Hindi transliteration | Mark code-mixed; do not force a single language if confidence is low |
| `NRM-005` | P2 | Text is mostly source boilerplate | Remove only known, versioned boilerplate patterns |
| `NRM-006` | P1 | Normalization produces empty text | Mark insufficient content and preserve original |
| `NRM-007` | P1 | Normalized text checksum changes after code update | New normalization version must create a new derived representation |
| `NRM-008` | P2 | HTML line breaks encode paragraph meaning | Preserve paragraph separation |
| `NRM-009` | P2 | Unicode normalization changes visually similar characters | Retain original and record normalization version |
| `NRM-010` | P2 | Long repeated characters are expressive | Cap only for feature extraction, not displayed normalized meaning |
| `NRM-011` | P2 | Product names have unusual casing | Avoid aggressive lowercasing in displayed normalized text |
| `NRM-012` | P1 | Text contains null bytes or control characters | Strip unsafe control characters and log quality event |

---

## 12. Language Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `LNG-001` | P2 | Language detector confidence is below threshold | Mark language unknown; do not force classification |
| `LNG-002` | P2 | One short record is ambiguous across languages | Preserve and mark low confidence |
| `LNG-003` | P2 | English-Hindi code mixing is detected | Route to supported code-mixed prompt or model |
| `LNG-004` | P2 | Unsupported language is detected | Retain record; set `unsupported_language`; exclude from default analysis |
| `LNG-005` | P2 | Emojis and product names dominate detector | Do not trust detector without minimum text threshold |
| `LNG-006` | P2 | Source language hint conflicts with detector | Store both; use detected result with conflict warning |
| `LNG-007` | P3 | Transliteration and native script appear together | Preserve both; future multilingual pipeline may process |
| `LNG-008` | P1 | Hosted model is asked to translate unsupported content automatically | Do not translate silently; translation must be explicit and versioned |
| `LNG-009` | P2 | Unsupported language is part of a multilingual thread | Preserve thread relationship while excluding record from synthesis |
| `LNG-010` | P2 | Language model changes between runs | New analysis run records language-detection version |

---

## 13. Privacy and Redaction Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `PII-001` | P0 | Email address is present | Redact in analysis and UI text; original remains protected in raw storage |
| `PII-002` | P0 | Phone number is present in multiple formats | Normalize detector coverage and replace with `[PHONE]` |
| `PII-003` | P0 | Order ID resembles ordinary number | Use context-aware redaction and retain confidence |
| `PII-004` | P0 | Delivery address is present | Redact address components; do not expose in evidence inspector |
| `PII-005` | P0 | Payment identifier or UPI ID is present | Redact and add privacy event |
| `PII-006` | P1 | Person name is also a brand or product | Do not over-redact without confidence or context |
| `PII-007` | P1 | Redaction offsets become invalid after normalization | Evidence spans must reference their correct text variant |
| `PII-008` | P0 | Redacted text accidentally contains original value in metadata | Sanitize metadata and logs |
| `PII-009` | P1 | Redaction removes the meaning required for research | Preserve safe category token and indicate redacted context |
| `PII-010` | P0 | Public username is used as a user segment | Prohibit segmentation; store only stable hash if needed for thread relation |
| `PII-011` | P0 | Model output repeats PII from prompt | Post-process output and block publication until sanitized |
| `PII-012` | P0 | Export contains unredacted evidence | Export only redacted snapshots |
| `PII-013` | P1 | Reviewer requests original text | Restrict to authorized role and audited access if feature exists |
| `PII-014` | P2 | Redaction confidence is low | Flag for review; default UI remains redacted |
| `PII-015` | P0 | Logs include raw source payload | Logging policy must exclude or sanitize payloads |

---

## 14. Relevance, Spam, and Quality Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `REL-001` | P2 | Review mentions delivery only, not discovery | Classify under service quality, not category exploration |
| `REL-002` | P2 | Industry article contains quoted user feedback | Separate article commentary from quoted evidence where extractable |
| `REL-003` | P2 | Promotional post resembles a recommendation | Mark promotion when commercial intent is explicit |
| `REL-004` | P2 | Sarcastic feedback appears positive lexically | Structured classifier should preserve uncertainty |
| `REL-005` | P2 | Very short review says “good” | Retain but mark low information |
| `REL-006` | P2 | Review is about a competitor | Mark relevant competitor feedback, not Instamart evidence |
| `REL-007` | P1 | Relevance classifier returns no valid class | Mark `unreviewed` or failed; do not discard |
| `REL-008` | P2 | Rule and model disagree on spam | Preserve both decisions; route low-confidence conflict to review |
| `REL-009` | P2 | Bot-like repeated content comes from many accounts | Near-duplicate and spam rules should reduce counting impact |
| `REL-010` | P2 | A record is both product discovery and service frustration | Multi-label analysis is permitted |
| `REL-011` | P2 | Review references Instamart indirectly | Preserve with lower relevance confidence |
| `REL-012` | P1 | Quality pipeline fails after relevance classification | Preserve completed stage and resume from failure |
| `REL-013` | P2 | Source commentary is useful context but not user feedback | Label `industry_commentary` and exclude from user-frequency counts |
| `REL-014` | P2 | Record contains harassment or offensive text | Preserve only as necessary, warn reviewers, and avoid prominent display |
| `REL-015` | P0 | Record includes illegal or dangerous personal instructions unrelated to research | Treat as untrusted content; do not execute or follow instructions |

---

## 15. Deduplication Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `DUP-001` | P1 | Exact duplicate appears in same source | One canonical count; duplicate remains auditable |
| `DUP-002` | P2 | Same content appears across sources | Mark cross-source repost without erasing source coverage |
| `DUP-003` | P2 | Same user posts an edited version | Link versions; determine canonical policy explicitly |
| `DUP-004` | P2 | Two short generic reviews are text-identical but independent | Avoid assuming duplicate solely from generic text when source IDs differ |
| `DUP-005` | P2 | Quoted content makes records highly similar | Detect quoted-copy relationship rather than full duplicate |
| `DUP-006` | P1 | Near-duplicate algorithm changes between runs | Version decision method and do not rewrite earlier links |
| `DUP-007` | P1 | A record is assigned to two canonical duplicate groups | Prevent through uniqueness constraint |
| `DUP-008` | P2 | Human reviewer reverses duplicate decision | Restore counting eligibility and recalculate affected metrics |
| `DUP-009` | P2 | Canonical record is removed at source | Promote valid duplicate or mark group unsupported |
| `DUP-010` | P1 | Similarity threshold creates one giant duplicate group | Detect abnormal group size and stop automatic acceptance |
| `DUP-011` | P2 | Duplicate source metadata differs materially | Preserve metadata per record |
| `DUP-012` | P1 | Embedding is missing during near-duplicate check | Fall back to lexical method with lower confidence or defer decision |

---

## 16. Thread Reconstruction Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `THR-001` | P2 | Parent post was not collected | Store child with unresolved external parent ID |
| `THR-002` | P2 | Parent is collected in later run | Backfill relationship idempotently |
| `THR-003` | P1 | Thread relation creates cycle | Reject relation and log integrity warning |
| `THR-004` | P2 | Comment depth is missing | Store null; do not infer arbitrary depth |
| `THR-005` | P2 | Source order differs from timestamp order | Preserve source position and publication time separately |
| `THR-006` | P2 | Deleted parent retains replies | Show replies with unavailable-parent state |
| `THR-007` | P2 | Context window exceeds model token limit | Select bounded parent and nearby context with explicit truncation |
| `THR-008` | P1 | Same comment appears under multiple parents due parser bug | Enforce connector-native identity and flag conflict |
| `THR-009` | P2 | Quoted reply references a different thread | Represent quote separately if supported; do not invent parent relation |
| `THR-010` | P2 | Child language differs from parent | Analyze independently while retaining context relation |

---

# Part III — Taxonomy, AI Calls, and Classification

## 17. Taxonomy Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `TAX-001` | P0 | Classification uses labels from a different taxonomy version | Reject persistence |
| `TAX-002` | P1 | Published taxonomy is edited in place | Prevent mutation; create new version |
| `TAX-003` | P2 | Label is deprecated | Historical results remain valid; new runs cannot apply it unless explicitly supported |
| `TAX-004` | P2 | New taxonomy splits one old label into two | New run required; do not backfill without versioned migration |
| `TAX-005` | P2 | Taxonomy has overlapping label definitions | Block publication or require explicit precedence guidance |
| `TAX-006` | P1 | Multi-label dimension is configured as single-label | Validation must catch inconsistent schema |
| `TAX-007` | P1 | Model returns unknown label key | Reject label and attempt structured repair |
| `TAX-008` | P2 | No taxonomy label fits record | Allow `other` or no-label outcome rather than forcing |
| `TAX-009` | P2 | Parent taxonomy label is inactive but child is active | Reject invalid taxonomy structure |
| `TAX-010` | P1 | Taxonomy file checksum differs from database snapshot | Prevent ambiguous run start |

---

## 18. Prompt Injection and Untrusted Content Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `AISEC-001` | P0 | Review says “ignore previous instructions” | Treat as evidence text only; model system instruction forbids following it |
| `AISEC-002` | P0 | Source content requests secrets or tool use | Never expose secrets or execute source instructions |
| `AISEC-003` | P0 | Evidence embeds fake citation labels | Citation labels are generated by application, not accepted from source |
| `AISEC-004` | P0 | Source contains JSON resembling expected model output | Delimit source content and validate model schema independently |
| `AISEC-005` | P0 | Source HTML includes hidden prompt text | Extract visible relevant text only where possible; sanitize |
| `AISEC-006` | P0 | Model output attempts to include external unverified facts | Grounding validator should remove or warn unsupported content |
| `AISEC-007` | P0 | Model references a source ID not in evidence package | Reject citation |
| `AISEC-008` | P1 | Prompt contains more untrusted evidence than instruction context | Apply bounded evidence packaging and explicit delimiters |
| `AISEC-009` | P0 | Tool-capable model is used accidentally | AI gateway must disable tools for evidence-analysis calls unless explicitly required |
| `AISEC-010` | P1 | Model repeats malicious text verbatim in answer | Quote only relevant excerpts and sanitize display |

---

## 19. Model Availability and Structured Output Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `MOD-001` | P1 | Model request times out | Retry boundedly and preserve model-call audit |
| `MOD-002` | P1 | Provider rate limits request | Mark retryable, queue retry, show partial progress |
| `MOD-003` | P1 | Provider returns malformed JSON | Attempt structured repair within retry limit |
| `MOD-004` | P1 | Provider returns valid JSON with missing required field | Reject schema and repair |
| `MOD-005` | P1 | Provider returns an unexpected enum | Reject field; do not coerce to closest label silently |
| `MOD-006` | P2 | Model refuses content | Mark failed or route to safe fallback prompt; do not fabricate result |
| `MOD-007` | P1 | Model response is truncated | Detect invalid structure; retry with reduced batch or larger allowed output |
| `MOD-008` | P1 | Input exceeds context limit | Chunk or summarize deterministically; record truncation and input strategy |
| `MOD-009` | P2 | Provider reports successful request but empty output | Treat as invalid output |
| `MOD-010` | P1 | Retry returns different classification | Preserve all model calls; accepted output follows configured retry policy |
| `MOD-011` | P2 | Model configuration is disabled mid-run | Active jobs use snapshot; new calls fail or switch only through explicit run policy |
| `MOD-012` | P0 | Provider key is missing | Fail configuration check before queuing paid work |
| `MOD-013` | P1 | Provider pricing changes | New cost entries use new pricing snapshot; historical costs remain unchanged |
| `MOD-014` | P2 | Provider usage count is unavailable | Store estimated usage and mark estimate |
| `MOD-015` | P1 | AI budget cap is reached mid-run | Stop new calls, preserve completed work, mark partial |
| `MOD-016` | P2 | Model latency is unusually high | Continue within timeout; record metric and degradation warning |
| `MOD-017` | P1 | Fallback model uses incompatible output schema | Do not switch unless compatibility is validated |
| `MOD-018` | P0 | Model output contains unredacted PII | Sanitize and prevent publication until passed |

---

## 20. Classification Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `CLS-001` | P2 | Record has mixed positive and negative sentiment | Use `mixed` and preserve signed score uncertainty |
| `CLS-002` | P2 | Sarcasm lowers sentiment confidence | Retain label with lower confidence |
| `CLS-003` | P2 | Multiple exploration barriers appear | Apply multi-label output |
| `CLS-004` | P2 | No barrier is present | Do not force a barrier label |
| `CLS-005` | P1 | Severity is provided without evidence span | Accept only if schema permits; mark explanation weakness |
| `CLS-006` | P1 | Evidence span offsets exceed text length | Reject span and repair or store label without span warning |
| `CLS-007` | P1 | Evidence span refers to normalized text but marked original | Reject inconsistent variant |
| `CLS-008` | P2 | Overall confidence is lower than all label confidences | Permit only if definition justifies it; otherwise flag anomaly |
| `CLS-009` | P2 | Human correction contradicts model output | Preserve both; human-reviewed version controls reviewed aggregates |
| `CLS-010` | P1 | Two active analyses exist for same record and run | Prevent through uniqueness |
| `CLS-011` | P2 | Classification changes materially after prompt version update | New run; comparison view may show drift |
| `CLS-012` | P2 | Rule-derived and model-derived labels conflict | Store provenance and apply configured precedence |
| `CLS-013` | P2 | Unsupported-language record reaches classifier | Stop and mark pipeline routing error |
| `CLS-014` | P2 | Duplicate record is classified separately | Permitted for audit, but duplicate excluded from default theme counts |
| `CLS-015` | P1 | Classification batch partially succeeds | Persist successful rows, retry failed items only |
| `CLS-016` | P2 | Record changes at source after classification | Mark analysis stale and require new analysis version |
| `CLS-017` | P0 | Model infers age, gender, income, or location without explicit evidence | Remove inference and add violation warning |
| `CLS-018` | P1 | Model labels industry commentary as user frustration | Relevance-class compatibility validation should catch it |
| `CLS-019` | P2 | Confidence threshold changes | Recalculate inclusion views without rewriting stored confidence |
| `CLS-020` | P1 | Classification job is repeated after success | Idempotency prevents duplicate analysis row |

---

# Part IV — Embeddings and Retrieval Index

## 21. Embedding Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `EMB-001` | P1 | Embedding provider fails for one record | Persist failure and continue batch |
| `EMB-002` | P0 | Returned vector dimension does not match configuration | Reject vector |
| `EMB-003` | P1 | Empty text reaches embedder | Skip and flag pipeline error |
| `EMB-004` | P2 | Text exceeds embedding input limit | Apply versioned truncation or chunking strategy |
| `EMB-005` | P1 | Text checksum changed since vector creation | Mark embedding stale and create new vector |
| `EMB-006` | P1 | Same text is embedded twice under same configuration | Unique constraint or idempotent upsert prevents duplicate |
| `EMB-007` | P2 | Local model and hosted model use same version key | Require globally unique configuration key |
| `EMB-008` | P1 | pgvector extension is unavailable | Fail health check before analysis |
| `EMB-009` | P2 | Approximate index has not yet included new vectors | Use exact fallback or mark indexing delay |
| `EMB-010` | P2 | Similarity score is NaN or outside expected range | Reject result |
| `EMB-011` | P2 | Code-mixed records retrieve poorly | Evaluation should expose language-specific retrieval gap |
| `EMB-012` | P1 | Embedding configuration is changed during run | Run uses immutable configuration |
| `EMB-013` | P2 | Object referenced by embedding was soft-deleted | Exclude from retrieval |
| `EMB-014` | P1 | Vector storage write succeeds but record status update fails | Reconcile by configuration, object ID, and checksum |

---

## 22. Hybrid Retrieval Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `RET-001` | P1 | Vector search returns no results | Fall back to keyword and structured filters |
| `RET-002` | P2 | Keyword and vector results disagree | Reranker considers both and preserves score provenance |
| `RET-003` | P1 | Exact count question is answered using semantic results only | Route to deterministic aggregation |
| `RET-004` | P2 | Search term is a taxonomy label synonym | Expand through versioned synonym map |
| `RET-005` | P2 | Search returns many duplicates | Apply duplicate and source-diversity controls |
| `RET-006` | P2 | Top results all come from one source | Apply source-diversity balancing and warn if unavoidable |
| `RET-007` | P2 | Date filter excludes all candidates | Return empty evidence state, not broad unfiltered results |
| `RET-008` | P1 | Retrieved object belongs to another analysis run | Reject cross-version mixing unless explicitly requested |
| `RET-009` | P2 | Theme result is relevant but has no current evidence | Exclude or mark stale |
| `RET-010` | P2 | Reranker fails | Use pre-rerank ordering with warning |
| `RET-011` | P1 | Retrieval result references deleted object | Exclude and log integrity event |
| `RET-012` | P2 | Query is shorter than semantic minimum, such as “why?” | Use session context or request clarification in answer |
| `RET-013` | P2 | Search text includes unsupported special syntax | Escape and treat as text unless advanced query mode exists |
| `RET-014` | P2 | Full-text search parser fails on punctuation | Fall back to safe plain-text query |
| `RET-015` | P1 | Evidence-package token budget is exceeded | Select diverse top evidence and record omitted count |
| `RET-016` | P2 | Contradictory evidence ranks below top K | Run dedicated contradiction retrieval |
| `RET-017` | P2 | Theme and insight summaries repeat the same evidence | Deduplicate evidence package by record |
| `RET-018` | P1 | Retrieval cache belongs to old theme set | Version cache key and invalidate |

---

# Part V — Themes and Insights

## 23. Theme Discovery Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `THM-001` | P1 | Eligible dataset contains no records | Do not run clustering; publish empty state with reason |
| `THM-002` | P2 | Dataset has too few records for configured algorithm | Use small-data fallback or require manual grouping |
| `THM-003` | P2 | All records become one cluster | Flag low usefulness; do not present as high-quality theme set |
| `THM-004` | P2 | Nearly every record becomes an outlier | Flag low coverage and review embedding or parameters |
| `THM-005` | P2 | Hundreds of tiny clusters are produced | Apply minimum cluster size or theme consolidation |
| `THM-006` | P2 | Two clusters receive near-identical names | Detect semantic duplication and route to merge review |
| `THM-007` | P2 | One cluster contains opposing behaviours | Preserve contradiction or split after coherence review |
| `THM-008` | P1 | Theme has no representative record | Do not publish theme |
| `THM-009` | P2 | Theme has records from only one source | Publish with source-concentration warning |
| `THM-010` | P2 | Theme name overstates causality | Rewrite to descriptive language |
| `THM-011` | P2 | Theme name includes inferred demographic | Reject or remove inferred segment |
| `THM-012` | P2 | Clustering is unstable across repeated runs | Store stability score and avoid high-confidence presentation |
| `THM-013` | P1 | Theme membership references ineligible record | Reject persistence |
| `THM-014` | P2 | Duplicate records inflate a cluster | Default membership metrics use primary records only |
| `THM-015` | P2 | A record belongs meaningfully to multiple themes | Multiple memberships are permitted with scores |
| `THM-016` | P2 | Theme membership score is below threshold | Retain as low-confidence or omit from default theme count |
| `THM-017` | P1 | Theme metrics disagree with membership count | Recalculate and block publication |
| `THM-018` | P2 | Trend appears due to source-volume increase | Display normalized share and coverage context |
| `THM-019` | P2 | Representative records are all highly engaged posts | Diversity selection must include ordinary records |
| `THM-020` | P2 | Cluster summary ignores contradictory records | Theme synthesis prompt must receive contradictions |
| `THM-021` | P2 | Human reviewer merges two themes | Create reviewed version or relation; recalculate metrics |
| `THM-022` | P2 | Human reviewer splits a theme | Create new theme version and memberships |
| `THM-023` | P1 | Theme set is regenerated while report uses prior set | Existing report remains version-pinned |
| `THM-024` | P2 | Theme model call fails after clustering succeeds | Preserve provisional clusters; show synthesis pending |
| `THM-025` | P2 | Theme contains industry commentary and user evidence | Metrics distinguish record roles |

---

## 24. Theme Metric Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `MET-001` | P1 | Denominator is zero | Return null or `not_applicable`, never divide by zero |
| `MET-002` | P2 | Rating is unavailable for most records | Show sample size and missing share |
| `MET-003` | P2 | Publication date is missing | Exclude from time trend and show undated count |
| `MET-004` | P1 | Metric logic version changes | New metric rows use new version; old results remain auditable |
| `MET-005` | P2 | Theme score uses a missing component | Re-normalize only if scoring profile specifies it; otherwise mark unscored |
| `MET-006` | P1 | Opportunity-score weights do not sum correctly | Reject scoring-profile publication |
| `MET-007` | P2 | Score is dominated by one large source | Source breadth component and warning should expose concentration |
| `MET-008` | P2 | Count includes low-confidence memberships unexpectedly | Metric query must state threshold |
| `MET-009` | P1 | Cached metric differs from database | Invalidate and recalculate |
| `MET-010` | P2 | A theme's score changes after evidence removal | Mark downstream insight and report stale |

---

## 25. Insight Synthesis Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `INS-001` | P0 | Insight has no evidence relationship | Do not publish |
| `INS-002` | P0 | Insight claims causality from public feedback | Rewrite as association or hypothesis |
| `INS-003` | P0 | Insight invents a user segment | Reject unsupported segmentation |
| `INS-004` | P1 | Insight includes a count not present in deterministic metrics | Reject or replace with database value |
| `INS-005` | P2 | Insight is supported by one record only | Label as observation, not repeated insight |
| `INS-006` | P2 | Supporting evidence comes from one source only | Add source-concentration warning |
| `INS-007` | P2 | Contradictory evidence exists but insight omits it | Grounding validation adds contradiction |
| `INS-008` | P2 | Insight repeats theme summary without interpretation | Mark low-value synthesis or regenerate |
| `INS-009` | P2 | Product implication is too prescriptive | Frame as opportunity or test, not roadmap command |
| `INS-010` | P1 | Product hypothesis lacks validation recommendation | Block publication as hypothesis |
| `INS-011` | P2 | Confidence is high despite low theme stability | Cap or flag confidence |
| `INS-012` | P2 | Insight evidence is later rejected by reviewer | Recalculate support and mark stale |
| `INS-013` | P2 | Two insights are duplicates | Detect and merge or retain relationship |
| `INS-014` | P2 | Insight contains outdated source coverage period | Display pinned period |
| `INS-015` | P2 | Opportunity score exists but components are hidden | Detail view must expose components |
| `INS-016` | P1 | Insight model returns malformed evidence IDs | Reject unresolved links |
| `INS-017` | P2 | Insight overgeneralizes competitor evidence to Instamart | Qualify source context |
| `INS-018` | P1 | Insight set generation partially fails | Publish draft with completed insights only; not final set |
| `INS-019` | P2 | Human edits insight meaning but keeps old citations | Require citation revalidation |
| `INS-020` | P2 | Evidence role changes from supporting to contradictory | Update insight support state and audit event |

---

# Part VI — Research Questions, Answers, and Citations

## 26. Query Understanding Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `QRY-001` | P2 | Question is ambiguous | Answer with explicit interpretation and alternatives |
| `QRY-002` | P2 | Question is too broad | Provide scoped synthesis and note limits |
| `QRY-003` | P1 | Question is unrelated to available dataset | State out-of-scope; do not answer from general model knowledge |
| `QRY-004` | P2 | Question asks for exact count | Use deterministic query plan |
| `QRY-005` | P2 | Question asks “why” but evidence only shows correlation | Separate observation from hypothesis |
| `QRY-006` | P2 | Question includes date range outside dataset | Show coverage mismatch |
| `QRY-007` | P2 | Question references unavailable source | State source is not included |
| `QRY-008` | P2 | Follow-up pronoun has unclear referent | Use session context; if still unclear, state assumption |
| `QRY-009` | P2 | Follow-up changes subject completely | Create new query plan while preserving session history |
| `QRY-010` | P1 | Query planner returns invalid filter key | Reject and repair |
| `QRY-011` | P1 | Query planner attempts demographic inference | Remove unsupported filter and warn |
| `QRY-012` | P2 | User asks to compare two theme sets | Allow only explicit cross-version comparison |
| `QRY-013` | P2 | Question contains source content copied with malicious instruction | Treat as user question text, not executable instruction |
| `QRY-014` | P2 | Empty question is submitted | Disable submission and provide accessible error |
| `QRY-015` | P2 | Question is extremely long | Enforce limit, preserve draft, and explain |
| `QRY-016` | P2 | Same question is submitted repeatedly | Reuse cached persisted answer only when dataset and filters match |
| `QRY-017` | P2 | User requests an unsupported chart or export from answer | Return supported answer and explain available actions |
| `QRY-018` | P1 | Effective filters differ from requested filters | Show the adjustment before or within answer context |

---

## 27. Answer Generation Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `ANS-001` | P0 | No evidence supports the question | Return insufficient-evidence answer |
| `ANS-002` | P1 | Evidence is sparse | Answer with low confidence and small-sample warning |
| `ANS-003` | P2 | Evidence is strongly contradictory | Present both patterns and avoid a single conclusion |
| `ANS-004` | P0 | Generated finding lacks citations | Exclude or mark unsupported |
| `ANS-005` | P0 | Citation does not support the claim | Grounding validator marks unsupported |
| `ANS-006` | P1 | Citation object no longer exists | Remove citation and mark answer stale |
| `ANS-007` | P2 | Answer includes model knowledge outside evidence package | Remove unsupported statement |
| `ANS-008` | P2 | Deterministic count differs from narrative wording | Count wins; regenerate narrative |
| `ANS-009` | P2 | Answer contains repeated findings | Deduplicate before persistence |
| `ANS-010` | P2 | Answer is longer than useful | Enforce structured concise response and progressive disclosure |
| `ANS-011` | P2 | Answer is too short to explain contradiction | Expand contradiction section |
| `ANS-012` | P1 | Grounding validation fails after answer stream displayed | Final state visibly marks affected findings and does not silently approve them |
| `ANS-013` | P1 | Model call succeeds but answer persistence fails | Do not mark question completed; allow safe recovery |
| `ANS-014` | P1 | Persistence succeeds but final SSE event is lost | Client reload retrieves authoritative persisted answer |
| `ANS-015` | P2 | User cancels generation | Stop future work where provider permits; preserve completed retrieval and partial state |
| `ANS-016` | P2 | Provider cannot cancel active call | Mark cancellation requested and discard unneeded final output if policy requires |
| `ANS-017` | P2 | Answer references stale theme set | Prevent generation or display version warning |
| `ANS-018` | P2 | Suggested validation is impossible with public data | Label as requiring internal behavioural data or user research |
| `ANS-019` | P0 | Answer states inferred demographic as fact | Reject finding |
| `ANS-020` | P2 | Answer calls a hypothesis “proven” | Rewrite to appropriate knowledge type |
| `ANS-021` | P2 | Answer includes only high-engagement posts | Evidence selection should include diversity |
| `ANS-022` | P2 | Findings use different denominators | State denominator per finding |
| `ANS-023` | P2 | Answer contains removed evidence | Mark stale and trigger revalidation |
| `ANS-024` | P1 | Citation count field differs from citation rows | Recalculate and prevent publication |

---

## 28. Streaming and SSE Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `SSE-001` | P1 | Client disconnects mid-stream | Server continues or cancels according to policy; persisted state remains authoritative |
| `SSE-002` | P1 | Client reconnects | Resume from event ID if supported or fetch current persisted status |
| `SSE-003` | P2 | Events arrive out of order | Sequence numbers allow client to ignore stale events |
| `SSE-004` | P1 | Duplicate event is received | Client handles idempotently |
| `SSE-005` | P1 | Stream closes without terminal event | Client polls final question state |
| `SSE-006` | P2 | Partial text contains unvalidated citation | Do not render citation as final until validated |
| `SSE-007` | P2 | Warning arrives after finding text | Insert warning beside finding with accessible announcement |
| `SSE-008` | P2 | Network switches from Wi-Fi to mobile | Reconnect without duplicate question submission |
| `SSE-009` | P2 | Browser suspends background tab | On resume, refresh authoritative status |
| `SSE-010` | P1 | Load balancer buffers SSE | Configure no-buffering and heartbeat events |
| `SSE-011` | P2 | Heartbeat events are mistaken for content | Client ignores non-content events |
| `SSE-012` | P1 | User opens same active question in two tabs | Both tabs observe same persisted job and events |

---

## 29. Citation and Evidence Inspection Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `CIT-001` | P0 | Citation label points to wrong object | Prevent persistence |
| `CIT-002` | P1 | Two findings use same label for different objects | Citation labels must be answer-scoped and unique |
| `CIT-003` | P2 | Evidence excerpt is unavailable after retention | Show metadata and removed-evidence warning |
| `CIT-004` | P2 | Source URL is dead | Preserve evidence snapshot and show unavailable external link |
| `CIT-005` | P2 | Source URL requires login | Show source limitation; do not promise direct access |
| `CIT-006` | P1 | Evidence inspector loads a record from another run context | Show lineage but prevent misleading active-context inclusion |
| `CIT-007` | P2 | Evidence has multiple theme roles | Show all memberships with current theme highlighted |
| `CIT-008` | P2 | Excerpt is very long | Show bounded excerpt with expand action |
| `CIT-009` | P2 | Excerpt is only redaction placeholders | Explain privacy redaction and avoid overinterpretation |
| `CIT-010` | P2 | Citation preview fails | Main answer remains usable; allow full evidence route |
| `CIT-011` | P2 | User navigates rapidly through citations | Cancel stale preview requests |
| `CIT-012` | P1 | Citation links to rejected evidence | Mark rejected and revalidate finding |
| `CIT-013` | P2 | Theme citation has no representative evidence | Show theme summary with warning |
| `CIT-014` | P1 | Citation validator times out | Answer completes with grounding pending, not passed |
| `CIT-015` | P2 | Same evidence supports and contradicts different claims | Roles remain finding-specific |

---

# Part VII — Validation and Human Review

## 30. Evaluation Dataset Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `EVAL-001` | P1 | Evaluation dataset has zero items | Block evaluation run |
| `EVAL-002` | P2 | Sample is heavily source-skewed | Display selection-bias warning |
| `EVAL-003` | P1 | Locked gold dataset is edited | Prevent mutation |
| `EVAL-004` | P2 | Taxonomy version does not match evaluated analysis | Require compatible mapping or reject |
| `EVAL-005` | P2 | Gold item references deleted record | Mark item unavailable and dataset affected |
| `EVAL-006` | P2 | No adjudicated gold output exists | Exclude from final metric |
| `EVAL-007` | P2 | Evaluation metric denominator is zero | Return not applicable |
| `EVAL-008` | P2 | Metric sample size is too small | Show sample-size warning |
| `EVAL-009` | P1 | Evaluation run partially fails | Persist available metrics with warning |
| `EVAL-010` | P2 | New prompt evaluated on old cached output | Ensure model-output version matches run |
| `EVAL-011` | P2 | Retrieval gold set has multiple valid evidence items | Support graded relevance |
| `EVAL-012` | P2 | Grounding evaluator disagrees with human review | Preserve both and route for adjudication |

---

## 31. Human Review Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `REV-001` | P1 | Two reviewers edit the same object concurrently | Use optimistic concurrency and conflict resolution |
| `REV-002` | P1 | Reviewer edits stale version | Warn and require merge or refresh |
| `REV-003` | P2 | Reviewer accepts without inspecting evidence | Product may warn or require evidence open for sensitive review types |
| `REV-004` | P2 | Reviewer rejects without reason | Require reason for configured objects |
| `REV-005` | P2 | Reviewer edits label to one outside taxonomy | Reject invalid value |
| `REV-006` | P1 | Human edit destroys model output | Prohibit overwrite; create reviewed version |
| `REV-007` | P2 | Reviewer lacks permission | Show read-only state |
| `REV-008` | P2 | Reviewer decision is reversed | Preserve audit history |
| `REV-009` | P2 | Second review is required but missing | Do not mark adjudicated |
| `REV-010` | P2 | Reviewer edits insight but not evidence | Require citation revalidation |
| `REV-011` | P2 | Review target is deleted while open | Prevent submission and show latest state |
| `REV-012` | P2 | Review decision API succeeds but UI times out | Refresh object before retry to avoid duplicate action |
| `REV-013` | P2 | Reviewer accepts low-confidence item | Record human acceptance separately from model confidence |
| `REV-014` | P2 | Reviewer bias creates systematic label drift | Evaluation should compare reviewer agreement |
| `REV-015` | P1 | Human-approved claim later loses evidence | Approval remains historical, but current support warning is required |

---

# Part VIII — Frontend and Interaction

## 32. Application Shell Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `UI-001` | P2 | Sidebar state is unavailable from local storage | Use default safely |
| `UI-002` | P2 | Sidebar is collapsed at narrow width | Switch to mobile navigation pattern |
| `UI-003` | P2 | Active route is not in navigation | Preserve route with clear breadcrumb |
| `UI-004` | P2 | Dataset selector has a deleted active version | Prompt to select available version |
| `UI-005` | P2 | User changes dataset while drawer is open | Close or refresh inspector with explicit context |
| `UI-006` | P2 | Browser back returns to stale filter state | URL state restores filters accurately |
| `UI-007` | P2 | URL contains unsupported filter | Ignore invalid filter and show adjustment |
| `UI-008` | P2 | URL becomes excessively long | Store only stable filter identifiers and compact values |
| `UI-009` | P2 | Command menu shortcut conflicts with browser or assistive tech | Provide visible trigger and configurable fallback |
| `UI-010` | P2 | Dark mode preference is unavailable | Follow system preference |
| `UI-011` | P2 | JavaScript hydration differs from server output | Avoid unstable generated values in initial render |
| `UI-012` | P1 | API schema is newer than frontend | Show incompatible-version error rather than rendering corrupt data |

---

## 33. Loading, Empty, Stale, and Partial States

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `STATE-001` | P1 | Initial overview has no dataset | Show first-ingestion empty state |
| `STATE-002` | P2 | Filters yield no results | Show filtered-empty state and clear action |
| `STATE-003` | P1 | Some analysis stages are complete | Show partial stage and usable completed outputs |
| `STATE-004` | P1 | Theme set is stale after new classifications | Display stale badge and recompute action |
| `STATE-005` | P2 | Cached overview is displayed during refresh | Mark refreshing without removing content |
| `STATE-006` | P2 | API returns empty array and warning | Show warning, not generic empty state |
| `STATE-007` | P2 | Skeleton persists unusually long | Replace with explicit loading or failure message |
| `STATE-008` | P1 | Source unavailable but historical data exists | Keep historical exploration available |
| `STATE-009` | P2 | Low-confidence share is high | Display prominent coverage-quality banner |
| `STATE-010` | P2 | Selected theme is removed during refresh | Return to theme list with notification |
| `STATE-011` | P1 | Partial answer is persisted after failure | Label incomplete and offer retry |
| `STATE-012` | P2 | Run progress total is unknown | Use indeterminate state, not fake percentage |

---

## 34. Responsive and Content Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `RSP-001` | P2 | Evidence excerpt is extremely long | Clamp with accessible expand control |
| `RSP-002` | P2 | Theme title is unusually long | Wrap to bounded lines and preserve full accessible text |
| `RSP-003` | P2 | Source name is very long | Truncate visually with full accessible label |
| `RSP-004` | P2 | Large metric has many digits | Use compact display with exact tooltip or detail |
| `RSP-005` | P2 | Table has more columns than viewport | Column controls or horizontal table scroll with sticky primary column |
| `RSP-006` | P2 | Mobile keyboard covers query composer | Keep composer visible above safe area |
| `RSP-007` | P2 | Screen rotates during active stream | Preserve session and scroll position where practical |
| `RSP-008` | P2 | Browser zoom is 200% | Layout remains usable without clipped controls |
| `RSP-009` | P2 | User uses large text settings | Cards expand vertically |
| `RSP-010` | P3 | Right-to-left language is added later | Layout should avoid assumptions that make RTL impossible |
| `RSP-011` | P2 | Chart labels do not fit | Use wrapping, abbreviations with accessible full labels, or table fallback |
| `RSP-012` | P2 | Mobile evidence table is unusable | Transform rows into cards |
| `RSP-013` | P2 | Inspector is wider than available viewport | Use full-screen sheet |
| `RSP-014` | P2 | Safe-area inset exists on mobile | Apply inset padding |
| `RSP-015` | P2 | Print mode captures interactive chrome | Print stylesheet hides controls and preserves citations |

---

## 35. Accessibility Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `A11Y-001` | P0 | Status is communicated only by color | Add text and icon |
| `A11Y-002` | P1 | Focus is trapped incorrectly in dialog | Restore correct Radix focus behaviour |
| `A11Y-003` | P1 | Closing evidence inspector loses focus | Return focus to originating citation |
| `A11Y-004` | P2 | Stream announces every token | Announce sentence or stage updates politely |
| `A11Y-005` | P1 | Chart has no text alternative | Provide summary and data-table access |
| `A11Y-006` | P1 | Icon button lacks accessible name | Block component QA |
| `A11Y-007` | P2 | Reduced motion is enabled | Remove transforms and loops |
| `A11Y-008` | P2 | Keyboard user cannot reorder report | Provide move up/down controls |
| `A11Y-009` | P2 | Filter result count changes silently | Announce count through live region |
| `A11Y-010` | P1 | Contrast fails in dark mode | Token QA must detect |
| `A11Y-011` | P2 | Tooltip contains essential information | Move essential information into persistent content |
| `A11Y-012` | P2 | Dense table requires horizontal scroll | Ensure keyboard-scroll and visible focus |
| `A11Y-013` | P1 | Command menu cannot be closed with Escape | Fix interaction |
| `A11Y-014` | P2 | Citation chip label “E12” is meaningless to screen reader | Accessible label includes evidence type and preview |
| `A11Y-015` | P2 | Dynamic validation warning appears | Move or announce focus only when necessary |
| `A11Y-016` | P2 | Touch target is visually small | Expand interactive hit area to 44px |
| `A11Y-017` | P2 | Error is identified only after submit | Associate inline error to input |
| `A11Y-018` | P2 | Animated signal field cannot be interpreted | Provide ranked-list alternative |

---

## 36. Visualization Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `VIZ-001` | P1 | Chart dataset is empty | Show clear empty state, not blank axes |
| `VIZ-002` | P2 | Chart has one point | Avoid misleading trend line |
| `VIZ-003` | P1 | Bar chart denominator differs across bars | Explain denominator or use counts |
| `VIZ-004` | P2 | Values are all equal | Avoid implying ranking significance |
| `VIZ-005` | P2 | One value dominates scale | Provide exact labels and optional log scale only when appropriate |
| `VIZ-006` | P2 | Missing periods exist | Show gaps; do not interpolate silently |
| `VIZ-007` | P2 | Negative sentiment score is plotted | Use diverging scale with clear zero |
| `VIZ-008` | P2 | More categories exist than palette supports | Group low-volume categories or use table |
| `VIZ-009` | P1 | Theme comparison uses inconsistent axis scales | Force shared scale |
| `VIZ-010` | P2 | Hover is unavailable on touch | Support tap and table view |
| `VIZ-011` | P2 | Chart animation causes motion discomfort | Disable under reduced-motion setting |
| `VIZ-012` | P1 | Visualization implies exact cluster distance | Add semantic-proximity explanation |
| `VIZ-013` | P2 | Signal field has overlapping nodes | Apply collision layout and list fallback |
| `VIZ-014` | P2 | Data changes while user is inspecting tooltip | Freeze snapshot until interaction ends or update clearly |
| `VIZ-015` | P1 | Chart values disagree with metric cards | Shared deterministic query source required |

---

# Part IX — Reports and Exports

## 37. Report Builder Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `RPT-001` | P1 | Report includes deleted insight | Mark section invalid and require replacement |
| `RPT-002` | P1 | Insight is updated after adding to report | Report uses pinned snapshot and may show newer-version notice |
| `RPT-003` | P2 | Same insight is added twice | Prevent duplicate or request confirmation |
| `RPT-004` | P2 | Report section order collides during concurrent edit | Use optimistic concurrency and stable position strategy |
| `RPT-005` | P1 | Human-edited section is regenerated | Respect locked state |
| `RPT-006` | P2 | Citation is removed from source insight | Mark report section stale |
| `RPT-007` | P2 | Report has no limitations section | Warn before publication or export |
| `RPT-008` | P2 | Product hypothesis lacks validation plan | Warn before export |
| `RPT-009` | P2 | Report mixes analysis versions | Block unless explicit comparison report |
| `RPT-010` | P2 | Drag-and-drop is unavailable | Keyboard actions support ordering |
| `RPT-011` | P1 | Autosave fails | Preserve local draft and display unsaved state |
| `RPT-012` | P2 | User opens same report in two tabs | Detect version conflict |
| `RPT-013` | P2 | Report title is empty | Require title before publication |
| `RPT-014` | P1 | Report references evidence removed for privacy | Suppress excerpt and display affected-evidence warning |
| `RPT-015` | P2 | Report narrative overstates insight type | Preserve knowledge-type labels in export |
| `RPT-016` | P2 | Report contains only one source | Add source-concentration warning |
| `RPT-017` | P2 | Section becomes too long for readable export | Support page breaks and continuation |
| `RPT-018` | P2 | Manual narrative contains unsupported claim | Optional report validation flags missing evidence |

---

## 38. Export Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `EXP-001` | P1 | Markdown export succeeds but PDF fails | Preserve successful artifact and show PDF-specific failure |
| `EXP-002` | P1 | Export storage write fails | Keep report unchanged and retry safely |
| `EXP-003` | P1 | Generated file checksum does not match stored checksum | Quarantine export |
| `EXP-004` | P2 | Unsupported Unicode glyph is missing in PDF font | Use supported fallback font and validate |
| `EXP-005` | P2 | Very long URL breaks layout | Wrap or use citation footnote |
| `EXP-006` | P2 | Chart is cut across page boundary | Apply print layout rules |
| `EXP-007` | P2 | Evidence excerpt overflows page | Split safely and preserve citation |
| `EXP-008` | P1 | Export contains interactive-only labels | Render print-friendly equivalents |
| `EXP-009` | P0 | Export includes unredacted PII | Block export |
| `EXP-010` | P2 | External source is unavailable during export | Use stored evidence snapshot |
| `EXP-011` | P2 | User downloads stale export | Show export creation time and source versions |
| `EXP-012` | P1 | Export job is submitted twice | Idempotency prevents duplicate paid rendering |
| `EXP-013` | P2 | Browser download is blocked | Keep export accessible in report history |
| `EXP-014` | P1 | Export completes after report was deleted | Apply deletion policy and avoid exposing orphan artifact |
| `EXP-015` | P2 | PDF rendering changes metric rounding | Use preformatted deterministic values |
| `EXP-016` | P2 | Dark-mode colors are exported | Use dedicated print theme |
| `EXP-017` | P2 | Page count is unexpectedly large | Warn and allow section selection |
| `EXP-018` | P1 | Export contains broken citation references | Fail validation before final artifact |

---

# Part X — Jobs, Infrastructure, and Recovery

## 39. Job and Queue Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `JOB-001` | P1 | Worker crashes mid-batch | Heartbeat expires; job retries from checkpoint |
| `JOB-002` | P0 | Same job executes twice | Idempotent writes and task lock prevent duplicate effects |
| `JOB-003` | P1 | Redis is unavailable | API rejects new background jobs gracefully; completed data remains readable |
| `JOB-004` | P1 | Redis loses transient progress | Database progress remains authoritative |
| `JOB-005` | P1 | Task remains `running` after worker death | Stale-job reconciler marks retryable |
| `JOB-006` | P2 | Retry limit is reached | Move to dead-lettered or failed state |
| `JOB-007` | P2 | User cancels queued job | Remove or revoke before execution |
| `JOB-008` | P2 | User cancels running job | Set cancellation flag; workers stop at safe checkpoint |
| `JOB-009` | P1 | Parent job fails after child jobs succeed | Parent reflects partial completion |
| `JOB-010` | P1 | Child job is duplicated | Uniqueness on business object and stage prevents duplicate work |
| `JOB-011` | P2 | Queue routing sends AI job to collection worker | Worker capability validation rejects it |
| `JOB-012` | P2 | Job input schema changes after deployment | Version job payload and maintain migration or compatibility |
| `JOB-013` | P1 | Progress current exceeds total | Reject update and log anomaly |
| `JOB-014` | P2 | Total becomes known after indeterminate progress | Transition cleanly to deterministic progress |
| `JOB-015` | P1 | Database commit succeeds but task acknowledgement fails | Redelivery must be idempotent |
| `JOB-016` | P2 | Scheduled job overlaps previous run | Skip, queue, or coalesce based on connector policy |
| `JOB-017` | P2 | Expensive job is initiated without cost estimate | Require estimate or explicit unknown-cost warning |
| `JOB-018` | P1 | Job result references an object deleted during execution | Abort finalization and record conflict |

---

## 40. Database Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `DB-001` | P0 | Database is unavailable during write | Fail request safely; do not report success |
| `DB-002` | P1 | Database is unavailable during read | Show unavailable state; do not replace with empty data |
| `DB-003` | P0 | Foreign-key constraint fails | Roll back full transaction |
| `DB-004` | P0 | Unique constraint catches duplicate source record | Treat as idempotent duplicate when appropriate |
| `DB-005` | P1 | Migration fails halfway | Transactional migration or documented rollback |
| `DB-006` | P0 | Published version is mutated directly | Trigger or service rejects |
| `DB-007` | P1 | Connection pool is exhausted | Apply backpressure and record metric |
| `DB-008` | P2 | Long analytical query times out | Optimize, paginate, or use precomputed aggregate |
| `DB-009` | P1 | Read replica lags behind write | Read authoritative state from primary for job completion |
| `DB-010` | P1 | Database and object storage disagree | Reconciliation job marks integrity warning |
| `DB-011` | P2 | Soft-deleted record appears in default query | Repository filters must exclude it |
| `DB-012` | P1 | Polymorphic object ID points to wrong type | Application validation rejects |
| `DB-013` | P2 | Timestamp precision differs across systems | Use UTC and compare with tolerance |
| `DB-014` | P1 | Transaction deadlock occurs | Retry boundedly for safe transactions |
| `DB-015` | P1 | Backfill is interrupted | Resume by checkpoint without rewriting completed rows |
| `DB-016` | P2 | Enum value is added in one environment only | Migration checks prevent deployment drift |
| `DB-017` | P0 | Hard delete cascades unexpectedly | Avoid unsafe ORM cascade and test deletion graph |
| `DB-018` | P1 | Metric materialization is stale | Display calculated timestamp and refresh path |

---

## 41. Cache Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `CAC-001` | P1 | Cache returns data from another analysis run | Versioned cache key prevents mixing |
| `CAC-002` | P2 | Cache is unavailable | Fall back to database |
| `CAC-003` | P1 | Cached answer contains removed evidence | Invalidate by evidence and version dependency |
| `CAC-004` | P2 | Cache stampede occurs on overview | Use short lock or stale-while-revalidate |
| `CAC-005` | P2 | Filter-facet cache ignores confidence threshold | Include threshold in key |
| `CAC-006` | P2 | User-specific draft is cached globally | Scope draft cache by user or session |
| `CAC-007` | P2 | Run progress cache is ahead of DB | DB is authoritative on reload |
| `CAC-008` | P1 | Cache serialization schema changes | Version payload and reject incompatible value |
| `CAC-009` | P2 | Cache TTL is too long for active run | Use short progress TTL |
| `CAC-010` | P2 | Cache clear removes active session state | Persist important session state in database |

---

## 42. Deployment and Configuration Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `DEP-001` | P0 | Required environment variable is missing | Health check fails before serving affected function |
| `DEP-002` | P0 | Development secrets are committed | CI secret scan fails |
| `DEP-003` | P1 | Frontend and API versions are incompatible | Compatibility check shows clear error |
| `DEP-004` | P1 | pgvector migration is missing in hosted DB | Deployment health check fails |
| `DEP-005` | P2 | Object-storage bucket does not exist | Fail startup or storage health check |
| `DEP-006` | P2 | Timezone differs between containers | Store and operate in UTC |
| `DEP-007` | P2 | System clock drift affects signed provider request | Monitor and correct host clock |
| `DEP-008` | P1 | Build succeeds but runtime font or asset is missing | Asset smoke test catches |
| `DEP-009` | P2 | Browser lacks a non-critical modern API | Provide fallback |
| `DEP-010` | P1 | SSE proxy configuration buffers events | Deployment test validates streaming |
| `DEP-011` | P2 | Worker image and API image use different code versions | Include release version in job payload and worker health |
| `DEP-012` | P1 | Rollback code cannot read newer schema | Use backward-compatible migration sequence |
| `DEP-013` | P2 | Demo mode accidentally calls paid live providers | Explicit demo configuration disables paid calls |
| `DEP-014` | P1 | Seed script is run twice | Deterministic IDs and idempotent upsert |
| `DEP-015` | P0 | Production environment starts with debug mode | Startup validation rejects |
| `DEP-016` | P2 | Hosted filesystem is ephemeral | Use object storage for persistent artifacts |

---

# Part XI — Security and Abuse

## 43. API and Input Security Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `SEC-001` | P0 | SQL injection payload is submitted in filters | Parameterized queries and schema validation |
| `SEC-002` | P0 | XSS payload is present in evidence text | Escape all displayed source text |
| `SEC-003` | P0 | Malicious Markdown is present | Sanitize rendered Markdown and external links |
| `SEC-004` | P0 | Source URL redirects to private network | Validate redirects against SSRF policy |
| `SEC-005` | P0 | Oversized JSON request is submitted | Enforce body-size limit |
| `SEC-006` | P1 | Research-question endpoint is abused for expensive calls | Rate limit and cost controls |
| `SEC-007` | P1 | Run-creation endpoint is replayed | Idempotency and authorization |
| `SEC-008` | P0 | Unauthorized user accesses raw unredacted evidence | Deny and audit |
| `SEC-009` | P0 | User modifies object ID to access another workspace | Enforce authorization by object scope |
| `SEC-010` | P0 | API error exposes stack trace | Return normalized safe error |
| `SEC-011` | P1 | Cross-site request submits a destructive action | CSRF protection when cookie auth exists |
| `SEC-012` | P0 | Export filename includes path characters | Sanitize filename |
| `SEC-013` | P0 | Provider webhook is forged | Verify signature if webhooks are introduced |
| `SEC-014` | P0 | Uploaded future file contains malware | Scan and isolate before processing |
| `SEC-015` | P0 | Secrets appear in model prompt | Prompt builder must exclude configuration secrets |
| `SEC-016` | P1 | Excessive failed authentication attempts | Rate limit and audit |
| `SEC-017` | P2 | User opens a suspicious external source URL | Mark as external and use safe link attributes |
| `SEC-018` | P0 | Model output contains script-like content | Render as escaped text |
| `SEC-019` | P1 | Internal audit endpoint is exposed publicly | Restrict route and data |
| `SEC-020` | P0 | Public source includes copyrighted full article | Store and display only necessary excerpts in accordance with policy |

---

## 44. Authorization Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `AUTH-001` | P1 | Viewer attempts to start paid ingestion | Deny |
| `AUTH-002` | P1 | Researcher attempts to publish taxonomy | Deny unless role permits |
| `AUTH-003` | P1 | Reviewer attempts to change model configuration | Deny |
| `AUTH-004` | P1 | User role changes during session | Refresh authorization before mutation |
| `AUTH-005` | P2 | Anonymous local mode is enabled in hosted deployment | Startup validation should warn or reject |
| `AUTH-006` | P2 | User is removed while a job they started is active | Job continues under system ownership; audit retains actor |
| `AUTH-007` | P1 | Actor ID is missing for protected action | Reject |
| `AUTH-008` | P2 | Report is shared with read-only user | Disable editing controls |
| `AUTH-009` | P1 | Reviewer tries to access unredacted raw artifact | Separate permission required |
| `AUTH-010` | P2 | API token expires during SSE stream | Complete stream or reauthenticate according to chosen auth design |

---

# Part XII — Retention, Removal, and Historical Integrity

## 45. Evidence Removal Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `DEL-001` | P0 | Source record is removed for privacy | Suppress raw and canonical display according to policy |
| `DEL-002` | P1 | Removed record supported an insight | Mark insight support changed and stale |
| `DEL-003` | P1 | Removed record was the only citation for a finding | Mark finding unsupported |
| `DEL-004` | P1 | Removed record appears in published report | Preserve removal notice and redact excerpt |
| `DEL-005` | P2 | Duplicate group canonical record is removed | Promote suitable duplicate or mark group affected |
| `DEL-006` | P1 | Raw artifact expires but derived record remains | Preserve minimal lineage and retention status |
| `DEL-007` | P0 | Hard-delete request would break audit obligations | Apply documented policy and retain minimal lawful metadata |
| `DEL-008` | P1 | Source is deleted but cached preview remains | Invalidate cache |
| `DEL-009` | P2 | Report export file contains removed excerpt | Mark export superseded and create corrected export |
| `DEL-010` | P2 | User deletes a draft report during export | Cancel or remove resulting artifact |
| `DEL-011` | P1 | Analysis run is soft-deleted but research session references it | Session becomes read-only or unavailable with clear explanation |
| `DEL-012` | P2 | Deletion is requested while a model call contains the evidence | Prevent new publication and sanitize retained audit payload |

---

## 46. Versioning and Historical Comparison Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `VER-001` | P1 | Two theme sets have same version number in one run | Prevent through uniqueness |
| `VER-002` | P1 | Prompt version is deprecated during active run | Run continues with snapshot |
| `VER-003` | P2 | Historical answer is opened under new dataset selector | Show pinned historical context |
| `VER-004` | P2 | User compares metrics across incompatible taxonomies | Require mapping or explain incompatibility |
| `VER-005` | P1 | Report silently updates to latest insight version | Prohibit; use pinned snapshot |
| `VER-006` | P2 | Embedding model changes and themes are not rebuilt | Mark theme set tied to old embeddings |
| `VER-007` | P2 | New normalization changes record checksum | Create new derived version |
| `VER-008` | P1 | Model configuration name is reused for different settings | Configuration identity must be immutable or versioned |
| `VER-009` | P2 | Historical cost is recalculated using current prices | Preserve pricing snapshot |
| `VER-010` | P2 | Evaluation metric is compared across different gold datasets | Display dataset version prominently |

---

# Part XIII — Observability and Cost

## 47. Logging and Metrics Edge Cases

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `OBS-001` | P0 | Log contains API key | Redaction test and log filter |
| `OBS-002` | P0 | Log contains unredacted evidence | Sanitize or omit payload |
| `OBS-003` | P1 | Request ID is missing across worker handoff | Propagate correlation IDs |
| `OBS-004` | P2 | Metrics label includes record ID and creates high cardinality | Use bounded dimensions |
| `OBS-005` | P2 | Provider latency metric is missing on failure | Record elapsed time where possible |
| `OBS-006` | P1 | Cost ledger entry is duplicated | Enforce provider-request uniqueness where possible |
| `OBS-007` | P2 | Estimated and actual cost differ | Preserve both and show variance |
| `OBS-008` | P1 | Cost cap calculation excludes pending calls | Include committed or reserved cost |
| `OBS-009` | P2 | Alerts fire during intentional demo shutdown | Environment-aware alert configuration |
| `OBS-010` | P1 | Run appears complete but child job still running | Parent completion checks child states |
| `OBS-011` | P2 | Success metric ignores partial failures | Report success and failure counts separately |
| `OBS-012` | P1 | Audit event write fails during sensitive action | Fail or queue according to action criticality |
| `OBS-013` | P2 | Clock skew produces negative duration | Normalize timestamps and flag anomaly |
| `OBS-014` | P2 | Metrics pipeline is unavailable | Core product remains operational |
| `OBS-015` | P1 | Model usage is unknown | Mark cost estimate as incomplete rather than zero |

---

# Part XIV — Cross-Feature Edge Cases

## 48. Cross-Version and Cross-Surface Consistency

| ID | Priority | Scenario | Expected behaviour |
|---|---|---|---|
| `XFN-001` | P1 | Theme count differs between Overview and Theme Explorer | Shared query or metric source required |
| `XFN-002` | P1 | Insight confidence differs between card and report | Use one pinned value |
| `XFN-003` | P1 | Evidence review state updates but open inspector is stale | Update or display refresh notice |
| `XFN-004` | P2 | Active filters differ between page header and URL | URL is authoritative |
| `XFN-005` | P1 | Dataset selector changes while answer is generating | Keep active question pinned and warn before context switch |
| `XFN-006` | P2 | Theme added to report then merged | Report uses original snapshot and shows superseded notice |
| `XFN-007` | P1 | Validation rejects an answer finding already in report | Report section becomes stale |
| `XFN-008` | P2 | Run finishes while user is on partial theme page | Offer refresh without losing reading position |
| `XFN-009` | P1 | Source removal occurs while evidence is open | Replace content with removed-evidence state |
| `XFN-010` | P2 | Dark-mode token differs between app and exported chart | Export uses print token set |
| `XFN-011` | P1 | Review correction changes aggregate metrics | Trigger or queue metric recalculation |
| `XFN-012` | P2 | User opens shared historical URL after version archived | Show read-only historical state |
| `XFN-013` | P1 | Cached answer uses different filters than shown | Effective filters are persisted and rendered from answer record |
| `XFN-014` | P2 | Multiple tabs edit filters independently | URL state remains tab-local |
| `XFN-015` | P1 | A run is retried but UI displays old failure | New attempt is linked and clearly differentiated |

---

# Part XV — Edge-Case UX Copy Patterns

## 49. Copy Rules

Error and warning messages should:

- name the affected object;
- describe what is still available;
- state whether data is preserved;
- explain retry safety;
- avoid technical jargon when not needed;
- avoid blaming the user;
- never imply success when output is partial.

### Source partial completion

```text
Reddit collection stopped early

684 records were saved before the source rate limit was reached.
You can analyze the available records now or retry from the saved checkpoint.
```

### Insufficient evidence

```text
The current dataset cannot support a reliable answer

Only two relevant records were found, both from the same source.
Review the available evidence or broaden the source and date filters.
```

### Citation validation warning

```text
One finding could not be fully verified

The answer remains available, but the affected finding is marked as partially supported.
```

### Stale analysis

```text
This theme was created before the latest evidence update

Its metrics and supporting examples may have changed.
Rebuild the theme set to use the current dataset.
```

### Removed evidence

```text
This evidence is no longer available

The source record was removed or expired. Dependent findings are being re-evaluated.
```

### Paid retry

```text
Retrying may create additional provider charges

The completed records are already saved. Only failed items will be retried.
```

---

# Part XVI — Required Automated Test Matrix

## 50. P0 Test Suite

The P0 suite must include:

- raw artifact checksum mismatch;
- object storage and database partial commit;
- duplicate paid-job submission;
- SSRF through direct URL and redirect;
- XSS in evidence and model output;
- prompt injection in source content;
- missing or mismatched citation;
- unsupported model count;
- unredacted PII in UI and export;
- unauthorized raw evidence access;
- taxonomy version mismatch;
- embedding dimension mismatch;
- destructive cascade prevention;
- source-removal propagation;
- published-version immutability;
- cross-workspace object access;
- secret leakage in logs;
- model inference of unsupported demographics.

A P0 failure blocks demonstration.

---

## 51. P1 Integration Suite

The P1 suite must include:

1. collection rate limit after partial success;
2. checkpoint resume without duplicates;
3. connector parser returns zero due schema change;
4. partial classification batch;
5. model invalid structured output and repair;
6. AI cost cap reached mid-run;
7. stale embedding detection;
8. no-cluster and all-outlier theme runs;
9. theme metric mismatch;
10. insight without sufficient support;
11. ambiguous question;
12. question with no supporting evidence;
13. SSE disconnect and reload recovery;
14. stale or deleted citation;
15. human-review concurrency conflict;
16. report with stale insight;
17. PDF export failure after Markdown success;
18. worker crash and retry;
19. Redis loss with database progress intact;
20. database read failure shown as unavailable, not empty;
21. cache version mismatch;
22. frontend/API schema mismatch;
23. source removal during active session;
24. metric consistency across Overview and Themes.

---

## 52. P2 Component and Accessibility Suite

The P2 suite should include:

- long titles and evidence excerpts;
- all empty states;
- partial and stale states;
- dark-mode contrast;
- 200% zoom;
- reduced motion;
- keyboard-only evidence inspection;
- focus restoration;
- chart text alternatives;
- mobile table conversion;
- mobile keyboard and safe-area handling;
- touch targets;
- filtered-empty state;
- command-menu keyboard behaviour;
- unknown progress total;
- source-concentration warning;
- unsupported-language record;
- duplicate generic short reviews;
- contradictory answer;
- report reorder without drag;
- unavailable external source URL.

---

# Part XVII — Demo Scenarios

## 53. Required Demonstration Fixtures

The demo seed should intentionally include:

1. a valid Google Play record;
2. a Reddit-style post and comments;
3. an industry article passage;
4. an exact duplicate;
5. a near duplicate;
6. an edited source record;
7. an undated record;
8. a low-information record;
9. a code-mixed English-Hindi record;
10. an unsupported-language record;
11. a record containing redacted PII;
12. a record with malicious prompt-injection wording;
13. contradictory evidence;
14. a low-confidence classification;
15. a human-corrected classification;
16. a theme with broad source coverage;
17. a source-concentrated theme;
18. a product hypothesis requiring internal validation;
19. an answer with a grounding warning;
20. a partially completed run;
21. a failed export;
22. a removed evidence record;
23. a stale report section;
24. a small evaluation dataset warning.

These cases allow the product to demonstrate resilience rather than showing only an ideal happy path.

---

# Part XVIII — Implementation Priorities

## 54. MVP P0 Requirements

Claude Code must implement before the first external demonstration:

- idempotent run creation and worker execution;
- raw checksum and storage consistency;
- source text sanitization;
- PII redaction in frontend and export;
- source-content prompt-injection protection;
- structured-output validation;
- taxonomy-version integrity;
- deterministic counts;
- citation existence and claim-support validation;
- evidence lineage;
- source-removal propagation;
- protected secrets and logs;
- role checks if authentication is enabled;
- safe SSRF policy;
- published-version immutability.

---

## 55. MVP P1 Requirements

Claude Code must implement:

- partial-run handling;
- checkpoint resume;
- bounded retry;
- explicit unavailable-source state;
- partial classification and embedding recovery;
- low-confidence display;
- stale analysis warnings;
- theme quality checks;
- insight evidence minimums;
- insufficient-evidence answers;
- contradiction retrieval;
- SSE recovery;
- human-review conflict handling;
- stale report warnings;
- export validation;
- database-authoritative progress;
- cache versioning;
- frontend loading, empty, partial, stale, and error states.

---

## 56. Deferrable P3 Cases

The following may be deferred if explicitly documented:

- real-time multi-user report collaboration;
- high-contrast theme beyond WCAG AA light and dark modes;
- full RTL interface;
- automated taxonomy migration across versions;
- sophisticated source-version history browsing;
- cluster visual physics beyond stable semantic layout;
- multi-region deployment failure handling;
- petabyte-scale partitioning;
- automatic cross-language translation;
- advanced reconciliation across multiple scraping vendors.

Deferral must not weaken evidence integrity.

---

# Part XIX — Guidance for Claude Code

## 57. Implementation Instructions

Claude Code should:

- use the stable edge-case IDs in tests, error codes, and implementation notes;
- create typed failure enums rather than free-text-only errors;
- preserve partial success and checkpoints;
- record retryability explicitly;
- keep PostgreSQL authoritative for durable state;
- treat Redis and SSE as transient delivery mechanisms;
- validate source-native identity before canonical insertion;
- retain original, normalized, and redacted text separately;
- block unsafe external URLs and redirects;
- sanitize all source and model content before rendering;
- use structured Pydantic output for every non-chat model task;
- delimit evidence and forbid instruction following from source content;
- reject unresolved labels, citations, object IDs, and vector dimensions;
- never use LLM output as the source of counts;
- calculate stale status from version and dependency changes;
- implement dedicated contradiction retrieval;
- preserve model output when humans edit it;
- enforce optimistic concurrency for reviews and reports;
- invalidate caches by analysis, theme, insight, evidence, and filter version;
- use database transactions for lineage-critical writes;
- add reconciliation jobs for storage, jobs, and dependent evidence;
- surface recovery actions that match actual retry safety;
- implement reduced-motion, keyboard, focus, and responsive edge cases;
- include P0 and P1 edge-case tests in CI;
- update `edgecases.md` when new failure modes or recovery rules are introduced.

---

## 58. Edge-Case Definition of Done

The edge-case specification is implemented adequately when:

1. every pipeline stage has explicit failure and partial-success states;
2. external-source failures preserve completed evidence and checkpoints;
3. malformed records cannot corrupt canonical data;
4. PII cannot appear in ordinary UI, logs, prompts, or exports;
5. source content cannot override system or model instructions;
6. duplicate jobs cannot duplicate paid work or derived artifacts;
7. model failures and invalid outputs are bounded and auditable;
8. taxonomy, prompt, model, embedding, theme, and insight versions cannot mix silently;
9. no theme, insight, answer, or report claim can exist without resolvable evidence lineage;
10. no exact count depends on an LLM;
11. contradictions and insufficient evidence are represented honestly;
12. stale and removed evidence propagate to dependent artifacts;
13. the UI distinguishes empty, partial, stale, unavailable, low-confidence, and failed states;
14. SSE disconnection does not lose the final answer or job state;
15. human edits preserve original model output and handle conflicts;
16. reports cannot export unredacted or broken citations;
17. infrastructure retries are idempotent;
18. P0 tests block release;
19. P1 workflow tests run in CI;
20. demo data contains intentional edge cases, not only happy-path records.
