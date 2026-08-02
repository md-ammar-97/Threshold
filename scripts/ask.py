#!/usr/bin/env python
"""CLI entry point for Phase 5 research — asks one question against an
existing research_session and prints the persisted, grounded answer.
"Pipeline mode" per architecture.md §6.1.

Usage:
    python scripts/ask.py --session-id <uuid> --question "Why do users hesitate to explore?"
    python scripts/ask.py --theme-set-id <uuid> --question "..."   # creates a session first
"""

import argparse
import asyncio
import sys
from pathlib import Path
from uuid import UUID

BACKEND_SRC = Path(__file__).resolve().parents[1] / "backend" / "src"
sys.path.insert(0, str(BACKEND_SRC))

from instamart_engine.ai.exceptions import AIGatewayError  # noqa: E402
from instamart_engine.core.database import get_session_factory  # noqa: E402
from instamart_engine.research import repository as research_repo  # noqa: E402
from instamart_engine.research.service import ask_question  # noqa: E402
from instamart_engine.themes.models import ThemeSet  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ask a research question.")
    parser.add_argument("--question", required=True)
    parser.add_argument("--session-id", default=None, help="Existing research_session UUID")
    parser.add_argument(
        "--theme-set-id",
        default=None,
        help="Create a new research_session from this theme_set UUID (if --session-id omitted)",
    )
    parser.add_argument("--insight-set-id", default=None)
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    session_factory = get_session_factory()

    async with session_factory() as session:
        if args.session_id:
            research_session_id = UUID(args.session_id)
        elif args.theme_set_id:
            theme_set = await session.get(ThemeSet, UUID(args.theme_set_id))
            if theme_set is None:
                print(f"No theme_set found with id={args.theme_set_id!r}")
                return
            research_session = await research_repo.create_research_session(
                session,
                title=f"CLI session for theme_set {theme_set.id}",
                analysis_run_id=theme_set.analysis_run_id,
                theme_set_id=theme_set.id,
                insight_set_id=UUID(args.insight_set_id) if args.insight_set_id else None,
            )
            await session.commit()
            research_session_id = research_session.id
            print(f"[SESSION CREATED] id={research_session_id}")
        else:
            print("Must pass either --session-id or --theme-set-id")
            return

        try:
            result = await ask_question(
                session, research_session_id=research_session_id, question_text=args.question
            )
        except AIGatewayError as exc:
            print(f"[ASK FAILED] {type(exc).__name__}: {exc}")
            return
        except ValueError as exc:
            print(f"[ASK FAILED] {exc}")
            return

        question = result.question
        answer = result.answer_result.generated_answer
        print(f"[QUESTION] id={question.id} status={question.status.value}")
        print(f"[GROUNDING] status={answer.grounding_status.value} "
              f"citations={answer.citation_count} warnings={answer.warning_count}")
        print(f"[ANSWER]\n{answer.answer_text}")


if __name__ == "__main__":
    asyncio.run(main())
