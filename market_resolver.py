"""
Dynamic Market Resolver for BTC Up/Down Markets

Fetches current active market condition IDs from Polymarket API.
5m and 15m markets rotate every 5/15 minutes with new condition IDs.
"""
import logging
import re
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

import requests

logger = logging.getLogger(__name__)


@dataclass
class MarketInfo:
    """Information about an active market"""
    condition_id: str
    market_slug: str
    question: str
    end_time: Optional[datetime] = None
    active: bool = True
    
    def __repr__(self):
        return f"MarketInfo(slug={self.market_slug}, condition_id={self.condition_id[:20]}...)"


class MarketResolver:
    """
    Resolves current active market condition IDs for BTC Up/Down markets.
    
    Polymarket rotates these markets every 5/15 minutes:
    - 5m market: New condition ID every 5 minutes
    - 15m market: New condition ID every 15 minutes
    
    This resolver fetches the current active market from Polymarket's API
    and caches it with automatic refresh.
    """
    
    # Polymarket GraphQL API endpoint
    POLYMARKET_API_URL = "https://polymarket.com/api/graphql"
    
    # Market type slugs for searching
    MARKET_PATTERNS = {
        "5m": ["btc-updown-5m", "bitcoin-updown-5m", "will-bitcoin-be-up-5m"],
        "15m": ["btc-updown-15m", "bitcoin-updown-15m", "will-bitcoin-be-up-15m"]
    }
    
    def __init__(self, market_type: str = "5m", update_interval: int = 60):
        """
        Initialize market resolver
        
        Args:
            market_type: "5m" or "15m"
            update_interval: Seconds between updates (default: 60)
        """
        if market_type not in ("5m", "15m"):
            raise ValueError(f"market_type must be '5m' or '15m', got '{market_type}'")
        
        self.market_type = market_type
        self.update_interval = update_interval
        self._current_market: Optional[MarketInfo] = None
        self._last_update: float = 0
        self._fallback_condition_id: Optional[str] = None
        self._fallback_market_slug: Optional[str] = None
        
        logger.info(f"MarketResolver initialized for {market_type} markets")
    
    def set_fallback(self, condition_id: str, market_slug: str):
        """Set fallback values if API fetch fails"""
        self._fallback_condition_id = condition_id
        self._fallback_market_slug = market_slug
        logger.debug(f"Fallback set: {market_slug}")
    
    def should_update(self) -> bool:
        """Check if we need to update the market info"""
        elapsed = time.time() - self._last_update
        return elapsed > self.update_interval or self._current_market is None
    
    def _query_polymarket_graphql(self, query: str, variables: Dict = None) -> Optional[Dict]:
        """Execute GraphQL query against Polymarket API"""
        try:
            payload = {"query": query}
            if variables:
                payload["variables"] = variables
            
            response = requests.post(
                self.POLYMARKET_API_URL,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0"
                },
                timeout=10
            )
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            logger.warning(f"GraphQL request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in GraphQL query: {e}")
            return None
    
    def _fetch_active_markets(self) -> list[Dict[str, Any]]:
        """Fetch active BTC Up/Down markets from Polymarket"""
        # GraphQL query to search for BTC markets
        query = """
        query SearchMarkets($search: String!, $limit: Int!) {
            markets(
                search: $search
                limit: $limit
                active: true
                closed: false
                orderBy: "volume"
                orderDirection: "desc"
            ) {
                id
                conditionId
                slug
                question
                endDate
                active
                closed
                volume
                liquidity
            }
        }
        """
        
        # Try different search terms
        search_terms = ["bitcoin up", "btc updown", "will bitcoin be up"]
        all_markets = []
        
        for search in search_terms:
            try:
                result = self._query_polymarket_graphql(
                    query, 
                    {"search": search, "limit": 20}
                )
                
                if result and "data" in result and "markets" in result["data"]:
                    markets = result["data"]["markets"]
                    all_markets.extend(markets)
                    
            except Exception as e:
                logger.debug(f"Search '{search}' failed: {e}")
                continue
        
        return all_markets
    
    def _parse_market_info(self, market_data: Dict) -> Optional[MarketInfo]:
        """Parse market data into MarketInfo"""
        try:
            condition_id = market_data.get("conditionId") or market_data.get("condition_id")
            slug = market_data.get("slug") or market_data.get("market_slug")
            question = market_data.get("question", "")
            
            if not condition_id or not slug:
                return None
            
            # Parse end time if available
            end_time = None
            end_date_str = market_data.get("endDate") or market_data.get("end_date")
            if end_date_str:
                try:
                    end_time = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                except:
                    pass
            
            return MarketInfo(
                condition_id=condition_id,
                market_slug=slug,
                question=question,
                end_time=end_time,
                active=market_data.get("active", True)
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse market info: {e}")
            return None
    
    def _matches_market_type(self, market_info: MarketInfo) -> bool:
        """Check if market matches our target type (5m or 15m)"""
        slug_lower = market_info.market_slug.lower()
        question_lower = market_info.question.lower()
        
        patterns = self.MARKET_PATTERNS.get(self.market_type, [])
        
        for pattern in patterns:
            if pattern.lower() in slug_lower or pattern.lower() in question_lower:
                return True
        
        # Also check question text for time indicators
        if self.market_type == "5m":
            if any(x in question_lower for x in ["5 minute", "5-minute", "5min"]):
                return True
        elif self.market_type == "15m":
            if any(x in question_lower for x in ["15 minute", "15-minute", "15min"]):
                return True
        
        return False
    
    def _fetch_from_api(self) -> Optional[MarketInfo]:
        """Fetch current active market from Polymarket API"""
        logger.debug(f"Fetching {self.market_type} market from Polymarket API...")
        
        markets = self._fetch_active_markets()
        
        if not markets:
            logger.warning("No markets found from API")
            return None
        
        # Filter and parse markets
        for market_data in markets:
            market_info = self._parse_market_info(market_data)
            
            if market_info and self._matches_market_type(market_info):
                # Check if market is still active
                if market_info.end_time and market_info.end_time < datetime.now():
                    logger.debug(f"Market {market_info.market_slug} has ended")
                    continue
                
                logger.info(f"Found {self.market_type} market: {market_info.market_slug}")
                return market_info
        
        logger.warning(f"No matching {self.market_type} market found in {len(markets)} markets")
        return None
    
    def _fetch_from_clob(self) -> Optional[MarketInfo]:
        """Alternative: Fetch from CLOB API if available"""
        try:
            # Try CLOB markets endpoint
            url = "https://clob.polymarket.com/markets"
            response = requests.get(url, params={"active": "true", "closed": "false"}, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            markets = data.get("data", [])
            
            for market in markets:
                slug = market.get("market_slug") or market.get("slug", "")
                condition_id = market.get("condition_id") or market.get("conditionId", "")
                question = market.get("question", "")
                
                if not condition_id:
                    continue
                
                market_info = MarketInfo(
                    condition_id=condition_id,
                    market_slug=slug,
                    question=question,
                    active=True
                )
                
                if self._matches_market_type(market_info):
                    logger.info(f"Found {self.market_type} market from CLOB: {slug}")
                    return market_info
                    
        except Exception as e:
            logger.debug(f"CLOB fetch failed: {e}")
        
        return None
    
    def update(self, force: bool = False) -> bool:
        """
        Update market info if needed
        
        Args:
            force: Force update even if not due
            
        Returns:
            True if update was successful (or not needed)
        """
        if not force and not self.should_update() and self._current_market:
            return True
        
        logger.info(f"Updating {self.market_type} market info...")
        
        # Try GraphQL API first
        market_info = self._fetch_from_api()
        
        # Fallback to CLOB API
        if not market_info:
            logger.debug("Trying CLOB API as fallback...")
            market_info = self._fetch_from_clob()
        
        if market_info:
            old_slug = self._current_market.market_slug if self._current_market else None
            old_condition = self._current_market.condition_id if self._current_market else None
            
            self._current_market = market_info
            self._last_update = time.time()
            
            # Log if market changed
            if old_slug and old_slug != market_info.market_slug:
                logger.info(
                    f"🔄 Market changed! {old_slug} -> {market_info.market_slug}"
                )
            elif old_condition and old_condition != market_info.condition_id:
                logger.info(
                    f"🔄 Condition ID changed! {old_condition[:20]}... -> {market_info.condition_id[:20]}..."
                )
            else:
                logger.info(f"✅ Market resolved: {market_info.market_slug}")
            
            return True
        
        # Update failed - use fallback if available
        if self._fallback_condition_id and not self._current_market:
            logger.warning(f"Using fallback condition ID: {self._fallback_condition_id[:20]}...")
            self._current_market = MarketInfo(
                condition_id=self._fallback_condition_id,
                market_slug=self._fallback_market_slug or "unknown",
                question="Fallback market",
                active=True
            )
            self._last_update = time.time()
            return True
        
        logger.error(f"Failed to update {self.market_type} market info")
        return False
    
    def get_condition_id(self) -> Optional[str]:
        """Get current condition ID, updating if needed"""
        if self.should_update():
            self.update()
        
        if self._current_market:
            return self._current_market.condition_id
        
        return self._fallback_condition_id
    
    def get_market_slug(self) -> Optional[str]:
        """Get current market slug, updating if needed"""
        if self.should_update():
            self.update()
        
        if self._current_market:
            return self._current_market.market_slug
        
        return self._fallback_market_slug
    
    def get_market_info(self) -> Optional[MarketInfo]:
        """Get full market info, updating if needed"""
        if self.should_update():
            self.update()
        return self._current_market
    
    def get_last_update_time(self) -> float:
        """Get timestamp of last successful update"""
        return self._last_update
    
    def is_fresh(self) -> bool:
        """Check if current market info is fresh"""
        return not self.should_update()
    
    def force_refresh(self) -> bool:
        """Force immediate refresh of market info"""
        return self.update(force=True)


# Factory functions for convenience
def create_market_resolver_5m(update_interval: int = 60) -> MarketResolver:
    """Create resolver for 5m markets"""
    return MarketResolver(market_type="5m", update_interval=update_interval)


def create_market_resolver_15m(update_interval: int = 60) -> MarketResolver:
    """Create resolver for 15m markets"""
    return MarketResolver(market_type="15m", update_interval=update_interval)


def get_current_market_info(market_type: str = "5m") -> Optional[MarketInfo]:
    """
    Quick helper to get current market info without managing resolver instance
    
    Args:
        market_type: "5m" or "15m"
        
    Returns:
        MarketInfo or None
    """
    resolver = MarketResolver(market_type=market_type)
    if resolver.update():
        return resolver.get_market_info()
    return None


# Global resolvers for singleton pattern
_5m_resolver: Optional[MarketResolver] = None
_15m_resolver: Optional[MarketResolver] = None


def get_resolver(market_type: str = "5m") -> MarketResolver:
    """Get or create global resolver instance"""
    global _5m_resolver, _15m_resolver
    
    if market_type == "5m":
        if _5m_resolver is None:
            _5m_resolver = create_market_resolver_5m()
        return _5m_resolver
    elif market_type == "15m":
        if _15m_resolver is None:
            _15m_resolver = create_market_resolver_15m()
        return _15m_resolver
    else:
        raise ValueError(f"Invalid market_type: {market_type}")
