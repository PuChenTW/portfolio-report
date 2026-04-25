import asyncio
from datetime import datetime

from portfolio.portfolio import TZ_TAIPEI
from portfolio.telegram import send_telegram_messages

from researcher.scheduler import create_scheduler
from researcher.bot import create_application


async def main() -> None:
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
        await app.start()
        await app.updater.start_polling()
        print("Bot polling started. Press Ctrl+C to stop.")
        stop_event = asyncio.Event()
        try:
            await stop_event.wait()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            await app.updater.stop()
            await app.stop()
            scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
