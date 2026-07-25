"""Automatically maintain PostgreSQL full-text search vectors.

Revision ID: 20260724_0002
Revises: 20260723_0001
Create Date: 2026-07-24
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260724_0002"
down_revision: str | Sequence[str] | None = "20260723_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_knowledge_content_search_vector()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            NEW.search_vector :=
                setweight(
                    to_tsvector(
                        'simple',
                        coalesce(NEW.lead_summary, '')
                    ),
                    'A'
                )
                ||
                setweight(
                    to_tsvector(
                        'simple',
                        coalesce(NEW.plain_text, '')
                    ),
                    'B'
                );

            RETURN NEW;
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_knowledge_chunk_search_vector()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            NEW.search_vector :=
                setweight(
                    to_tsvector(
                        'simple',
                        coalesce(
                            array_to_string(NEW.heading_path, ' '),
                            ''
                        )
                    ),
                    'A'
                )
                ||
                setweight(
                    to_tsvector(
                        'simple',
                        coalesce(NEW.content, '')
                    ),
                    'B'
                );

            RETURN NEW;
        END;
        $$;
        """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS
            trg_knowledge_content_search_vector
        ON knowledge_content;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_knowledge_content_search_vector
        BEFORE INSERT OR UPDATE OF lead_summary, plain_text
        ON knowledge_content
        FOR EACH ROW
        EXECUTE FUNCTION update_knowledge_content_search_vector();
        """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS
            trg_knowledge_chunk_search_vector
        ON knowledge_chunks;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_knowledge_chunk_search_vector
        BEFORE INSERT OR UPDATE OF heading_path, content
        ON knowledge_chunks
        FOR EACH ROW
        EXECUTE FUNCTION update_knowledge_chunk_search_vector();
        """
    )

    op.execute(
        """
        UPDATE knowledge_content
        SET search_vector =
            setweight(
                to_tsvector(
                    'simple',
                    coalesce(lead_summary, '')
                ),
                'A'
            )
            ||
            setweight(
                to_tsvector(
                    'simple',
                    coalesce(plain_text, '')
                ),
                'B'
            );
        """
    )

    op.execute(
        """
        UPDATE knowledge_chunks
        SET search_vector =
            setweight(
                to_tsvector(
                    'simple',
                    coalesce(
                        array_to_string(heading_path, ' '),
                        ''
                    )
                ),
                'A'
            )
            ||
            setweight(
                to_tsvector(
                    'simple',
                    coalesce(content, '')
                ),
                'B'
            );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS
            trg_knowledge_chunk_search_vector
        ON knowledge_chunks;
        """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS
            trg_knowledge_content_search_vector
        ON knowledge_content;
        """
    )

    op.execute(
        """
        DROP FUNCTION IF EXISTS
            update_knowledge_chunk_search_vector();
        """
    )

    op.execute(
        """
        DROP FUNCTION IF EXISTS
            update_knowledge_content_search_vector();
        """
    )


