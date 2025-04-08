from typing import Dict, List, Tuple, Any
from src.model.datamodel import OrderDepth, TradingState, Order, Listing, Observation, ProsperityEncoder, Symbol, Trade
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
        for product in state.order_depths.keys():
            if product == "RAINFOREST_RESIN":
                limit = LIMIT_RAINFOREST_RESIN
            elif product == "KELP":
                limit = LIMIT_KELP
            elif product == "SQUID_INK":
                limit = LIMIT_SQUID_INK
            else:
                limit = 0

            # Retrieve the Order Depth containing all the market BUY and SELL orders
            order_depth: OrderDepth = state.order_depths[product]

            # Initialize the list of Orders to be sent as an empty list
            orders: list[Order] = []

            expected_price = self.calculate_expected_price(order_depth)

            # Check if product exists in position dictionary
            current_position = state.position.get(product, 0)

            logger.print("EXPECTED PRICE", expected_price)

            if order_depth.sell_orders:
                sorted_sell_orders_prices = sorted(
                    order_depth.sell_orders.keys())
                for sell_order_price in sorted_sell_orders_prices:
                    # volume when selling is negative
                    volume = order_depth.sell_orders[sell_order_price]
                    if sell_order_price < expected_price and current_position + volume <= limit:
                        logger.print("BUY", str(volume) +
                                     "x", sell_order_price)
                        orders.append(
                            Order(product, sell_order_price, -volume))

            if order_depth.buy_orders:
                sorted_buy_orders_prices = sorted(
                    order_depth.buy_orders.keys(), reverse=True)

                for buy_order_price in sorted_buy_orders_prices:
                    volume = order_depth.buy_orders[buy_order_price]
                    # volume when buying is positive
                    if buy_order_price > expected_price and current_position + volume >= -limit:
                        logger.print("SELL", str(-volume) +
                                     "x", buy_order_price)
                        orders.append(Order(product, buy_order_price, volume))

            # Add all the above the orders to the result dict
            result[product] = orders

        # String value holding Trader state data required. It will be delivered as TradingState.traderData on next execution.
        traderData = "SAMPLE"

        conversions = 0

        # Return the dict of orders
        # These possibly contain buy or sell orders
        # Depending on the logic above

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
