"""feedback record media columns

Adds media_url/media_type/extracted_media_text to feedback_record for the
Phase 1 media pipeline (OCR on images, speech-to-text on video/audio) — all
nullable, additive, backward-compatible.

Revision ID: d4a1e6f293b7
Revises: f918156187f0
Create Date: 2026-07-29 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4a1e6f293b7"
down_revision: Union[str, Sequence[str], None] = "f918156187f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    media_type = postgresql.ENUM("image", "video", name="media_type", create_type=False)
    media_type.create(op.get_bind(), checkfirst=True)

    op.add_column("feedback_record", sa.Column("media_url", sa.Text(), nullable=True))
    op.add_column("feedback_record", sa.Column("media_type", media_type, nullable=True))
    op.add_column(
        "feedback_record", sa.Column("extracted_media_text", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("feedback_record", "extracted_media_text")
    op.drop_column("feedback_record", "media_type")
    op.drop_column("feedback_record", "media_url")

    postgresql.ENUM("image", "video", name="media_type").drop(op.get_bind(), checkfirst=True)
