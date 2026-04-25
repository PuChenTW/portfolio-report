import asyncio
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from portfolio.telegram import send_telegram_messages

import researcher.workflows.premarket as premarket
import researcher.workflows.midday as midday
import researcher.workflows.daily_summary as daily_summary
import researcher.workflows.weekly_review as weekly_review

_TZ = "Asia/Taipei"


def _wrap(fn, *args):
    """Wrap a sync workflow function for async scheduler execution."""
    async def job():
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, fn, *args)
        except Exception as e:
            msg = f"❌ Workflow {fn.__name__}({', '.join(str(a) for a in args)}) failed: {e}"
            print(msg)
            try:
                send_telegram_messages([msg])
            except Exception:
                pass
    return job


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=_TZ)

    # TW market (weekdays)
    scheduler.add_job(_wrap(premarket.run, "TW"), CronTrigger(day_of_week="mon-fri", hour=8, minute=30, timezone=_TZ))
    scheduler.add_job(_wrap(daily_summary.run, "TW"), CronTrigger(day_of_week="mon-fri", hour=13, minute=35, timezone=_TZ))

    # US market (weekdays, times in Taipei = ET+13)
    scheduler.add_job(_wrap(premarket.run, "US"), CronTrigger(day_of_week="mon-fri", hour=21, minute=30, timezone=_TZ))
    scheduler.add_job(_wrap(midday.run), CronTrigger(day_of_week="tue-sat", hour=2, minute=0, timezone=_TZ))
    scheduler.add_job(_wrap(daily_summary.run, "US"), CronTrigger(day_of_week="tue-sat", hour=5, minute=0, timezone=_TZ))

    # Weekly review (Saturday)
    scheduler.add_job(_wrap(weekly_review.run), CronTrigger(day_of_week="sat", hour=10, minute=0, timezone=_TZ))

    return scheduler
