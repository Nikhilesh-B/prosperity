from typing import Dict, List, Tuple, Any
from datamodel import OrderDepth, TradingState, Order, Listing, Observation, ProsperityEncoder, Symbol, Trade
import json

LIMIT_RAINFOREST_RESIN = 50
LIMIT_KELP = 50
LIMIT_SQUID_INK = 50


class Trader:
    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], int, str]:
        """
        Only method required. It takes all buy and sell orders for all symbols as an input,
        and outputs a list of orders to be sent
        """
        # Initialize the method output dict as an empty dict
        result = {}

        # Iterate over all the keys (the available products) contained in the order dephts
        result: Dict[str, List[Order]] = {}
        for product, order_depth in state.order_depths.items():
            # Identify an absolute inventory limit for this product
            if product == "RAINFOREST_RESIN":
                limit = LIMIT_RAINFOREST_RESIN
            elif product == "KELP":
                limit = LIMIT_KELP
            elif product == "SQUID_INK":
                limit = LIMIT_SQUID_INK
            else:
                # If some other product appears, skip for now
                limit = 0

            current_position = state.position.get(product, 0)

            # We need both buy_orders and sell_orders to determine a mid-price
            if not order_depth.buy_orders or not order_depth.sell_orders:
                continue

            best_bid = max(order_depth.buy_orders.keys())   # highest buy price
            best_ask = min(order_depth.sell_orders.keys())  # lowest sell price
            if best_bid is None or best_ask is None:
                continue

            mid_price = self.calculate_expected_price(order_depth)
            logger.print(
                f"PRODUCT={product} | BEST_BID={best_bid} | BEST_ASK={best_ask} | MID={mid_price} | POS={current_position}")

            # ------------------------
            # 1) Choose a percentage-based spread
            #    e.g. 0.2% (0.002) or 0.5% (0.005), etc.
            # ------------------------
            spread_percent = 0.005   # 0.2% of the mid price
            base_spread = mid_price * spread_percent
            half_spread = base_spread / 2

            # ------------------------
            # 2) Position-based skew
            #
            # We push quotes up/down if we are long/short to reduce
            # the chance of increasing a big position. We'll scale
            # the skew by how close we are to the limit.
            # ------------------------
            # position ratio in [-1, +1]
            position_ratio = current_position / limit if limit > 0 else 0

            # Multiply by half_spread to shift quotes.
            # A positive 'position_ratio' => we're long => shift quotes downward (less buying).
            # If mid_price is large, the skew is bigger in absolute terms.
            position_skew = position_ratio * half_spread

            bid_price = mid_price - half_spread - position_skew
            ask_price = mid_price + half_spread - position_skew

            # Round bid and ask to integers
            bid_price = int(bid_price)
            ask_price = int(ask_price)

            # ------------------------
            # 3) Quote sizes
            # We'll define a base size. Then we'll ensure we don't exceed the limit
            # if we get fully filled.
            # ------------------------
            base_quote_size = 10

            # If near or at the long limit, reduce or skip bidding
            if current_position >= limit:
                bid_quantity = 0
            else:
                max_buyable = limit - current_position
                bid_quantity = min(base_quote_size, max_buyable)

            # If near or at the short limit, reduce or skip asking
            if current_position <= -limit:
                ask_quantity = 0
            else:
                # how many we can sell before hitting -limit
                max_sellable = -limit + current_position
                ask_quantity = -max(base_quote_size, max_sellable)

            # ------------------------
            # 4) Create your two-sided quotes (if size > 0)
            # ------------------------
            # BUY order (bid)
            orders = []
            if bid_quantity > 0:
                # volume is positive for a BUY
                logger.print("BUY", str(bid_quantity) + "x", bid_price)
                orders.append(Order(product, bid_price, bid_quantity))

            # SELL order (ask)
            if ask_quantity > 0:
                # volume is positive in your original code when you do SELL,
                # but we store it as negative in the Order class
                logger.print("SELL", str(ask_quantity) + "x", ask_price)
                orders.append(Order(product, ask_price, -ask_quantity))

            result[product] = orders

        # No conversions in this example
        conversions = 0
        traderData = "SAMPLE"
        logger.flush(state, result, conversions, traderData)
        return result, conversions, traderData

    def calculate_expected_price(self, order_depth: OrderDepth) -> float:
        buy_orders = order_depth.buy_orders
        sell_orders = order_depth.sell_orders

        sum = 0
        count = 0

        for price, volume in buy_orders.items():
            sum += price * abs(volume)
            count += abs(volume)

        for price, volume in sell_orders.items():
            sum += price * abs(volume)
            count += abs(volume)

        if count == 0:
            return 0

        return sum / count


class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(
            self.to_json(
                [
                    self.compress_state(state, ""),
                    self.compress_orders(orders),
                    conversions,
                    "",
                    "",
                ]
            )
        )

        # We truncate state.traderData, trader_data, and self.logs to the same max. length to fit the log limit
        max_item_length = (self.max_log_length - base_length) // 3

        print(
            self.to_json(
                [
                    self.compress_state(state, self.truncate(
                        state.traderData, max_item_length)),
                    self.compress_orders(orders),
                    conversions,
                    self.truncate(trader_data, max_item_length),
                    self.truncate(self.logs, max_item_length),
                ]
            )
        )

        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [
            state.timestamp,
            trader_data,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings: dict[Symbol, Listing]) -> list[list[Any]]:
        compressed = []
        for listing in listings.values():
            compressed.append(
                [listing.symbol, listing.product, listing.denomination])

        return compressed

    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict[Symbol, list[Any]]:
        compressed = {}
        for symbol, order_depth in order_depths.items():
            compressed[symbol] = [
                order_depth.buy_orders, order_depth.sell_orders]

        return compressed

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        compressed = []
        for arr in trades.values():
            for trade in arr:
                compressed.append(
                    [
                        trade.symbol,
                        trade.price,
                        trade.quantity,
                        trade.buyer,
                        trade.seller,
                        trade.timestamp,
                    ]
                )

        return compressed

    def compress_observations(self, observations: Observation) -> list[Any]:
        conversion_observations = {}
        for product, observation in observations.conversionObservations.items():
            conversion_observations[product] = [
                observation.bidPrice,
                observation.askPrice,
                observation.transportFees,
                observation.exportTariff,
                observation.importTariff,
                observation.sugarPrice,
                observation.sunlightIndex,
            ]

        return [observations.plainValueObservations, conversion_observations]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        compressed = []
        for arr in orders.values():
            for order in arr:
                compressed.append([order.symbol, order.price, order.quantity])

        return compressed

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        if len(value) <= max_length:
            return value

        return value[: max_length - 3] + "..."


logger = Logger()
