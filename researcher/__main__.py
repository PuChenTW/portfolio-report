import asyncio
import logging
import signal
from datetime import datetime

from portfolio.portfolio import TZ_TAIPEI
from portfolio.telegram import send_telegram_messages

from researcher.scheduler import create_scheduler
from researcher.bot import create_application
from researcher.bot import COMMANDS


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    print(f"[{datetime.now(TZ_TAIPEI).isoformat()}] Researcher agent starting...")

    scheduler = create_scheduler()
    app = create_application()

    scheduler.start()

    try:
        send_telegram_messages(["✅ Researcher agent online\\."])
    except Exception as e:
        print(f"[warn] startup notification failed: {e}")

    async with app:
        await app.initialize()

        await app.bot.set_my_commands(COMMANDS)
        await app.start()
        await app.updater.start_polling()  # type: ignore
        print("Bot polling started. Press Ctrl+C to stop.")
        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)
        try:
            await stop_event.wait()
        finally:
            await app.updater.stop()  # type: ignore
            await app.stop()
            scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
