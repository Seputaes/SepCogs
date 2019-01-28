from typing import Optional, List

import pytz
from pytz.tzinfo import DstTzInfo


class TimezoneStrings(object):

    TZ_MAP = {
        "hawaii": "US/Hawaii",
        "alaska": "US/Alaska",
        "pacific": "US/Pacific",
        "mountain": "US/Mountain",
        "central": "US/Central",
        "eastern": "US/Eastern",
        "atlantic": "Canada/Atlantic",
        "utc": "UTC",
    }

    @staticmethod
    def get_timezone_options() -> List[str]:
        return sorted(TimezoneStrings.TZ_MAP.keys())

    @staticmethod
    def get_pytz_string(tz: str) -> Optional[str]:
        if tz in pytz.all_timezones:
            return tz
        return TimezoneStrings.TZ_MAP.get(tz.lower())

    @staticmethod
    def get_tz_info(tz: str) -> Optional[DstTzInfo]:
        tz_str = TimezoneStrings.get_pytz_string(tz)
        if tz_str:
            return pytz.timezone(tz_str)
