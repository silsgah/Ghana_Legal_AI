"""Delete the requesting user's LangGraph PostgresSaver thread(s).

The previous implementation tried to drop MongoDB collections, which is dead
code — production runs the PostgresSaver checkpointer (see generate_response.py).
Clicking "New Consultation" / "Clear History" appeared to do nothing because
the PG thread was untouched and the next message reused the same thread_id.
"""

from typing import Optional

from loguru import logger

from ghana_legal.config import settings


# LangGraph's AsyncPostgresSaver writes to these three tables, all keyed by
# thread_id. Deleting the rows for a thread is enough to "start over" — the
# next graph run on that thread_id begins from a fresh empty state.
_CHECKPOINT_TABLES = ("checkpoints", "checkpoint_writes", "checkpoint_blobs")


async def reset_conversation_state(clerk_id: str, expert_id: Optional[str] = None) -> dict:
    """Delete LangGraph checkpoint rows for the user (and optionally one expert).

    thread_id format used by generate_response.py is f"{clerk_id}_{expert_id}".
    When expert_id is provided we delete just that thread; otherwise we delete
    every thread belonging to the user (all experts).
    """
    if expert_id:
        thread_pattern = f"{clerk_id}_{expert_id}%"  # match base + any -uuid suffix
    else:
        thread_pattern = f"{clerk_id}_%"

    deleted_counts: dict[str, int] = {}

    from ghana_legal.infrastructure.database import get_checkpointer_pool
    pool = await get_checkpointer_pool()

    async with pool.connection() as conn:
        for table in _CHECKPOINT_TABLES:
            try:
                async with conn.cursor() as cur:
                    await cur.execute(
                        f"DELETE FROM {table} WHERE thread_id LIKE %s",
                        (thread_pattern,),
                    )
                    deleted_counts[table] = cur.rowcount
            except Exception as e:
                # Table might not exist yet (first deploy); log and continue.
                logger.warning(f"DELETE on {table} failed (treating as 0 rows): {e}")
                deleted_counts[table] = 0
        await conn.commit()

    total = sum(deleted_counts.values())
    logger.info(
        f"Reset thread_pattern={thread_pattern!r} — deleted "
        f"{deleted_counts} (total {total} rows)"
    )

    return {
        "status": "success",
        "thread_pattern": thread_pattern,
        "deleted": deleted_counts,
        "total": total,
    }
