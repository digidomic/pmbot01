"""
Polymarket Activity Scraper - Scrapes trades from user activity pages
"""
import time
import logging
import requests
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, SoupStrainer
from lxml import html
import lxml.etree as etree

from scraper.models import Trade, ScrapingLog
from database.db import DatabaseManager
from config.settings import config

logger = logging.getLogger(__name__)


class PolymarketActivityScraper:
    """
    Robust scraper for Polymarket user activity.
    Extracts trade information from profile activity pages.
    """
    
    BASE_URL = "https://polymarket.com"
    REQUEST_TIMEOUT = 30
    RETRY_ATTEMPTS = 3
    RETRY_DELAY = 2
    RATE_LIMIT_DELAY = 5
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize the scraper
        
        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager
        self.target_username = config.TARGET_USERNAME
        self.activity_url = f"{self.BASE_URL}/profile/@{self.target_username}?tab=activity"
        
        # Setup session with proper headers to avoid blocking
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        logger.info(f"Initialized scraper for user: {self.target_username}")
    
    def scrape_activity(self, max_trades: int = 50) -> Dict[str, Any]:
        """
        Hauptmethode: Scrape die Activity und speichere neue Trades
        
        Args:
            max_trades: Maximale Anzahl zu verarbeitender Trades
            
        Returns:
            Dict mit Statistiken über den Run
        """
        run_start = datetime.now()
        stats = {
            'success': False,
            'trades_found': 0,
            'new_trades': 0,
            'error_message': None,
            'duration_seconds': 0,
        }
        
        try:
            logger.info(f"Starting activity scrape for {self.target_username}")
            
            # Hole die Activity-Daten
            trades_data = self._fetch_activity_data()
            stats['trades_found'] = len(trades_data)
            
            if not trades_data:
                logger.warning("No trades found in activity")
                stats['error_message'] = "No trades found"
                return stats
            
            # Verarbeite die Trades
            new_trades_count = self._process_trades(trades_data[:max_trades])
            stats['new_trades'] = new_trades_count
            stats['success'] = True
            
            logger.info(
                f"Activity scrape completed: {stats['trades_found']} found, "
                f"{stats['new_trades']} new trades"
            )
            
        except Exception as e:
            logger.error(f"Activity scrape failed: {e}")
            stats['error_message'] = str(e)
        
        finally:
            stats['duration_seconds'] = (datetime.now() - run_start).total_seconds()
            
            # Speichere Log-Eintrag
            self._save_scraping_log(stats)
        
        return stats
    
    def _fetch_activity_data(self) -> List[Dict[str, Any]]:
        """
        Fetch activity data from Polymarket profile page
        
        Returns:
            List of trade dictionaries
        """
        trades = []
        
        for attempt in range(self.RETRY_ATTEMPTS):
            try:
                logger.debug(f"Fetching activity (attempt {attempt + 1})")
                
                # Rate limiting
                if attempt > 0:
                    time.sleep(self.RETRY_DELAY * attempt)
                
                response = self.session.get(
                    self.activity_url,
                    timeout=self.REQUEST_TIMEOUT
                )
                response.raise_for_status()
                
                # Parse die Trades aus der Response
                trades = self._parse_activity_html(response.text)
                
                if trades:
                    break
                else:
                    logger.warning(f"No trades found in attempt {attempt + 1}")
                    
            except requests.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}): {e}")
                if attempt == self.RETRY_ATTEMPTS - 1:
                    raise e
            except Exception as e:
                logger.error(f"Unexpected error in attempt {attempt + 1}: {e}")
                if attempt == self.RETRY_ATTEMPTS - 1:
                    raise e
        
        return trades
    
    def _parse_activity_html(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Parse trades from HTML content using multiple strategies
        
        Args:
            html_content: Raw HTML from activity page
            
        Returns:
            List of parsed trade dictionaries
        """
        trades = []
        
        # Strategie 1: Next.js Data aus Script-Tags
        trades = self._parse_nextjs_data(html_content)
        if trades:
            logger.debug(f"Found {len(trades)} trades via Next.js data")
            return trades
        
        # Strategie 2: LXML/HTML Parsing der Activity-Tabelle
        trades = self._parse_activity_table_lxml(html_content)
        if trades:
            logger.debug(f"Found {len(trades)} trades via HTML table parsing")
            return trades
        
        # Strategie 3: BeautifulSoup Fallback
        trades = self._parse_activity_table_bs4(html_content)
        if trades:
            logger.debug(f"Found {len(trades)} trades via BeautifulSoup parsing")
            return trades
        
        logger.warning("No trades found with any parsing strategy")
        return []
    
    def _parse_nextjs_data(self, html_content: str) -> List[Dict[str, Any]]:
        """Parse trades from Next.js __NEXT_DATA__ script"""
        import re
        import json
        
        try:
            # Suche nach __NEXT_DATA__ Script
            pattern = r'window\.__NEXT_DATA__\s*=\s*({.+?});'
            match = re.search(pattern, html_content, re.DOTALL)
            
            if not match:
                return []
            
            # Parse JSON
            data = json.loads(match.group(1))
            
            # Navigate zu den Activities
            activities = self._extract_activities_from_nextjs(data)
            
            trades = []
            for activity in activities:
                trade = self._parse_activity_item(activity)
                if trade:
                    trades.append(trade)
            
            return trades
            
        except Exception as e:
            logger.debug(f"Next.js parsing failed: {e}")
            return []
    
    def _extract_activities_from_nextjs(self, data: dict) -> List[Dict]:
        """Extract activities array from Next.js data structure"""
        activities = []
        
        try:
            # Verschiedene mögliche Pfade zu den Activities
            paths = [
                ['props', 'pageProps', 'activities'],
                ['props', 'pageProps', 'user', 'activities'],
                ['props', 'pageProps', 'dehydratedState', 'queries'],
            ]
            
            for path in paths:
                current = data
                for key in path:
                    if isinstance(current, dict) and key in current:
                        current = current[key]
                    else:
                        break
                else:
                    # Pfad erfolgreich durchlaufen
                    if isinstance(current, list):
                        activities = current
                        break
                    elif key == 'queries' and isinstance(current, list):
                        # React Query dehydrated state
                        for query in current:
                            if isinstance(query, dict):
                                query_data = query.get('state', {}).get('data')
                                if isinstance(query_data, dict) and 'activities' in query_data:
                                    activities = query_data['activities']
                                    break
                                elif isinstance(query_data, list):
                                    for item in query_data:
                                        if isinstance(item, dict) and 'activities' in item:
                                            activities = item['activities']
                                            break
                            if activities:
                                break
            
            # Filter für Trade-Activities
            if activities:
                activities = [
                    a for a in activities 
                    if isinstance(a, dict) and a.get('type') in ['buy', 'sell', 'TRADE']
                ]
                
        except Exception as e:
            logger.debug(f"Activity extraction failed: {e}")
        
        return activities
    
    def _parse_activity_table_lxml(self, html_content: str) -> List[Dict[str, Any]]:
        """Parse activity table using lxml for better performance"""
        try:
            tree = html.fromstring(html_content)
            
            # Suche nach Activity-Rows
            # Versuche verschiedene Selektoren
            selectors = [
                "//tr[contains(@class, 'activity')]",
                "//div[contains(@class, 'activity-item')]",
                "//div[contains(@class, 'trade')]",
                "//table//tr",
            ]
            
            trades = []
            for selector in selectors:
                rows = tree.xpath(selector)
                if rows:
                    logger.debug(f"Found {len(rows)} rows with selector: {selector}")
                    for row in rows[:50]:  # Limit processing
                        trade = self._parse_activity_row_lxml(row)
                        if trade:
                            trades.append(trade)
                    if trades:
                        break
            
            return trades
            
        except Exception as e:
            logger.debug(f"LXML parsing failed: {e}")
            return []
    
    def _parse_activity_table_bs4(self, html_content: str) -> List[Dict[str, Any]]:
        """Fallback: Parse using BeautifulSoup"""
        try:
            # Nur Activity-relevante Elemente parsen für Performance
            strainer = SoupStrainer(['tr', 'div'], class_=lambda x: x and any(
                term in x.lower() for term in ['activity', 'trade', 'transaction']
            ))
            soup = BeautifulSoup(html_content, 'lxml', parse_only=strainer)
            
            trades = []
            rows = soup.find_all(['tr', 'div'])
            
            for row in rows[:50]:  # Limit processing
                trade = self._parse_activity_row_bs4(row)
                if trade:
                    trades.append(trade)
            
            return trades
            
        except Exception as e:
            logger.debug(f"BeautifulSoup parsing failed: {e}")
            return []
    
    def _parse_activity_item(self, activity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a single activity item from Next.js data"""
        try:
            # Basis-Validierung
            if not isinstance(activity, dict):
                return None
            
            # Trade-Typ check
            activity_type = activity.get('type', '').lower()
            if activity_type not in ['buy', 'sell', 'trade']:
                return None
            
            # Extrahiere Trade-Details
            trade_id = (
                activity.get('id') or 
                activity.get('transactionHash') or 
                activity.get('activityId') or
                f"activity_{int(time.time())}_{hash(str(activity))}"
            )
            
            # Market Info
            market = activity.get('market', {})
            market_slug = market.get('slug', '')
            market_id = market.get('id', '') or market.get('address', '')
            market_name = market.get('question', '') or market.get('name', '')
            
            # Trade Details
            side = activity.get('side', 'BUY').upper()
            if side not in ['BUY', 'SELL']:
                side = 'BUY' if activity_type == 'buy' else 'SELL'
            
            outcome = activity.get('outcome', 'YES').upper()
            if outcome not in ['YES', 'NO']:
                outcome = 'YES'
            
            # Amount (versuche verschiedene Felder)
            amount = 0
            for field in ['takerAmount', 'makerAmount', 'amount', 'size', 'quantity']:
                if field in activity and activity[field]:
                    amount = float(activity[field])
                    if amount > 1e10:  # Wei to USDC
                        amount = amount / 1e6
                    break
            
            if amount <= 0:
                return None  # Kein gültiger Trade ohne Amount
            
            # Price
            price = float(activity.get('price', 0) or activity.get('avgPrice', 0))
            
            # Timestamp
            timestamp = self._parse_timestamp(
                activity.get('timestamp') or 
                activity.get('createdAt') or
                activity.get('date')
            )
            
            # Transaction Hash
            tx_hash = activity.get('transactionHash') or activity.get('txHash')
            
            return {
                'trade_id': trade_id,
                'market_slug': market_slug,
                'market_id': market_id,
                'market_name': market_name,
                'outcome': outcome,
                'side': side,
                'amount_usdc': amount,
                'price': price,
                'timestamp': timestamp,
                'tx_hash': tx_hash,
            }
            
        except Exception as e:
            logger.debug(f"Failed to parse activity item: {e}")
            return None
    
    def _parse_activity_row_lxml(self, row) -> Optional[Dict[str, Any]]:
        """Parse a single activity row using lxml"""
        try:
            # Extrahiere Text aus Zellen
            cells = row.xpath('.//td | .//div[contains(@class, "cell")]')
            if len(cells) < 4:
                return None
            
            # Trade Typ (BUY/SELL)
            side_text = cells[0].text_content().strip().upper()
            if 'BUY' in side_text:
                side = 'BUY'
            elif 'SELL' in side_text:
                side = 'SELL'
            else:
                return None
            
            # Markt Name
            market_name = cells[1].text_content().strip()
            
            # Outcome (YES/NO)
            outcome_text = cells[2].text_content().strip().upper()
            outcome = 'YES' if 'YES' in outcome_text else 'NO'
            
            # Amount
            amount_text = cells[3].text_content().strip()
            amount = self._parse_amount(amount_text)
            if amount <= 0:
                return None
            
            # Generiere Trade ID
            trade_id = f"html_{int(time.time())}_{hash(str(row))}"
            
            return {
                'trade_id': trade_id,
                'market_slug': '',
                'market_id': '',
                'market_name': market_name,
                'outcome': outcome,
                'side': side,
                'amount_usdc': amount,
                'price': 0.0,
                'timestamp': datetime.now(),
                'tx_hash': None,
            }
            
        except Exception as e:
            logger.debug(f"Failed to parse lxml row: {e}")
            return None
    
    def _parse_activity_row_bs4(self, row) -> Optional[Dict[str, Any]]:
        """Parse a single activity row using BeautifulSoup"""
        try:
            cells = row.find_all(['td', 'div'])
            if len(cells) < 4:
                return None
            
            # Ähnliche Logik wie lxml version
            side_text = cells[0].get_text(strip=True).upper()
            if 'BUY' in side_text:
                side = 'BUY'
            elif 'SELL' in side_text:
                side = 'SELL'
            else:
                return None
            
            market_name = cells[1].get_text(strip=True)
            outcome_text = cells[2].get_text(strip=True).upper()
            outcome = 'YES' if 'YES' in outcome_text else 'NO'
            
            amount_text = cells[3].get_text(strip=True)
            amount = self._parse_amount(amount_text)
            if amount <= 0:
                return None
            
            trade_id = f"html_{int(time.time())}_{hash(str(row))}"
            
            return {
                'trade_id': trade_id,
                'market_slug': '',
                'market_id': '',
                'market_name': market_name,
                'outcome': outcome,
                'side': side,
                'amount_usdc': amount,
                'price': 0.0,
                'timestamp': datetime.now(),
                'tx_hash': None,
            }
            
        except Exception as e:
            logger.debug(f"Failed to parse bs4 row: {e}")
            return None
    
    def _parse_amount(self, amount_text: str) -> float:
        """Parse amount from text (e.g., '$1,234.56' or '1234 USDC')"""
        import re
        
        try:
            # Entferne $ und USDC Währungssymbole
            clean_text = re.sub(r'[\$,]|USDC|USD', '', amount_text, flags=re.IGNORECASE)
            
            # Finde Zahl mit optionalen Tausender-Trennern
            match = re.search(r'[\d,]+\.?\d*', clean_text)
            if match:
                amount_str = match.group(0).replace(',', '')
                return float(amount_str)
            
        except Exception as e:
            logger.debug(f"Failed to parse amount '{amount_text}': {e}")
        
        return 0.0
    
    def _parse_timestamp(self, timestamp_val) -> datetime:
        """Parse timestamp from various formats"""
        if not timestamp_val:
            return datetime.now()
        
        try:
            if isinstance(timestamp_val, str):
                # ISO format
                if 'T' in timestamp_val:
                    if timestamp_val.endswith('Z'):
                        timestamp_val = timestamp_val[:-1] + '+00:00'
                    return datetime.fromisoformat(timestamp_val)
                
                # Unix timestamp als String
                if timestamp_val.isdigit():
                    ts = int(timestamp_val)
                    if ts > 1e12:  # Milliseconds
                        ts = ts / 1000
                    return datetime.fromtimestamp(ts)
            
            # Unix timestamp als Zahl
            elif isinstance(timestamp_val, (int, float)):
                if timestamp_val > 1e12:  # Milliseconds
                    timestamp_val = timestamp_val / 1000
                return datetime.fromtimestamp(timestamp_val)
                
        except Exception as e:
            logger.debug(f"Failed to parse timestamp '{timestamp_val}': {e}")
        
        return datetime.now()
    
    def _process_trades(self, trades_data: List[Dict[str, Any]]) -> int:
        """
        Verarbeite die gescrapten Trades und speichere neue in der DB
        
        Args:
            trades_data: List von Trade-Dictionaries
            
        Returns:
            Anzahl der neuen Trades
        """
        new_trades_count = 0
        
        with self.db.get_session() as session:
            for trade_data in trades_data:
                # Prüfe ob Trade bereits existiert
                existing = session.query(Trade).filter(
                    Trade.source_trade_id == trade_data['trade_id']
                ).first()
                
                if existing:
                    logger.debug(f"Trade {trade_data['trade_id']} already exists, skipping")
                    continue
                
                # Erstelle neuen Trade
                trade = Trade(
                    source_trade_id=trade_data['trade_id'],
                    trader_address=self.target_username,  # Für jetzt hardcoded
                    market_slug=trade_data['market_slug'],
                    market_id=trade_data['market_id'],
                    market_name=trade_data['market_name'],
                    outcome=trade_data['outcome'],
                    side=trade_data['side'],
                    amount_usdc=trade_data['amount_usdc'],
                    price=trade_data['price'],
                    timestamp=trade_data['timestamp'],
                    tx_hash=trade_data['tx_hash'],
                )
                
                session.add(trade)
                new_trades_count += 1
                
                logger.debug(f"Added new trade: {trade}")
        
        return new_trades_count
    
    def _save_scraping_log(self, stats: Dict[str, Any]):
        """Speichere Log-Eintrag für den Scraping-Run"""
        try:
            with self.db.get_session() as session:
                log_entry = ScrapingLog(
                    success=stats['success'],
                    trades_found=stats['trades_found'],
                    new_trades=stats['new_trades'],
                    error_message=stats['error_message'],
                    duration_seconds=stats['duration_seconds'],
                )
                session.add(log_entry)
                
        except Exception as e:
            logger.error(f"Failed to save scraping log: {e}")
    
    def get_recent_trades(self, limit: int = 20) -> List[Trade]:
        """
        Hole die letzten Trades aus der Datenbank
        
        Args:
            limit: Maximale Anzahl zu retournierender Trades
            
        Returns:
            List von Trade-Objekten
        """
        with self.db.get_session() as session:
            return session.query(Trade).order_by(
                Trade.timestamp.desc()
            ).limit(limit).all()
    
    def get_uncopied_trades(self, limit: int = 20) -> List[Trade]:
        """
        Hole Trades die noch nicht kopiert wurden
        
        Args:
            limit: Maximale Anzahl
            
        Returns:
            List von Trade-Objekten
        """
        with self.db.get_session() as session:
            return session.query(Trade).filter(
                Trade.copied == False
            ).order_by(Trade.timestamp.desc()).limit(limit).all()
    
    def mark_trade_copied(self, trade_id: str, our_trade_id: str = None, 
                         status: str = 'executed'):
        """
        Markiere einen Trade als kopiert
        
        Args:
            trade_id: Source Trade ID
            our_trade_id: Unsere Trade ID (optional)
            status: Status des kopierten Trades
        """
        with self.db.get_session() as session:
            trade = session.query(Trade).filter(
                Trade.source_trade_id == trade_id
            ).first()
            
            if trade:
                trade.copied = True
                trade.copied_at = datetime.now()
                trade.our_trade_id = our_trade_id
                trade.our_trade_status = status
                
                logger.info(f"Marked trade {trade_id} as copied")
