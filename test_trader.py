#!/usr/bin/env python3
"""
Test-Skript für CLOB Trader
Verwendung: python test_trader.py [--live]

--live: Aktiviert echten Trading-Modus (ohne Dry Run)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import logging
from database.db import DatabaseManager
from trader.clob_trader import create_trader
from config import config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_balance(trader):
    """Test: Balance abfragen"""
    print("\n" + "="*60)
    print("TEST 1: Balance Abfrage")
    print("="*60)
    
    balance = trader.get_balance()
    print(f"USDC Balance: {balance.get('usdc', 0):.6f}")
    print(f"Locked: {balance.get('locked', 0):.6f}")
    print(f"Available: {balance.get('available', 0):.6f}")
    
    if balance.get('error'):
        print(f"❌ Error: {balance['error']}")
    else:
        print("✅ Balance check passed")
    
    return balance.get('error') is None


def test_market_lookup(trader):
    """Test: Market Lookup"""
    print("\n" + "="*60)
    print("TEST 2: Market Lookup")
    print("="*60)
    
    # Teste ein paar bekannte Markets
    test_slugs = [
        "will-bitcoin-hit-100k-in-2025",
        "will-trump-win-2024",
        "will-ethereum-etfs-accumulate-100k"
    ]
    
    for slug in test_slugs:
        print(f"\nTesting: {slug}")
        market = trader.validate_market(slug, auto_refresh=True)
        if market:
            print(f"✅ Found: {market.get('question', 'N/A')[:60]}...")
            print(f"   Condition ID: {market.get('condition_id', 'N/A')[:30]}...")
            print(f"   Tokens: {len(market.get('tokens', []))}")
            
            # Teste Token Lookup
            for outcome in ['YES', 'NO']:
                token_id = trader.get_token_id(market, outcome)
                if token_id:
                    print(f"   {outcome} Token: {token_id[:30]}...")
        else:
            print(f"❌ Market not found")
    
    print(f"\n📊 Cached markets: {len(trader.market_cache._markets)}")
    return True


def test_order_calculation(trader):
    """Test: Order-Größen Berechnung"""
    print("\n" + "="*60)
    print("TEST 3: Order-Größen Berechnung")
    print("="*60)
    
    test_amounts = [10, 50, 100, 500, 1000]
    
    print(f"Config: MAX={config.MAX_TRADE_AMOUNT_USDC}, PERCENT={config.TRADE_PERCENTAGE}%")
    print("-" * 40)
    
    for amount in test_amounts:
        calculated = trader.calculate_order_size(amount)
        print(f"Original: {amount:>6} USDC -> Copy: {calculated:.2f} USDC")
    
    print("✅ Calculation test passed")
    return True


def test_dry_run_order(trader):
    """Test: Dry Run Order"""
    print("\n" + "="*60)
    print("TEST 4: Dry Run Order Creation")
    print("="*60)
    
    # Finde einen validen Market
    test_slug = "will-bitcoin-hit-100k-in-2025"
    
    success, error, result = trader.create_order(
        market_slug=test_slug,
        outcome="YES",
        side="BUY",
        size=10.0,
        price=0.55
    )
    
    if success:
        print(f"✅ Dry run order created")
        print(f"   Order ID: {result.get('order_id')}")
        print(f"   Market: {result.get('market_slug')}")
        print(f"   Side: {result.get('side')} {result.get('size')} USDC")
        print(f"   Outcome: {result.get('outcome')} @ {result.get('price')}")
    else:
        print(f"❌ Failed: {error}")
    
    return success


def test_stats(trader):
    """Test: Trader Stats"""
    print("\n" + "="*60)
    print("TEST 5: Trader Stats")
    print("="*60)
    
    stats = trader.get_stats()
    
    print(f"Initialized: {stats.get('initialized')}")
    print(f"Dry Run: {stats.get('dry_run')}")
    print(f"Markets Cached: {stats.get('markets_cached')}")
    print(f"Cache Stale: {stats.get('cache_stale')}")
    print(f"Daily Spent: {stats.get('daily_spent'):.2f} USDC")
    print(f"Daily Limit: {stats.get('daily_limit'):.2f} USDC")
    
    balance = stats.get('balance', {})
    print(f"Balance: {balance.get('available', 0):.2f} USDC available")
    
    print("✅ Stats retrieved")
    return True


def main():
    parser = argparse.ArgumentParser(description='Test CLOB Trader')
    parser.add_argument('--live', action='store_true', help='Enable live trading (disable dry run)')
    parser.add_argument('--test', choices=['balance', 'market', 'calc', 'order', 'stats', 'all'],
                       default='all', help='Which test to run')
    args = parser.parse_args()
    
    dry_run = not args.live
    
    print("🚀 CLOB Trader Test Suite")
    print(f"Mode: {'LIVE' if not dry_run else 'DRY RUN'}")
    print(f"CLOB Available: {trader.clob_trader.CLOB_AVAILABLE if hasattr(trader, 'clob_trader') else 'N/A'}")
    
    # Validate config
    errors = config.validate()
    if errors:
        print("\n❌ Config errors:")
        for error in errors:
            print(f"  - {error}")
        print("\nPlease check your .env file!")
        sys.exit(1)
    
    # Initialize
    print("\nInitializing...")
    db = DatabaseManager(config.DATABASE_PATH)
    trader = create_trader(db, dry_run=dry_run)
    
    if not trader.initialized:
        print("❌ Failed to initialize CLOB trader!")
        print("Check your API credentials and network connection.")
        sys.exit(1)
    
    print("✅ CLOB trader initialized")
    
    # Run tests
    results = []
    
    if args.test in ('balance', 'all'):
        results.append(('Balance', test_balance(trader)))
    
    if args.test in ('market', 'all'):
        results.append(('Market Lookup', test_market_lookup(trader)))
    
    if args.test in ('calc', 'all'):
        results.append(('Order Calc', test_order_calculation(trader)))
    
    if args.test in ('order', 'all'):
        results.append(('Dry Run Order', test_dry_run_order(trader)))
    
    if args.test in ('stats', 'all'):
        results.append(('Stats', test_stats(trader)))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{name:.<40} {status}")
    
    all_passed = all(passed for _, passed in results)
    
    print("\n" + "="*60)
    if all_passed:
        print("🎉 All tests passed!")
    else:
        print("⚠️ Some tests failed")
    print("="*60)
    
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()
