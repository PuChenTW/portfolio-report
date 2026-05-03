import asyncio
import re
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from portfolio.telegram import send_telegram_messages
import researcher.workflows.premarket as premarket
import researcher.workflows.midday as midday
import researcher.workflows.daily_summary as daily_summary
import researcher.workflows.weekly_review as weekly_review
from researcher.services.workflow_deps import make_deps

_TZ_TW = "Asia/Taipei"
_TZ_US = "America/New_York"


def _esc(text: str) -> str:
    return re.sub(r"([_*\[\]()~`>#+=|{}.!\-])", r"\\\1", text)


def _wrap(fn, *args):
    """Wrap a sync workflow function for async scheduler execution."""

    async def job():
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, fn, *args)
        except Exception as e:
            plain = f"Workflow {fn.__name__}({', '.join(str(a) for a in args)}) failed: {e}"
            print(f"❌ {plain}")
            try:
                send_telegram_messages([f"❌ {_esc(plain)}"])
            except Exception:
                pass

    return job


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=_TZ_TW)
    deps = make_deps()

    # TW market (weekdays, Taipei time)
    scheduler.add_job(
        _wrap(premarket.run, "TW", deps),
        CronTrigger(day_of_week="mon-fri", hour=8, minute=30, timezone=_TZ_TW),
        misfire_grace_time=60,
    )
    scheduler.add_job(
        _wrap(midday.run, "TW", deps),
        CronTrigger(day_of_week="mon-fri", hour=11, minute=30, timezone=_TZ_TW),
        misfire_grace_time=60,
    )
    scheduler.add_job(
        _wrap(daily_summary.run, "TW", deps),
        CronTrigger(day_of_week="mon-fri", hour=13, minute=35, timezone=_TZ_TW),
        misfire_grace_time=60,
    )

    # US market (weekdays, Eastern time)
    scheduler.add_job(
        _wrap(premarket.run, "US", deps),
        CronTrigger(day_of_week="mon-fri", hour=8, minute=30, timezone=_TZ_US),
        misfire_grace_time=60,
    )
    scheduler.add_job(
        _wrap(midday.run, "US", deps),
        CronTrigger(day_of_week="mon-fri", hour=13, minute=0, timezone=_TZ_US),
        misfire_grace_time=60,
    )
    scheduler.add_job(
        _wrap(daily_summary.run, "US", deps),
        CronTrigger(day_of_week="mon-fri", hour=16, minute=0, timezone=_TZ_US),
        misfire_grace_time=60,
    )

    # Weekly review (Saturday, Taipei time)
    scheduler.add_job(
        _wrap(weekly_review.run, deps),
        CronTrigger(day_of_week="sat", hour=10, minute=0, timezone=_TZ_TW),
        misfire_grace_time=60,
    )

    return scheduler
