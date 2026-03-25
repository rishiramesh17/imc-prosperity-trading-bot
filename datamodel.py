from dataclasses import dataclass, field
from typing import Dict, List, Optional


Symbol = str
Product = str
Position = int
UserId = str


@dataclass
class Listing:
    symbol: Symbol
    product: Product
    denomination: str


@dataclass
class Order:
    symbol: Symbol
    price: int
    quantity: int


@dataclass
class OrderDepth:
    buy_orders: Dict[int, int] = field(default_factory=dict)
    sell_orders: Dict[int, int] = field(default_factory=dict)


@dataclass
class Trade:
    symbol: Symbol
    price: int
    quantity: int
    buyer: Optional[UserId] = None
    seller: Optional[UserId] = None
    timestamp: int = 0


@dataclass
class TradingState:
    traderData: str
    timestamp: int
    listings: Dict[Symbol, Listing]
    order_depths: Dict[Symbol, OrderDepth]
    own_trades: Dict[Symbol, List[Trade]]
    market_trades: Dict[Symbol, List[Trade]]
    position: Dict[Product, Position]
    observations: dict
