import logging
from datetime import datetime
from zoneinfo import ZoneInfo


class ISTFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        timestamp = datetime.fromtimestamp(record.created, ZoneInfo("Asia/Kolkata"))
        return (
            timestamp.strftime(datefmt) if datefmt else timestamp.isoformat(timespec="milliseconds")
        )
