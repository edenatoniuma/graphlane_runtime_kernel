from __future__ import annotations

import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from graphlane import AppSpec, ModelSpec, TurnRequest
from graphlane.api import KernelBuilder


async def main() -> None:
    kernel = KernelBuilder().build()

    await kernel.publish_revision(
        AppSpec(
            app_id="demo",
            name="demo",
            revision=1,
            app_type="REACT",
            enabled_patterns=["REACT"],
            prompt="echo",
            model=ModelSpec(provider="mock", model="demo-model"),
        )
    )

    sync_result = await kernel.invoke(
        TurnRequest(
            app_id="demo",
            session_id="sync-session",
            query="hello-sync",
        )
    )
    print("sync_result:", sync_result.assistant_content)

    turn_id = await kernel.submit_async(
        TurnRequest(
            app_id="demo",
            session_id="async-session",
            query="hello-async",
        )
    )
    print("async_turn_id:", turn_id)

    async for event in kernel.subscribe_async(turn_id):
        print("async_event:", event.type, event.payload)


if __name__ == "__main__":
    asyncio.run(main())

