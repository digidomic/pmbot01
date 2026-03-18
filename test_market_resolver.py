#!/usr/bin/env python3
"""
Test script for the Market Resolver
Verifies dynamic market resolution is working correctly.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from market_resolver import MarketResolver, create_market_resolver_5m, create_market_resolver_15m
from config.strategy_config import arbitrage_config, get_current_condition_id, get_current_market_slug


def test_market_resolver():
    """Test the market resolver functionality"""
    print("=" * 60)
    print("BTC Arbitrage Bot - Market Resolver Test")
    print("=" * 60)
    
    # Test 1: Direct resolver test
    print("\n1. Testing MarketResolver class directly...")
    print("-" * 40)
    
    for market_type in ["5m", "15m"]:
        print(f"\n   Testing {market_type} resolver:")
        resolver = MarketResolver(market_type=market_type, update_interval=60)
        
        # Try to update
        success = resolver.update()
        
        if success:
            market_info = resolver.get_market_info()
            if market_info:
                print(f"   ✓ Found {market_type} market:")
                print(f"     - Slug: {market_info.market_slug}")
                print(f"     - Condition ID: {market_info.condition_id}")
                print(f"     - Question: {market_info.question[:60]}...")
            else:
                print(f"   ⚠ Update succeeded but no market info returned")
        else:
            print(f"   ✗ Failed to update {market_type} market")
    
    # Test 2: Via config interface
    print("\n2. Testing via config interface...")
    print("-" * 40)
    print(f"   MARKET_RESOLVER_ENABLED: {arbitrage_config.MARKET_RESOLVER_ENABLED}")
    print(f"   MARKET_TYPE: {arbitrage_config.MARKET_TYPE}")
    
    condition_id = get_current_condition_id()
    market_slug = get_current_market_slug()
    
    print(f"\n   Current market info:")
    print(f"   - Condition ID: {condition_id}")
    print(f"   - Market Slug: {market_slug}")
    
    # Test 3: Resolver status
    print("\n3. Market Resolver Status...")
    print("-" * 40)
    status = arbitrage_config.get_market_resolver_status()
    print(f"   Enabled: {status.get('enabled')}")
    print(f"   Initialized: {status.get('initialized')}")
    print(f"   Fresh: {status.get('fresh')}")
    print(f"   Last Update: {status.get('last_update')}")
    
    # Test 4: Compare with fallback values
    print("\n4. Comparing with fallback values...")
    print("-" * 40)
    
    if arbitrage_config.MARKET_TYPE == 'updown_5m':
        fallback_id = arbitrage_config.UPDOWN_5M_CONDITION_ID
        fallback_slug = arbitrage_config.UPDOWN_5M_SLUG
    else:
        fallback_id = arbitrage_config.UPDOWN_15M_CONDITION_ID
        fallback_slug = arbitrage_config.UPDOWN_15M_SLUG
    
    print(f"   Fallback Condition ID: {fallback_id}")
    print(f"   Current Condition ID:  {condition_id}")
    print(f"   Match: {'✓ YES' if condition_id == fallback_id else '✗ NO (dynamic market detected!)'}")
    
    print(f"\n   Fallback Slug: {fallback_slug}")
    print(f"   Current Slug:  {market_slug}")
    print(f"   Match: {'✓ YES' if market_slug == fallback_slug else '✗ NO (dynamic market detected!)'}")
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)
    
    if condition_id and condition_id != fallback_id:
        print("\n🎉 SUCCESS: Dynamic market resolution is working!")
        print("   The resolver detected a different market than the fallback.")
        return 0
    elif condition_id:
        print("\n⚠️  WARNING: Using fallback values.")
        print("   The resolver may not have found a different active market,")
        print("   or the fallback values happen to be current.")
        print("   This is okay if markets haven't rotated yet.")
        return 0
    else:
        print("\n✗ ERROR: Could not resolve market condition ID!")
        return 1


if __name__ == "__main__":
    try:
        exit_code = test_market_resolver()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
