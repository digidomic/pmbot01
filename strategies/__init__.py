"""
Strategies Module - Trading strategies for PM Bot
"""
from .bitcoin_arbitrage import (
    BitcoinArbitrageStrategy,
    CoinbaseWebSocketClient,
    Signal,
    TradeSignal,
    create_bitcoin_arbitrage_strategy,
)

__all__ = [
    'BitcoinArbitrageStrategy',
    'CoinbaseWebSocketClient',
    'Signal',
    'TradeSignal',
    'create_bitcoin_arbitrage_strategy',
]
