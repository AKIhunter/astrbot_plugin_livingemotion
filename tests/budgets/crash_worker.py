"""Exit only after a real worker has durably reserved and dispatched its stub."""

import asyncio
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from budget_support import Rig


def offline(event, args):
    if event in {"socket.connect", "socket.bind", "socket.sendto", "socket.getaddrinfo"}:
        raise RuntimeError("offline_only")


async def main():
    rig = Rig(Path(sys.argv[1]), model_daily_limit=1)
    await rig.open()

    async def crash_after_dispatch():
        os._exit(0)

    await rig.model("synthetic-crash-inflight", crash_after_dispatch)


if __name__ == "__main__":
    sys.addaudithook(offline)
    asyncio.run(main())
