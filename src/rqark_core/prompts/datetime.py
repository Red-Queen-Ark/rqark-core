from datetime import datetime
from zoneinfo import ZoneInfo

from rqark_core.types.prompt import BasePrompt


class DateTimePrompt(BasePrompt):
    priority = 60

    def __init__(self, timezone_name: str = 'Asia/Hong_Kong') -> None:
        self._tz = ZoneInfo(timezone_name)

    def get_messages(self) -> str:
        now = datetime.now(self._tz)
        tz_name = str(self._tz)
        utc_offset = now.utcoffset()
        offset_hours = int(utc_offset.total_seconds() / 3600) if utc_offset else 0
        sign = '+' if offset_hours >= 0 else ''
        return f'## Current Time\nNow: {now:%Y-%m-%d %H:%M:%S %A} ({tz_name}, UTC{sign}{offset_hours})'

    def params(self) -> dict[str, str]:
        return {'timezone_name': str(self._tz)}
