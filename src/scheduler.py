"""
Scheduler for automated RFP discovery and notifications.
Runs discovery at configured intervals and sends email alerts.
"""

import os
import sys
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional, Callable

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import database as db
from src.rfp_discovery import RFPDiscoveryEngine
from src.notifications import NotificationService, send_daily_digest, send_deadline_alerts

logger = logging.getLogger(__name__)

# Scheduler configuration
SCHEDULE_CONFIG = {
    'discovery_interval_hours': 6,  # Run discovery every 6 hours
    'deadline_check_hours': 24,     # Check deadlines daily
    'daily_digest_time': '08:00',   # Send daily digest at 8 AM
    'deadline_reminder_days': 3,    # Remind about RFPs due in 3 days
}


class SchedulerService:
    """Background scheduler for automated tasks."""

    def __init__(self):
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.last_discovery: Optional[datetime] = None
        self.last_deadline_check: Optional[datetime] = None
        self.last_daily_digest: Optional[datetime] = None
        self.notification_service = NotificationService()

    def start(self):
        """Start the scheduler in a background thread."""
        if self.running:
            logger.warning("Scheduler is already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info("Scheduler started")

    def stop(self):
        """Stop the scheduler."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Scheduler stopped")

    def _run_loop(self):
        """Main scheduler loop."""
        while self.running:
            try:
                now = datetime.now()

                # Check if discovery is due
                if self._should_run_discovery(now):
                    self._run_discovery()

                # Check if deadline reminder is due
                if self._should_check_deadlines(now):
                    self._check_deadlines()

                # Check if daily digest is due
                if self._should_send_digest(now):
                    self._send_daily_digest()

                # Sleep for 1 minute before next check
                time.sleep(60)

            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(60)

    def _should_run_discovery(self, now: datetime) -> bool:
        """Check if discovery should run."""
        if self.last_discovery is None:
            return True

        interval = timedelta(hours=SCHEDULE_CONFIG['discovery_interval_hours'])
        return now - self.last_discovery >= interval

    def _should_check_deadlines(self, now: datetime) -> bool:
        """Check if deadline check should run."""
        if self.last_deadline_check is None:
            return True

        interval = timedelta(hours=SCHEDULE_CONFIG['deadline_check_hours'])
        return now - self.last_deadline_check >= interval

    def _should_send_digest(self, now: datetime) -> bool:
        """Check if daily digest should be sent."""
        if self.last_daily_digest and self.last_daily_digest.date() == now.date():
            return False  # Already sent today

        digest_time = SCHEDULE_CONFIG['daily_digest_time']
        hour, minute = map(int, digest_time.split(':'))

        # Send if we're past the digest time and haven't sent today
        if now.hour >= hour and now.minute >= minute:
            if self.last_daily_digest is None or self.last_daily_digest.date() < now.date():
                return True

        return False

    def _run_discovery(self):
        """Run RFP discovery and send notifications."""
        logger.info("Running scheduled discovery...")

        try:
            engine = RFPDiscoveryEngine()
            stats = engine.run_discovery()

            self.last_discovery = datetime.now()

            # Get newly discovered RFPs (from this run)
            # We'll check for RFPs created in the last discovery interval
            new_rfps = self._get_recent_rfps(hours=SCHEDULE_CONFIG['discovery_interval_hours'])

            if new_rfps:
                logger.info(f"Found {len(new_rfps)} new RFPs, sending notification...")
                self.notification_service.send_new_rfps_alert(new_rfps, stats)
            else:
                logger.info("No new relevant RFPs found")

        except Exception as e:
            logger.error(f"Discovery failed: {e}")

    def _check_deadlines(self):
        """Check for upcoming deadlines and send reminders."""
        logger.info("Checking upcoming deadlines...")

        try:
            days = SCHEDULE_CONFIG['deadline_reminder_days']
            send_deadline_alerts(days=days)
            self.last_deadline_check = datetime.now()

        except Exception as e:
            logger.error(f"Deadline check failed: {e}")

    def _send_daily_digest(self):
        """Send daily digest email."""
        logger.info("Sending daily digest...")

        try:
            send_daily_digest()
            self.last_daily_digest = datetime.now()

        except Exception as e:
            logger.error(f"Daily digest failed: {e}")

    def _get_recent_rfps(self, hours: int) -> list:
        """Get RFPs created within the last N hours."""
        cutoff = datetime.now() - timedelta(hours=hours)

        all_rfps = db.get_all_rfps()
        recent = []

        for rfp in all_rfps:
            if rfp.get('created_at'):
                try:
                    created = datetime.strptime(rfp['created_at'][:19], '%Y-%m-%d %H:%M:%S')
                    if created >= cutoff:
                        recent.append(rfp)
                except (ValueError, TypeError):
                    pass

        return recent

    def run_now(self, task: str = 'all'):
        """Manually trigger a scheduled task."""
        if task in ('all', 'discovery'):
            self._run_discovery()

        if task in ('all', 'deadlines'):
            self._check_deadlines()

        if task in ('all', 'digest'):
            self._send_daily_digest()


# Global scheduler instance
_scheduler: Optional[SchedulerService] = None


def get_scheduler() -> SchedulerService:
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = SchedulerService()
    return _scheduler


def start_scheduler():
    """Start the global scheduler."""
    scheduler = get_scheduler()
    scheduler.start()
    return scheduler


def stop_scheduler():
    """Stop the global scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.stop()
        _scheduler = None


def run_discovery_now():
    """Run discovery immediately."""
    scheduler = get_scheduler()
    scheduler.run_now('discovery')


def run_all_tasks_now():
    """Run all scheduled tasks immediately."""
    scheduler = get_scheduler()
    scheduler.run_now('all')


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("Starting scheduler...")
    print(f"Discovery interval: {SCHEDULE_CONFIG['discovery_interval_hours']} hours")
    print(f"Daily digest time: {SCHEDULE_CONFIG['daily_digest_time']}")
    print(f"Deadline reminder: {SCHEDULE_CONFIG['deadline_reminder_days']} days before")
    print("\nPress Ctrl+C to stop\n")

    scheduler = start_scheduler()

    # Run discovery immediately on start
    print("Running initial discovery...")
    run_discovery_now()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping scheduler...")
        stop_scheduler()
        print("Done")
