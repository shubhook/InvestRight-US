from datetime import datetime, date, time
import pytz
import pandas_market_calendars as mcal

# US Eastern Time for NYSE
ET = pytz.timezone("America/New_York")

# NYSE Regular Trading Hours (RTH): 09:30 - 16:00 ET
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)
TRADING_DAYS = {0, 1, 2, 3, 4}  # Monday=0 … Friday=4

# NYSE calendar from pandas_market_calendars
_nyse = mcal.get_calendar('NYSE')


def is_market_open() -> bool:
    """
    Return True if NYSE is currently in its regular trading session.
    Checks weekday, exchange holidays (via pandas_market_calendars), 
    and market hours (09:30–16:00 ET).
    """
    now_et = datetime.now(ET)
    
    # Check weekday
    if now_et.weekday() not in TRADING_DAYS:
        return False
    
    # Check if today is a valid trading day using NYSE calendar
    today = now_et.date()
    schedule = _nyse.schedule(start_date=today, end_date=today)
    
    if schedule.empty:
        # Not a trading day (holiday or weekend)
        return False
    
    # Check market hours
    current_time = now_et.time()
    return MARKET_OPEN <= current_time <= MARKET_CLOSE
