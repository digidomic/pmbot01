"""
Polymarket Activity Scraper
Scrapes user activity from Polymarket profile pages
"""
import re
import json
import time
import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class RawTrade:
    """Raw trade data from scraping"""
    trade_id: str
    market_slug: str
    market_question: str
    side: str  # BUY or SELL
    outcome: str  # YES or NO
    amount: float
    price: float
    timestamp: datetime
    tx_hash: Optional[str] = None


class PolymarketScraper:
    """Scraper for Polymarket user activity"""
    
    BASE_URL = "https://polymarket.com"
    
    def __init__(self, target_username: str = "0x8dxd"):
        self.target_username = target_username
        self.target_url = f"{self.BASE_URL}/profile/@{target_username}"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def fetch_activity(self, limit: int = 20) -> list[RawTrade]:
        """
        Fetch recent trades from user's activity page
        
        Note: This uses the public profile page. In production, 
        consider using the CLOB API for more reliable data.
        """
        trades = []
        
        try:
            logger.info(f"Fetching activity for {self.target_username}")
            response = self.session.get(
                f"{self.target_url}?tab=activity",
                timeout=30
            )
            response.raise_for_status()
            
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try to find activity data in script tags (Next.js data)
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and '__NEXT_DATA__' in script.string:
                    try:
                        # Try multiple patterns
                        json_match = re.search(r'window\.__NEXT_DATA__\s*=\s*({.+?});', script.string, re.DOTALL)
                        if not json_match:
                            # Try without semicolon
                            json_match = re.search(r'window\.__NEXT_DATA__\s*=\s*({.+})', script.string, re.DOTALL)
                        
                        if json_match:
                            data = json.loads(json_match.group(1))
                            trades = self._parse_nextjs_data(data, limit)
                            if trades:
                                logger.info(f"Parsed {len(trades)} trades from Next.js data")
                                return trades
                        else:
                            logger.warning("Found __NEXT_DATA__ but couldn't extract JSON")
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON decode error: {e}")
                    except Exception as e:
                        logger.warning(f"Failed to parse Next.js data: {e}")
            
            logger.info("No Next.js data found, trying HTML fallback")
            
            # Fallback: Try to parse activity from HTML
            trades = self._parse_html_activity(soup, limit)
            
        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        
        return trades
    
    def _parse_nextjs_data(self, data: dict, limit: int) -> list[RawTrade]:
        """Parse trades from Next.js data"""
        trades = []
        
        try:
            # Navigate through Next.js data structure
            props = data.get('props', {})
            page_props = props.get('pageProps', {})
            
            logger.debug(f"pageProps keys: {list(page_props.keys())}")
            
            # Look for activity/trades in various locations
            activities = []
            
            # Try common locations for activity data
            if 'activities' in page_props:
                activities = page_props['activities']
                logger.info(f"Found {len(activities)} activities in pageProps['activities']")
            elif 'user' in page_props and isinstance(page_props['user'], dict) and 'activities' in page_props['user']:
                activities = page_props['user']['activities']
                logger.info(f"Found {len(activities)} activities in pageProps['user']['activities']")
            elif 'dehydratedState' in page_props:
                # React Query dehydrated state
                queries = page_props['dehydratedState'].get('queries', [])
                logger.debug(f"Searching {len(queries)} queries in dehydratedState")
                for query in queries:
                    query_data = query.get('state', {}).get('data', {})
                    if isinstance(query_data, dict) and 'activities' in query_data:
                        activities = query_data['activities']
                        logger.info(f"Found {len(activities)} activities in dehydratedState query")
                        break
                    elif isinstance(query_data, list):
                        for item in query_data:
                            if isinstance(item, dict) and 'activities' in item:
                                activities = item['activities']
                                logger.info(f"Found {len(activities)} activities in dehydratedState list item")
                                break
            
            if not activities:
                logger.warning("No activities found in Next.js data structure")
                # Debug: Show available keys
                logger.debug(f"Available keys in pageProps: {list(page_props.keys())}")
                return trades
            
            logger.info(f"Parsing {len(activities[:limit])} activities")
            for activity in activities[:limit]:
                trade = self._parse_activity_item(activity)
                if trade:
                    trades.append(trade)
                    logger.debug(f"Parsed trade: {trade.side} {trade.outcome} - {trade.amount} USDC")
            
            logger.info(f"Successfully parsed {len(trades)} trades from Next.js data")
                    
        except Exception as e:
            logger.error(f"Error parsing Next.js data: {e}", exc_info=True)
        
        return trades
    
    def _parse_activity_item(self, activity: dict) -> Optional[RawTrade]:
        """Parse a single activity item"""
        try:
            # Skip non-trade activities
            if activity.get('type') not in ['buy', 'sell', 'TRADE']:
                return None
            
            trade_id = activity.get('id') or activity.get('transactionHash', '')
            
            # Extract market info
            market = activity.get('market', {})
            market_slug = market.get('slug', '')
            market_question = market.get('question', '')
            
            # Extract trade details
            side = activity.get('side', 'BUY').upper()
            outcome = activity.get('outcome', 'YES').upper()
            
            # Amount and price
            amount = float(activity.get('takerAmount', 0) or activity.get('amount', 0))
            if amount == 0:
                amount = float(activity.get('makerAmount', 0))
            
            # Convert from wei if needed
            if amount > 1e10:
                amount = amount / 1e6
            
            price = float(activity.get('price', 0))
            
            # Parse timestamp
            timestamp_str = activity.get('timestamp') or activity.get('createdAt')
            timestamp = self._parse_timestamp(timestamp_str)
            
            tx_hash = activity.get('transactionHash')
            
            return RawTrade(
                trade_id=trade_id,
                market_slug=market_slug,
                market_question=market_question,
                side=side,
                outcome=outcome,
                amount=amount,
                price=price,
                timestamp=timestamp,
                tx_hash=tx_hash
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse activity item: {e}")
            return None
    
    def _parse_html_activity(self, soup: BeautifulSoup, limit: int) -> list[RawTrade]:
        """Fallback: Parse activity from HTML structure"""
        trades = []
        
        # Look for activity rows/tables
        activity_rows = soup.find_all(['tr', 'div'], class_=re.compile(r'activity|trade|transaction', re.I))
        
        for row in activity_rows[:limit]:
            try:
                # Try to extract trade info from HTML
                # This is a fallback and may need adjustment based on actual HTML structure
                cells = row.find_all(['td', 'div'])
                if len(cells) >= 4:
                    # Extract data from cells
                    side = cells[0].get_text(strip=True).upper()
                    if side not in ['BUY', 'SELL']:
                        continue
                    
                    market = cells[1].get_text(strip=True)
                    amount_text = cells[2].get_text(strip=True)
                    price_text = cells[3].get_text(strip=True)
                    
                    # Parse amount
                    amount_match = re.search(r'[\d,]+\.?\d*', amount_text)
                    amount = float(amount_match.group(0).replace(',', '')) if amount_match else 0
                    
                    # Parse price
                    price_match = re.search(r'[\d.]+', price_text)
                    price = float(price_match.group(0)) if price_match else 0
                    
                    trade = RawTrade(
                        trade_id=f"html_{int(time.time())}_{len(trades)}",
                        market_slug="",
                        market_question=market,
                        side=side,
                        outcome="YES",
                        amount=amount,
                        price=price,
                        timestamp=datetime.now()
                    )
                    trades.append(trade)
                    
            except Exception as e:
                logger.warning(f"Failed to parse HTML row: {e}")
        
        return trades
    
    def _parse_timestamp(self, timestamp_str) -> datetime:
        """Parse various timestamp formats"""
        if not timestamp_str:
            return datetime.now()
        
        try:
            # Try ISO format
            if isinstance(timestamp_str, str):
                if timestamp_str.endswith('Z'):
                    timestamp_str = timestamp_str[:-1] + '+00:00'
                return datetime.fromisoformat(timestamp_str)
            # Try Unix timestamp (seconds)
            elif isinstance(timestamp_str, (int, float)):
                if timestamp_str > 1e12:  # Milliseconds
                    timestamp_str = timestamp_str / 1000
                return datetime.fromtimestamp(timestamp_str)
        except:
            pass
        
        return datetime.now()
    
    def fetch_with_api(self, api_client, limit: int = 20) -> list[RawTrade]:
        """
        Alternative: Fetch using CLOB API (more reliable)
        Requires authenticated API client
        """
        trades = []
        
        try:
            # Use CLOB client to get trades
            # This is a placeholder - actual implementation depends on clob-client
            logger.info("Fetching trades via CLOB API")
            
            # Get user's trades from API
            # Note: This requires the target user's address
            # response = api_client.get_trades(...)
            
        except Exception as e:
            logger.error(f"API fetch failed: {e}")
        
        return trades
