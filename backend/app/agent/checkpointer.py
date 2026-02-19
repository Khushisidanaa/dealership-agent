from __future__ import annotations

"""Checkpointer for LangGraph state persistence.

Uses MemorySaver for hackathon/development.  Swap to AsyncMongoDBSaver
for production once the motor + pymongo version matrix is pinned.
"""

from langgraph.checkpoint.memory import MemorySaver

_checkpointer: MemorySaver | None = None


async def get_checkpointer() -> MemorySaver:
    """Return a singleton MemorySaver (state lives in process memory)."""
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    _checkpointer = MemorySaver()
    return _checkpointer


async def close_checkpointer() -> None:
    """Reset the checkpointer."""
    global _checkpointer
    _checkpointer = None
