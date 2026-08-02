#!/usr/bin/env bash
# Daily data-extraction pipeline — meant to run on a schedule (Render Cron
# Job, render.yaml: "30 0 * * *" = 00:30 UTC = 6:00 AM IST).
#
# Runs each source connector's collection (with --process, so newly
# ingested raw items are normalized into feedback_record immediately), then
# the media pipeline, then the unified classify->embed->cluster->
# synthesize->insights run under one shared AnalysisRun (scripts/pipeline.py
# — see its own docstring for why classify.py+analyze.py run separately
# would be wrong here).
#
# `public_web` is deliberately NOT included: unlike every other connector,
# it has no sensible "keep re-fetching automatically" target — it exists
# for ad-hoc, user-specified article URLs (docs/architecture.md §10.2),
# not an evergreen source. Run it manually with an explicit --urls list
# when needed.
#
# reddit/twitter/instagram/forum/mouthshut/quickcommerce all fall back to
# real, working default search terms / hashtags / seed URLs / feed URLs
# when --search-terms/--hashtags/--urls are omitted (see scripts/ingest.py
# and each connector's own module docstring) — no need to duplicate those
# lists here.
#
# One bad source (an expired Apify actor, a dead RSS feed, a rate limit)
# must not block every other source or the classify/synthesize pass, so
# each `ingest.py` call is allowed to fail without stopping the script —
# failures are logged and counted, and the script's own exit code reflects
# only whether the final scripts/pipeline.py run (the step that actually
# determines same-day data freshness) succeeded.

set -uo pipefail

cd "$(dirname "$0")/.."

FAILED_SOURCES=()

run_ingest() {
    local source="$1"
    shift
    echo "=== ingest: ${source} ==="
    if ! python scripts/ingest.py "${source}" "$@" --process; then
        echo "!!! ingest failed: ${source}"
        FAILED_SOURCES+=("${source}")
    fi
}

# --- Phase 1: collection ---
# google_play/apple_app_store take a real target identifier; every other
# source takes "" and relies on its built-in defaults (see header comment).
run_ingest google_play "in.swiggy.android" --limit 200
run_ingest apple_app_store "1352526847" --limit 50   # expect discovered=0 most days — Apple's review RSS only exposes a bounded recent window
run_ingest reddit "" --limit 100
run_ingest twitter "" --limit 50
run_ingest instagram "" --limit 50
run_ingest forum "" --limit 30
run_ingest mouthshut "" --limit 30
run_ingest quickcommerce "" --limit 50

# --- Phase 2: media (OCR / speech-to-text) for anything collected above ---
echo "=== extract_media ==="
if ! python scripts/extract_media.py --limit 200; then
    echo "!!! extract_media failed (continuing — classification degrades gracefully to text-only)"
fi

# --- Phase 3: the unified pipeline — this is the step that matters ---
echo "=== pipeline (classify -> embed -> cluster -> synthesize -> insights) ==="
if python scripts/pipeline.py --synthesize --generate-insights; then
    PIPELINE_OK=1
else
    PIPELINE_OK=0
fi

echo "=== daily_extraction summary ==="
if [ "${#FAILED_SOURCES[@]}" -gt 0 ]; then
    echo "sources with collection failures: ${FAILED_SOURCES[*]}"
else
    echo "all sources collected without error"
fi

if [ "${PIPELINE_OK}" -eq 1 ]; then
    echo "pipeline: OK"
    exit 0
else
    echo "pipeline: FAILED — today's data was not classified/clustered/synthesized"
    exit 1
fi
