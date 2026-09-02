from datetime import datetime, date, time, timedelta
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


def get_session() -> dict:
    """
    Returns current market session info for frontend.
    
    Returns:
        dict with:
            - et_iso (str): Current ET time as ISO-8601 with offset
            - is_rth (bool): True if NYSE is in regular trading hours
            - next_bell (str): ISO-8601 ET of next open or close
    """
    now_et = datetime.now(ET)
    today = now_et.date()
    
    # Get current state
    is_rth = is_market_open()
    
    # Determine next bell
    if is_rth:
        # Market is open, next bell is today's close at 16:00
        next_bell_dt = datetime.combine(today, MARKET_CLOSE).replace(tzinfo=ET)
    else:
        # Market is closed, find next open at 09:30
        # Look ahead up to 10 days to find next trading day
        search_start = today
        search_end = today + timedelta(days=10)
        schedule = _nyse.schedule(start_date=search_start, end_date=search_end)
        
        if not schedule.empty:
            # Find next trading day
            for trading_date in schedule.index:
                trading_day = trading_date.date()
                open_time = datetime.combine(trading_day, MARKET_OPEN).replace(tzinfo=ET)
                
                # If it's today and we haven't passed open time yet, use today
                # Otherwise use the next trading day's open
                if open_time > now_et:
                    next_bell_dt = open_time
                    break
            else:
                # Fallback: next business day at 09:30 (shouldn't happen with 10-day window)
                next_bell_dt = datetime.combine(today + timedelta(days=1), MARKET_OPEN).replace(tzinfo=ET)
        else:
            # Fallback if schedule lookup fails
            next_bell_dt = datetime.combine(today + timedelta(days=1), MARKET_OPEN).replace(tzinfo=ET)
    
    return {
        "et_iso": now_et.isoformat(),
        "is_rth": is_rth,
        "next_bell": next_bell_dt.isoformat(),
    }
