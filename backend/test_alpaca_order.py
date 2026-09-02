#!/usr/bin/env python3
"""
Test script for Alpaca Paper Trading integration.
Places a 1-share AAPL paper BUY order, checks status, and optionally cancels.

Requires:
    ALPACA_API_KEY and ALPACA_SECRET_KEY in environment
    
Usage:
    export ALPACA_API_KEY=your_key_here
    export ALPACA_SECRET_KEY=your_secret_here
    python3 backend/test_alpaca_order.py
"""

import os
import sys
import time

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from broker.alpaca_paper_broker import AlpacaPaperBroker

def main():
    print("=== Alpaca Paper Trading Test ===\n")
    
    # Check credentials
    if not os.getenv("ALPACA_API_KEY") or not os.getenv("ALPACA_SECRET_KEY"):
        print("ERROR: ALPACA_API_KEY and ALPACA_SECRET_KEY must be set")
        print("\nUsage:")
        print("  export ALPACA_API_KEY=your_key")
        print("  export ALPACA_SECRET_KEY=your_secret")
        print("  python3 backend/test_alpaca_order.py")
        sys.exit(1)
    
    # Initialize broker
    print("1. Initializing AlpacaPaperBroker...")
    broker = AlpacaPaperBroker()
    
    if not broker.trading_client:
        print("   ✗ FAILED: Trading client not initialized")
        sys.exit(1)
    
    print("   ✓ Trading client initialized\n")
    
    # Place order
    print("2. Placing paper order: BUY 1 share AAPL (MARKET, DAY)")
    order_params = {
        "symbol": "AAPL",
        "action": "BUY",
        "quantity": 1,
        "order_type": "MARKET",
        "trade_id": "test-" + str(int(time.time())),
    }
    
    result = broker.place_order(order_params)
    
    if result.get("status") == "FAILED":
        print(f"   ✗ Order FAILED: {result.get('failure_reason')}")
        sys.exit(1)
    
    order_id = result.get("order_id")
    broker_order_id = result.get("broker_order_id")
    
    print(f"   ✓ Order placed")
    print(f"   Order ID: {order_id}")
    print(f"   Alpaca Order ID: {broker_order_id}")
    print(f"   Status: {result.get('status')}")
    if result.get('filled_price'):
        print(f"   Filled Price: ${result.get('filled_price'):.2f}")
    print()
    
    # Check status
    print("3. Checking order status...")
    time.sleep(1)
    
    status_result = broker.get_order_status(broker_order_id)
    print(f"   Status: {status_result.get('status')}")
    print(f"   Filled Qty: {status_result.get('filled_quantity', 0)}")
    if status_result.get('filled_price'):
        print(f"   Filled Price: ${status_result.get('filled_price'):.2f}")
    print()
    
    # Cancel if not filled
    final_status = status_result.get('status')
    if final_status in ["PENDING", "NEW", "ACCEPTED"]:
        print("4. Cancelling pending order...")
        cancelled = broker.cancel_order(broker_order_id)
        if cancelled:
            print("   ✓ Order cancelled")
        else:
            print("   ✗ Cancel failed")
    elif final_status == "FILLED":
        print("4. Order filled — leaving paper position")
    else:
        print(f"4. Order terminal status: {final_status}")
    
    print("\n=== TEST COMPLETE ===")
    print(f"Real Alpaca paper order placed: {broker_order_id}")
    print("No secrets printed. No secrets committed.")


if __name__ == "__main__":
    main()
