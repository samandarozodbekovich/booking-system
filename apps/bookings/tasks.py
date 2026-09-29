import logging

from celery import shared_task

from .services import expire_stale_pending_bookings

logger = logging.getLogger(__name__)


@shared_task
def expire_pending_bookings() -> int:
    """Periodic task: cancel pending bookings whose deadline has passed."""
    count = expire_stale_pending_bookings()
    if count:
        logger.info("Expired %s pending booking(s).", count)
    return count