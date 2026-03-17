"""
CLOB Trader - Polymarket trade execution via CLOB client
"""
import json
import logging
import os
import time
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Optional, Dict, Any

# Import CLOB client
try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import ApiCreds, OrderArgs
    from py_clob_client.constants import BUY, SELL
    CLOB_AVAILABLE = True
except ImportError:
    CLOB_AVAILABLE = False
    logging.warning("py-clob-client not installed. Trading functionality will be disabled.")

from config import config
from database.db import DatabaseManager
from scraper.models import Trade

logger = logging.getLogger(__name__)


class MarketCache:
    """Cache für Polymarket Markets mit JSON-Persistenz"""
    
    def __init__(self, cache_file: str = "database/market_cache.json"):
        self.cache_file = Path(cache_file)
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self._markets: Dict[str, dict] = {}
        self._last_update: Optional[datetime] = None
        self._load_cache()
    
    def _load_cache(self):
        """Lade Cache aus Datei"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    self._markets = data.get('markets', {})
                    last_update_str = data.get('last_update')
                    if last_update_str:
                        self._last_update = datetime.fromisoformat(last_update_str)
                logger.debug(f"Loaded {len(self._markets)} markets from cache")
            except Exception as e:
                logger.warning(f"Failed to load market cache: {e}")
                self._markets = {}
    
    def _save_cache(self):
        """Speichere Cache in Datei"""
        try:
            data = {
                'markets': self._markets,
                'last_update': datetime.now().isoformat()
            }
            with open(self.cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save market cache: {e}")
    
    def get(self, market_slug: str) -> Optional[dict]:
        """Hole Market aus Cache"""
        return self._markets.get(market_slug)
    
    def set(self, market_slug: str, market_data: dict):
        """Speichere Market im Cache"""
        self._markets[market_slug] = market_data
        self._save_cache()
    
    def is_stale(self, max_age_hours: int = 24) -> bool:
        """Prüfe ob Cache veraltet ist"""
        if not self._last_update:
            return True
        age = datetime.now() - self._last_update
        return age > timedelta(hours=max_age_hours)
    
    def clear(self):
        """Lösche Cache"""
        self._markets = {}
        self._last_update = None
        if self.cache_file.exists():
            self.cache_file.unlink()


class ClobTrader:
    """Executes trades via Polymarket CLOB"""
    
    # USDC hat 6 Dezimalstellen
    USDC_DECIMALS = 1_000_000
    MIN_ORDER_SIZE = 1  # Minimum 1 USDC
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # Sekunden zwischen Retries
    
    def __init__(self, db: DatabaseManager, dry_run: bool = True):
        """
        Initialize CLOB trader
        
        Args:
            db: Database manager instance
            dry_run: If True, simulate trades without actual execution
        """
        self.db = db
        self.dry_run = dry_run
        self.client: Optional[ClobClient] = None
        self.api_creds: Optional[ApiCreds] = None
        self.initialized = False
        self.market_cache = MarketCache()
        
        # Daily spending tracking
        self.daily_spent = 0.0
        self.daily_limit = config.MAX_TRADE_AMOUNT_USDC * 5  # Default: 5x max trade
        self._load_daily_spending()
        
        if CLOB_AVAILABLE:
            self._init_client()
        else:
            logger.error("py-clob-client not available - trading disabled")
    
    def _load_daily_spending(self):
        """Lade heutiges Spending aus Datei"""
        spending_file = Path("database/daily_spending.json")
        if spending_file.exists():
            try:
                with open(spending_file, 'r') as f:
                    data = json.load(f)
                    today = datetime.now().strftime('%Y-%m-%d')
                    if data.get('date') == today:
                        self.daily_spent = data.get('spent', 0.0)
            except Exception as e:
                logger.warning(f"Failed to load daily spending: {e}")
    
    def _save_daily_spending(self):
        """Speichere heutiges Spending"""
        spending_file = Path("database/daily_spending.json")
        try:
            data = {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'spent': self.daily_spent
            }
            with open(spending_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Failed to save daily spending: {e}")
    
    def _init_client(self):
        """Initialize CLOB client with credentials"""
        try:
            # Chain ID for Polygon (Polymarket)
            chain_id = 137
            
            # Create API credentials
            self.api_creds = ApiCreds(
                api_key=config.POLYMARKET_API_KEY,
                api_secret=config.POLYMARKET_SECRET,
                api_passphrase=config.POLYMARKET_PASSPHRASE
            )
            
            # Initialize client
            self.client = ClobClient(
                host="https://clob.polymarket.com",
                chain_id=chain_id,
                creds=self.api_creds
            )
            
            # Test connection by getting API keys
            self.client.get_api_keys()
            
            self.initialized = True
            logger.info("✅ CLOB client initialized successfully")
            
            # Log dry_run status
            if self.dry_run:
                logger.info("🔧 DRY RUN MODE - No real trades will be executed")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize CLOB client: {e}")
            self.initialized = False
    
    def get_balance(self) -> dict:
        """
        Get USDC balance from CLOB
        
        Returns:
            dict with 'usdc', 'locked', 'available', 'error'
        """
        if not self.initialized:
            return {'usdc': 0, 'locked': 0, 'available': 0, 'error': 'Client not initialized'}
        
        try:
            balance = self.client.get_balance()
            
            # Parse balance response
            usdc_balance = 0
            locked_balance = 0
            
            if isinstance(balance, dict):
                usdc_balance = float(balance.get('balance', 0)) / self.USDC_DECIMALS
                locked_balance = float(balance.get('locked', 0)) / self.USDC_DECIMALS
            elif isinstance(balance, (int, float)):
                usdc_balance = float(balance) / self.USDC_DECIMALS
            
            available = usdc_balance - locked_balance
            
            # Check if balance is below threshold
            if available < config.MAX_TRADE_AMOUNT_USDC:
                logger.warning(
                    f"⚠️ Low balance: {available:.2f} USDC available, "
                    f"need {config.MAX_TRADE_AMOUNT_USDC} USDC for trades"
                )
            
            return {
                'usdc': round(usdc_balance, 6),
                'locked': round(locked_balance, 6),
                'available': round(available, 6),
                'error': None
            }
            
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return {'usdc': 0, 'locked': 0, 'available': 0, 'error': str(e)}
    
    def _refresh_market_cache(self) -> bool:
        """
        Aktualisiere Market Cache von CLOB API
        
        Returns:
            True wenn erfolgreich
        """
        if not self.initialized:
            logger.error("Cannot refresh cache - client not initialized")
            return False
        
        try:
            logger.info("🔄 Refreshing market cache from CLOB API...")
            
            # Hole alle Markets (paginiert)
            all_markets = []
            next_cursor = None
            
            for page in range(10):  # Max 10 pages
                try:
                    if next_cursor:
                        response = self.client.get_markets(next_cursor=next_cursor)
                    else:
                        response = self.client.get_markets()
                    
                    if isinstance(response, dict):
                        markets = response.get('data', [])
                        next_cursor = response.get('next_cursor')
                    else:
                        markets = response
                        next_cursor = None
                    
                    all_markets.extend(markets)
                    
                    if not next_cursor:
                        break
                        
                    time.sleep(0.1)  # Rate limiting
                    
                except Exception as e:
                    logger.error(f"Error fetching page {page}: {e}")
                    break
            
            # Cache markets by slug
            cached_count = 0
            for market in all_markets:
                slug = market.get('market_slug') or market.get('slug')
                if slug:
                    # Extrahiere wichtige Daten
                    cached_data = {
                        'condition_id': market.get('condition_id'),
                        'market_slug': slug,
                        'question': market.get('question'),
                        'tokens': market.get('tokens', []),
                        'active': market.get('active', True),
                        'closed': market.get('closed', False),
                        'cached_at': datetime.now().isoformat()
                    }
                    self.market_cache.set(slug, cached_data)
                    cached_count += 1
            
            logger.info(f"✅ Cached {cached_count} markets")
            return True
            
        except Exception as e:
            logger.error(f"Failed to refresh market cache: {e}")
            return False
    
    def validate_market(self, market_slug: str, auto_refresh: bool = True) -> Optional[dict]:
        """
        Validiere ob ein Market existiert und tradable ist
        
        Args:
            market_slug: Der Market Slug (z.B. "will-bitcoin-hit-100k")
            auto_refresh: Cache automatisch aktualisieren wenn nicht gefunden
            
        Returns:
            Market data dict oder None wenn nicht gefunden/nicht tradable
        """
        # Prüfe Cache
        market_data = self.market_cache.get(market_slug)
        
        if market_data:
            # Prüfe ob market aktiv ist
            if market_data.get('closed') or not market_data.get('active', True):
                logger.warning(f"Market {market_slug} is closed or inactive")
                return None
            return market_data
        
        # Nicht im Cache - versuche Refresh
        if auto_refresh and self.initialized:
            logger.info(f"Market {market_slug} not in cache, refreshing...")
            if self._refresh_market_cache():
                market_data = self.market_cache.get(market_slug)
                if market_data:
                    if market_data.get('closed') or not market_data.get('active', True):
                        logger.warning(f"Market {market_slug} is closed or inactive")
                        return None
                    return market_data
        
        logger.error(f"Market {market_slug} not found")
        return None
    
    def get_token_id(self, market_data: dict, outcome: str) -> Optional[str]:
        """
        Extrahiere token_id für ein bestimmtes Outcome
        
        Args:
            market_data: Market data aus Cache
            outcome: "YES", "NO" oder andere Outcome-Bezeichnung
            
        Returns:
            token_id oder None
        """
        tokens = market_data.get('tokens', [])
        
        if not tokens:
            logger.error(f"No tokens found in market data")
            return None
        
        # Normalisiere outcome
        outcome_normalized = outcome.upper().strip()
        
        for token in tokens:
            token_outcome = token.get('outcome', '').upper().strip()
            if token_outcome == outcome_normalized:
                return token.get('token_id')
        
        # Wenn nicht gefunden, versuche fuzzy matching
        for token in tokens:
            token_outcome = token.get('outcome', '').upper().strip()
            if outcome_normalized in token_outcome or token_outcome in outcome_normalized:
                return token.get('token_id')
        
        logger.error(f"Token for outcome '{outcome}' not found in market")
        return None
    
    def calculate_order_size(self, original_amount: float) -> float:
        """
        Berechne die Order-Größe basierend auf Konfiguration
        
        Returns das kleinere von:
        - Prozentsatz vom Original-Trade
        - Maximum erlaubter Betrag
        """
        # Berechne Prozentsatz
        percent_amount = original_amount * (config.TRADE_PERCENTAGE / 100)
        
        # Nimm das kleinere
        trade_amount = min(percent_amount, config.MAX_TRADE_AMOUNT_USDC)
        
        # Runde auf 2 Dezimalstellen
        trade_amount = round(trade_amount, 2)
        
        # Minimum Check
        if trade_amount < self.MIN_ORDER_SIZE:
            logger.warning(
                f"Trade amount {trade_amount} below minimum {self.MIN_ORDER_SIZE} USDC, "
                f"using minimum"
            )
            trade_amount = self.MIN_ORDER_SIZE
        
        return trade_amount
    
    def create_order(
        self,
        market_slug: str,
        outcome: str,
        side: str,
        size: float,
        price: Optional[float] = None,
        retry_count: int = 0
    ) -> tuple[bool, Optional[str], Optional[dict]]:
        """
        Erstelle und sende eine Order an das CLOB
        
        Args:
            market_slug: Market identifier
            outcome: "YES" oder "NO"
            side: "BUY" oder "SELL"
            size: Order-Größe in USDC
            price: Limit-Preis (optional, sonst Market Order)
            retry_count: Intern für Retries
            
        Returns:
            (success, error_message, result_dict)
        """
        if not self.initialized:
            return False, "CLOB client not initialized", None
        
        # Dry Run Check
        if self.dry_run:
            logger.info(
                f"🔧 [DRY RUN] Would create order: {side} {size} USDC "
                f"of {outcome} on {market_slug} @ {price or 'MARKET'}"
            )
            return True, None, {
                'dry_run': True,
                'order_id': f'dry-run-{int(time.time())}',
                'market_slug': market_slug,
                'outcome': outcome,
                'side': side,
                'size': size,
                'price': price
            }
        
        try:
            # 1. Market validieren
            market_data = self.validate_market(market_slug)
            if not market_data:
                return False, f"Market {market_slug} not found or not tradable", None
            
            condition_id = market_data.get('condition_id')
            if not condition_id:
                return False, "No condition_id in market data", None
            
            # 2. Token ID ermitteln
            token_id = self.get_token_id(market_data, outcome)
            if not token_id:
                return False, f"Token for outcome '{outcome}' not found", None
            
            # 3. Balance Check
            balance = self.get_balance()
            if balance.get('error'):
                return False, f"Balance check failed: {balance['error']}", None
            
            available = balance.get('available', 0)
            if available < size:
                return False, f"Insufficient balance: {available:.2f} USDC available, need {size:.2f}", None
            
            # 4. Daily Limit Check
            if self.daily_spent + size > self.daily_limit:
                return False, (
                    f"Daily limit exceeded: would spend {self.daily_spent + size:.2f} USDC, "
                    f"limit is {self.daily_limit:.2f} USDC"
                ), None
            
            # 5. Preis ermitteln wenn nicht angegeben
            if price is None:
                # Versuche aktuellen Marktpreis zu holen
                try:
                    orderbook = self.client.get_order_book(token_id)
                    if side.upper() == "BUY" and orderbook.bids:
                        price = float(orderbook.bids[0].price)
                    elif side.upper() == "SELL" and orderbook.asks:
                        price = float(orderbook.asks[0].price)
                    else:
                        price = 0.5  # Default fallback
                except Exception as e:
                    logger.warning(f"Could not get orderbook, using default price: {e}")
                    price = 0.5
            
            # 6. OrderArgs erstellen
            # USDC in Basis-Einheiten (6 Dezimalstellen)
            size_base = int(size * self.USDC_DECIMALS)
            
            order_args = OrderArgs(
                token_id=token_id,
                side=side.upper(),
                size=size_base,
                price=price
            )
            
            logger.info(
                f"Creating order: {side} {size} USDC of {outcome} on {market_slug} "
                f"@ {price} (token: {token_id[:20]}...)"
            )
            
            # 7. Order erstellen
            order = self.client.create_order(order_args)
            
            # 8. Order signieren
            signed_order = self.client.sign_order(order)
            
            # 9. Order senden
            result = self.client.post_order(signed_order)
            
            # 10. Ergebnis verarbeiten
            if isinstance(result, dict):
                order_id = result.get('order_id') or result.get('id')
                tx_hash = result.get('transaction_hash') or result.get('tx_hash')
                
                # Update daily spending
                self.daily_spent += size
                self._save_daily_spending()
                
                logger.info(f"✅ Order placed successfully: {order_id}")
                
                return True, None, {
                    'order_id': order_id,
                    'tx_hash': tx_hash,
                    'market_slug': market_slug,
                    'outcome': outcome,
                    'side': side,
                    'size': size,
                    'price': price,
                    'condition_id': condition_id,
                    'token_id': token_id
                }
            else:
                return False, f"Unexpected response format: {result}", None
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Order creation failed: {error_msg}")
            
            # Retry bei Netzwerk-Fehlern
            if retry_count < self.MAX_RETRIES:
                if any(err in error_msg.lower() for err in ['timeout', 'connection', 'network', 'temporarily']):
                    logger.info(f"Retrying in {self.RETRY_DELAY}s... (attempt {retry_count + 1}/{self.MAX_RETRIES})")
                    time.sleep(self.RETRY_DELAY)
                    return self.create_order(
                        market_slug, outcome, side, size, price, retry_count + 1
                    )
            
            return False, error_msg, None
    
    def execute_trade(self, trade: Trade) -> tuple[bool, Optional[str]]:
        """
        Führe einen Copy-Trade aus
        
        Args:
            trade: Trade Objekt aus der DB
            
        Returns:
            (success, error_message)
        """
        if not self.initialized:
            error = "CLOB client not initialized"
            logger.error(error)
            self._update_trade_status(trade, 'failed', error)
            return False, error
        
        try:
            logger.info(f"🚀 Executing trade: {trade.market_slug} {trade.side} {trade.outcome}")
            
            # Berechne Order-Größe
            order_size = self.calculate_order_size(trade.amount_usdc)
            
            if order_size < self.MIN_ORDER_SIZE:
                error = f"Order size too small: {order_size} USDC (min: {self.MIN_ORDER_SIZE})"
                logger.warning(error)
                self._update_trade_status(trade, 'failed', error)
                return False, error
            
            # Validiere Market vorab
            if not self.validate_market(trade.market_slug):
                error = f"Market {trade.market_slug} not available for trading"
                logger.error(error)
                self._update_trade_status(trade, 'failed', error)
                return False, error
            
            # Erstelle Order
            success, error, result = self.create_order(
                market_slug=trade.market_slug,
                outcome=trade.outcome,
                side=trade.side,
                size=order_size
            )
            
            if success:
                # Update Trade in DB
                with self.db.get_session() as session:
                    trade.copied = True
                    trade.copied_at = datetime.now()
                    trade.our_trade_id = result.get('order_id') if result else None
                    trade.our_trade_status = 'executed'
                    
                    # Speichere zusätzliche Info
                    if result:
                        trade.our_trade_error = json.dumps(result)
                    
                    session.commit()
                
                latency = (datetime.now() - trade.detected_at).total_seconds()
                logger.info(f"✅ Trade executed: {trade.source_trade_id} (latency: {latency:.2f}s)")
                
                if self.dry_run:
                    logger.info("🔧 Note: This was a DRY RUN - no real trade was executed!")
                
                return True, None
            else:
                self._update_trade_status(trade, 'failed', error)
                return False, error
                
        except Exception as e:
            error = str(e)
            logger.error(f"Trade execution failed: {error}")
            self._update_trade_status(trade, 'failed', error)
            return False, error
    
    def _update_trade_status(self, trade: Trade, status: str, error: Optional[str] = None):
        """Update Trade Status in DB"""
        try:
            with self.db.get_session() as session:
                trade.our_trade_status = status
                trade.our_trade_error = error
                if status == 'executed':
                    trade.copied = True
                    trade.copied_at = datetime.now()
                session.commit()
        except Exception as e:
            logger.error(f"Failed to update trade status: {e}")
    
    def get_trade_status(self, order_id: str) -> Optional[dict]:
        """
        Hole Status einer Order vom CLOB
        
        Args:
            order_id: Die Order ID
            
        Returns:
            Order Status dict oder None
        """
        if not self.initialized:
            return None
        
        try:
            # CLOB client hat keine direkte get_order Methode,
            # aber wir können Trades oder Order History abfragen
            # Dies ist ein Platzhalter für zukünftige Implementation
            logger.warning("get_trade_status not fully implemented yet")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get trade status: {e}")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Breche eine Order ab
        
        Args:
            order_id: Die zu cancelnde Order ID
            
        Returns:
            True wenn erfolgreich
        """
        if not self.initialized:
            return False
        
        try:
            result = self.client.cancel_order(order_id)
            logger.info(f"Order {order_id} cancelled: {result}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    def set_daily_limit(self, limit_usdc: float):
        """Setze tägliches Spending-Limit"""
        self.daily_limit = limit_usdc
        logger.info(f"Daily spending limit set to {limit_usdc} USDC")
    
    def get_stats(self) -> dict:
        """Hole Trader Statistiken"""
        balance = self.get_balance()
        
        return {
            'initialized': self.initialized,
            'dry_run': self.dry_run,
            'balance': balance,
            'daily_spent': self.daily_spent,
            'daily_limit': self.daily_limit,
            'markets_cached': len(self.market_cache._markets),
            'cache_stale': self.market_cache.is_stale()
        }


# Factory function für einfache Nutzung
def create_trader(db: DatabaseManager, dry_run: bool = True) -> ClobTrader:
    """
    Factory function zum Erstellen eines ClobTraders
    
    Args:
        db: DatabaseManager instance
        dry_run: True für Test-Modus ohne echte Trades
        
    Returns:
        ClobTrader instance
    """
    return ClobTrader(db, dry_run=dry_run)
