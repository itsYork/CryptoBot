#!/usr/bin/env python3
import anyio
from src.core.scheduler import start_scheduler
from src.core.health import serve_health
from src.core.config import settings

async def _main():
    async with anyio.create_task_group() as tg:
        tg.start_soon(start_scheduler, settings)
        tg.start_soon(serve_health, 8000)

def main():
    anyio.run(_main)

if __name__ == "__main__":
    main()
