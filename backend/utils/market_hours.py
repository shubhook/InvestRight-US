from datetime import datetime, date, time
import pytz

# US Eastern Time for NYSE
ET = pytz.timezone("America/New_York")

# NYSE Regular Trading Hours (RTH): 09:30 - 16:00 ET
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)
TRADING_DAYS = {0, 1, 2, 3, 4}  # Monday=0 … Friday=4

# NYSE exchange holidays
# Source: NYSE Market Holidays calendar
# https://www.nyse.com/markets/hours-calendars
NYSE_HOLIDAYS = {
    # 2025
    date(2025, 1, 1),    # New Year's Day
    date(2025, 1, 20),   # Martin Luther King Jr. Day
    date(2025, 2, 17),   # Presidents' Day
    date(2025, 4, 18),   # Good Friday
    date(2025, 5, 26),   # Memorial Day
    date(2025, 6, 19),   # Juneteenth (observed)
    date(2025, 7, 4),    # Independence Day
    date(2025, 9, 1),    # Labor Day
    date(2025, 11, 27),  # Thanksgiving Day
    date(2025, 12, 25),  # Christmas Day
    
    # 2026
    date(2026, 1, 1),    # New Year's Day
    date(2026, 1, 19),   # Martin Luther King Jr. Day
    date(2026, 2, 16),   # Presidents' Day
    date(2026, 4, 3),    # Good Friday
    date(2026, 5, 25),   # Memorial Day
    date(2026, 6, 19),   # Juneteenth
    date(2026, 7, 3),    # Independence Day (observed)
    date(2026, 9, 7),    # Labor Day
    date(2026, 11, 26),  # Thanksgiving Day
    date(2026, 12, 25),  # Christmas Day
    
    # 2027
    date(2027, 1, 1),    # New Year's Day
    date(2027, 1, 18),   # Martin Luther King Jr. Day
    date(2027, 2, 15),   # Presidents' Day
    date(2027, 3, 26),   # Good Friday
    date(2027, 5, 31),   # Memorial Day
    date(2027, 6, 18),   # Juneteenth (observed)
    date(2027, 7, 5),    # Independence Day (observed)
    date(2027, 9, 6),    # Labor Day
    date(2027, 11, 25),  # Thanksgiving Day
    date(2027, 12, 24),  # Christmas Day (observed)
}


def is_market_open() -> bool:
    """
    Return True if NYSE is currently in its regular trading session.
    Checks weekday, exchange holidays, and market hours (09:30–16:00 ET).
    """
    now_et = datetime.now(ET)
    if now_et.weekday() not in TRADING_DAYS:
        return False
    if now_et.date() in NYSE_HOLIDAYS:
        return False
    current_time = now_et.time()
    return MARKET_OPEN <= current_time <= MARKET_CLOSE
