import datetime
from langchain.tools import tool

@tool
def get_system_time(timezone: str = "IST") -> str:
    """
    Returns current live system time and date.
    Use this plugin tool whenever the user asks for current time, date, or time zone.
    """
    now = datetime.datetime.now()
    return f"🕒 હાલનો સમય (Current Time): {now.strftime('%Y-%m-%d %H:%M:%S')} ({timezone})"
