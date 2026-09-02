from datetime import datetime, date, time
import pytz

IST = pytz.timezone("Asia/Kolkata")
MARKET_OPEN  = time(9, 15)
MARKET_CLOSE = time(15, 30)
TRADING_DAYS = {0, 1, 2, 3, 4}  # Monday=0 … Friday=4

# NSE/BSE exchange holidays — update annually.
# Source: NSE India circular (https://www.nseindia.com/resources/exchange-communication-holidays)
NSE_HOLIDAYS = {
    # 2025
    date(2025, 1, 26),   # Republic Day
    date(2025, 2, 26),   # Mahashivratri
    date(2025, 3, 14),   # Holi
    date(2025, 3, 31),   # Id-Ul-Fitr (Ramadan Eid)
    date(2025, 4, 14),   # Dr. Ambedkar Jayanti / Good Friday
    date(2025, 4, 18),   # Good Friday (observed)
    date(2025, 5, 1),    # Maharashtra Day
    date(2025, 8, 15),   # Independence Day
    date(2025, 8, 27),   # Ganesh Chaturthi
    date(2025, 10, 2),   # Gandhi Jayanti / Dussehra
    date(2025, 10, 20),  # Diwali Laxmi Puja (Muhurat trading may occur)
    date(2025, 10, 21),  # Diwali Balipratipada
    date(2025, 11, 5),   # Prakash Gurpurab
    date(2025, 12, 25),  # Christmas
    # 2026
    date(2026, 1, 26),   # Republic Day
    date(2026, 3, 19),   # Holi
    date(2026, 4, 3),    # Good Friday
    date(2026, 8, 15),   # Independence Day
    date(2026, 10, 2),   # Gandhi Jayanti
    date(2026, 12, 25),  # Christmas
}


def is_market_open() -> bool:
    """
    Return True if NSE/BSE is currently in its regular trading session.
    Checks weekday, exchange holidays, and market hours (09:15–15:30 IST).
    """
    now_ist = datetime.now(IST)
    if now_ist.weekday() not in TRADING_DAYS:
        return False
    if now_ist.date() in NSE_HOLIDAYS:
        return False
    current_time = now_ist.time()
    return MARKET_OPEN <= current_time <= MARKET_CLOSE
