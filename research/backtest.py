import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from datamodel import Listing, Order, OrderDepth, Trade, TradingState
from submission.trader import Trader


LIMITS = {"EMERALDS": 80, "TOMATOES": 80}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Approximate local backtester for IMC Prosperity tutorial round 1.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/tutorial_round_1"),
        help="Directory containing prices_round_0_day_*.csv and trades_round_0_day_*.csv",
    )
    return parser.parse_args()


def load_prices(data_dir: Path):
    events = []
    for path in sorted(data_dir.glob("prices_round_0_day_*.csv")):
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle, delimiter=";")
            for row in reader:
                row["day"] = int(row["day"])
                row["timestamp"] = int(row["timestamp"])
                row["mid_price"] = float(row["mid_price"])
                for key, value in list(row.items()):
                    if key in {"day", "timestamp", "product", "mid_price", "profit_and_loss"}:
                        continue
                    row[key] = float(value) if value else None
                events.append(row)
    return sorted(events, key=lambda row: (row["day"], row["timestamp"], row["product"]))


def load_trades(data_dir: Path):
    trade_map = defaultdict(list)
    for path in sorted(data_dir.glob("trades_round_0_day_*.csv")):
        day = int(path.stem.split("_")[-1])
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle, delimiter=";")
            for row in reader:
                timestamp = int(row["timestamp"])
                symbol = row["symbol"]
                trade = Trade(
                    symbol=symbol,
                    price=int(float(row["price"])),
                    quantity=int(row["quantity"]),
                    buyer=row["buyer"] or None,
                    seller=row["seller"] or None,
                    timestamp=timestamp,
                )
                trade_map[(day, timestamp, symbol)].append(trade)
    return trade_map


def build_steps(events: List[dict]):
    by_step = defaultdict(dict)
    for row in events:
        by_step[(row["day"], row["timestamp"])][row["product"]] = row
    return sorted(by_step.items())


def to_order_depth(row: dict) -> OrderDepth:
    depth = OrderDepth()
    for level in (1, 2, 3):
        bid_price = row.get(f"bid_price_{level}")
        bid_volume = row.get(f"bid_volume_{level}")
        ask_price = row.get(f"ask_price_{level}")
        ask_volume = row.get(f"ask_volume_{level}")
        if bid_price is not None and bid_volume is not None:
            depth.buy_orders[int(bid_price)] = int(bid_volume)
        if ask_price is not None and ask_volume is not None:
            depth.sell_orders[int(ask_price)] = -abs(int(ask_volume))
    return depth


def execute_orders(
    product: str,
    orders: List[Order],
    current_row: dict,
    next_row: dict,
    trades_now: List[Trade],
    position: int,
    cash: int,
) -> Tuple[int, int, List[Trade]]:
    own_trades: List[Trade] = []
    remaining_bids = sorted(
        ((price, volume) for price, volume in to_order_depth(current_row).buy_orders.items()),
        reverse=True,
    )
    remaining_asks = sorted(
        ((price, -volume) for price, volume in to_order_depth(current_row).sell_orders.items())
    )
    best_bid = remaining_bids[0][0]
    best_ask = remaining_asks[0][0]
    touch_hit_volume = sum(trade.quantity for trade in trades_now if trade.price == best_bid)
    touch_lift_volume = sum(trade.quantity for trade in trades_now if trade.price == best_ask)

    for order in sorted((order for order in orders if order.quantity > 0), key=lambda order: order.price, reverse=True):
        buy_capacity = LIMITS[product] - position
        quantity_left = min(order.quantity, max(0, buy_capacity))
        if quantity_left <= 0:
            continue

        new_asks = []
        for ask_price, ask_volume in remaining_asks:
            if quantity_left <= 0 or ask_price > order.price:
                new_asks.append((ask_price, ask_volume))
                continue
            fill = min(quantity_left, ask_volume)
            if fill > 0:
                position += fill
                cash -= fill * ask_price
                quantity_left -= fill
                own_trades.append(Trade(product, ask_price, fill))
            leftover = ask_volume - fill
            if leftover > 0:
                new_asks.append((ask_price, leftover))
        remaining_asks = new_asks

        if quantity_left > 0 and order.price > best_bid and touch_hit_volume > 0:
            fill = min(quantity_left, touch_hit_volume)
            position += fill
            cash -= fill * order.price
            quantity_left -= fill
            touch_hit_volume -= fill
            own_trades.append(Trade(product, order.price, fill))

        if quantity_left > 0 and next_row is not None:
            next_best_ask = int(next_row["ask_price_1"])
            next_ask_volume = abs(int(next_row["ask_volume_1"]))
            if next_best_ask <= order.price:
                fill = min(quantity_left, next_ask_volume)
                position += fill
                cash -= fill * order.price
                own_trades.append(Trade(product, order.price, fill))

    for order in sorted((order for order in orders if order.quantity < 0), key=lambda order: order.price):
        sell_capacity = LIMITS[product] + position
        quantity_left = min(-order.quantity, max(0, sell_capacity))
        if quantity_left <= 0:
            continue

        new_bids = []
        for bid_price, bid_volume in remaining_bids:
            if quantity_left <= 0 or bid_price < order.price:
                new_bids.append((bid_price, bid_volume))
                continue
            fill = min(quantity_left, bid_volume)
            if fill > 0:
                position -= fill
                cash += fill * bid_price
                quantity_left -= fill
                own_trades.append(Trade(product, bid_price, -fill))
            leftover = bid_volume - fill
            if leftover > 0:
                new_bids.append((bid_price, leftover))
        remaining_bids = new_bids

        if quantity_left > 0 and order.price < best_ask and touch_lift_volume > 0:
            fill = min(quantity_left, touch_lift_volume)
            position -= fill
            cash += fill * order.price
            quantity_left -= fill
            touch_lift_volume -= fill
            own_trades.append(Trade(product, order.price, -fill))

        if quantity_left > 0 and next_row is not None:
            next_best_bid = int(next_row["bid_price_1"])
            next_bid_volume = abs(int(next_row["bid_volume_1"]))
            if next_best_bid >= order.price:
                fill = min(quantity_left, next_bid_volume)
                position -= fill
                cash += fill * order.price
                own_trades.append(Trade(product, order.price, -fill))

    return position, cash, own_trades


def mark_price(product: str, final_row: dict) -> int:
    if product == "EMERALDS":
        return 10000
    return int(final_row["mid_price"])


def simulate_day(day: int, day_prices: List[dict], trade_map) -> dict:
    steps = build_steps(day_prices)
    trader = Trader()

    listings = {
        "EMERALDS": Listing("EMERALDS", "EMERALDS", "XIRECS"),
        "TOMATOES": Listing("TOMATOES", "TOMATOES", "XIRECS"),
    }

    trader_data = ""
    positions = defaultdict(int)
    cash = defaultdict(int)
    own_trade_book = defaultdict(list)
    last_rows = {}

    for index, ((_, timestamp), product_rows) in enumerate(steps):
        next_rows = None
        if index + 1 < len(steps):
            next_rows = steps[index + 1][1]

        order_depths = {product: to_order_depth(row) for product, row in product_rows.items()}
        market_trades = {
            product: trade_map.get((day, timestamp, product), [])
            for product in product_rows
        }

        state = TradingState(
            traderData=trader_data,
            timestamp=timestamp,
            listings=listings,
            order_depths=order_depths,
            own_trades={product: own_trade_book.get(product, []) for product in product_rows},
            market_trades=market_trades,
            position=dict(positions),
            observations={},
        )

        orders_by_product, _, trader_data = trader.run(state)
        own_trade_book = defaultdict(list)

        for product, row in product_rows.items():
            next_row = next_rows.get(product) if next_rows else None
            positions[product], cash[product], own_trades = execute_orders(
                product=product,
                orders=orders_by_product.get(product, []),
                current_row=row,
                next_row=next_row,
                trades_now=market_trades.get(product, []),
                position=positions[product],
                cash=cash[product],
            )
            own_trade_book[product] = own_trades
            last_rows[product] = row

    day_summary = {"products": {}, "total": 0.0}
    for product in LIMITS:
        final_row = last_rows[product]
        pnl = cash[product] + positions[product] * mark_price(product, final_row)
        day_summary["products"][product] = {
            "cash": cash[product],
            "position": positions[product],
            "pnl": pnl,
        }
        day_summary["total"] += pnl

    day_summary["traderData"] = json.loads(trader_data) if trader_data else {}
    return day_summary


def main():
    args = parse_args()
    prices = load_prices(args.data_dir)
    trade_map = load_trades(args.data_dir)

    by_day_prices = defaultdict(list)
    for row in prices:
        by_day_prices[row["day"]].append(row)

    summary = {"by_day": {}, "by_product": defaultdict(float)}
    total_pnl = 0.0
    for day in sorted(by_day_prices):
        day_summary = simulate_day(day, by_day_prices[day], trade_map)
        summary["by_day"][day] = day_summary
        total_pnl += day_summary["total"]
        for product, product_summary in day_summary["products"].items():
            summary["by_product"][product] += product_summary["pnl"]

    summary["by_product"] = dict(summary["by_product"])
    summary["total"] = total_pnl
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"Approx total PnL: {total_pnl:.2f}")


if __name__ == "__main__":
    main()
