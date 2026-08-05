from __future__ import annotations


async def publish_knowledge(
    payload: dict,
) -> dict:
    """
    Mock knowledge publishing handler.

    Real MediaWiki integration will be added later.
    """

    return {
        "executed": True,
        "action": "publish_knowledge",
        "document": payload.get(
            "document"
        ),
    }
