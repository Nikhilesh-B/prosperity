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

        # Iterate over all the keys (the available products) contained in the order dephts
        result: Dict[str, List[Order]] = {}
        for product, order_depth in state.order_depths.items():
            # Identify an absolute inventory limit for this product

            # onlt operating with Rainforest Resin right now! Keeping it to Rainforest resin;
            if product == "RAINFOREST_RESIN":
                limit = LIMIT_RAINFOREST_RESIN
                continue
            elif product == "KELP":
                limit = LIMIT_KELP
            elif product == "SQUID_INK":
                limit = LIMIT_SQUID_INK
                continue
            else:
                # If some other product appears, skip for now
                limit = 0

            current_position = state.position.get(product, 0)

            # We need both buy_orders and sell_orders to determine a mid-price
            if not order_depth.buy_orders or not order_depth.sell_orders:
                continue

            ph = PurchaseHistory.from_json_string(state.traderData)

            buy_orders_sorted = sorted(
                list(order_depth.buy_orders.keys()), reverse=True)
            sell_orders_sorted = sorted(
                list(order_depth.sell_orders.keys()))

            expected_price = self.calculate_expected_price(
                order_depth=order_depth)
            orders = []

            # you have some statistical understanding of the expected price that is changing over time
            # as that statical price changes over time we will then buy opportunistically any products that may be far below what we potentially percieve the market value
            for sell_order_price in sell_orders_sorted:
                #volume is negative as it is a sell order
                volume = order_depth.sell_orders[sell_order_price]
                if sell_order_price < expected_price and current_position - volume <= limit:
                    logger.print("BUY", str(-volume) +
                                 "x", sell_order_price)
                    ph.add_purchase(symbol=product, price=sell_order_price, quantity=-volume)
                    orders.append(
                        Order(product, sell_order_price, -volume))

            # This would be a ford fulkerson matching algorithm type approach if we didn't run these together 

            if product in ph.purchases:
                # Sort purchase history by price ascending
                purchase_prices = sorted(ph.purchases[product].keys())
                purchase_idx = 0
                buy_idx = 0

                # Two pointer approach to match purchases with current buy orders
                while purchase_idx < len(purchase_prices) and buy_idx < len(buy_orders_sorted):
                    purchase_price = purchase_prices[purchase_idx]
                    buy_price = buy_orders_sorted[buy_idx]
                    
                    # Only sell if we would make a profit
                    if buy_price > purchase_price:
                        purchase_quantity = ph.purchases[product][purchase_price]
                        buy_volume = order_depth.buy_orders[buy_price]
                        
                        # Only proceed if we have inventory to sell
                        if purchase_quantity > 0:
                            # Sell the minimum of what they want to buy and what we have
                            sell_quantity = min(buy_volume, purchase_quantity)
                            
                            if current_position - sell_quantity >= -limit:
                                logger.print("SELL", str(sell_quantity) + "x", buy_price)
                                ph.remove_purchases(product, purchase_price, sell_quantity)
                                orders.append(Order(product, buy_price, -sell_quantity))
                                
                                # Update the remaining volume for this buy order
                                order_depth.buy_orders[buy_price] -= sell_quantity
                                
                                # If buy order is fully filled, move to next one
                                if order_depth.buy_orders[buy_price] == 0:
                                    buy_idx += 1
                                # If we sold all inventory at this price, move to next purchase price    
                                if ph.purchases[product][purchase_price] == 0:
                                    purchase_idx += 1
                            else:
                                # Hit position limit, stop selling
                                break
                        else:
                            # No inventory at this price, move to next purchase price
                            purchase_idx += 1
                    else:
                        # Current buy price not profitable, move to next buy order
                        buy_idx += 1


            traderData = ph.to_json_string()
            result[product] = orders

        # No conversions in this example
        conversions = 0
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


class PurchaseHistory:
    def __init__(self) -> None:
        self.purchases: Dict[Dict[int, int]] = {}

    def add_purchase(self, symbol: str, price: int, quantity: int) -> None:
        if symbol not in self.purchases:
            self.purchases[symbol] = {}

        if price not in self.purchases[symbol]:
            self.purchases[symbol][price] = quantity
        else:
            self.purchases[symbol][price] += quantity

    def remove_purchases(self, symbol: str, og_purchase_price: int, quantity: int) -> None:
        if symbol not in self.purchases:
            raise ValueError('symbol not in purchase history')

        if og_purchase_price not in self.purchases[symbol]:
            raise ValueError('purchase price not found in history')

        if self.purchases[symbol][og_purchase_price] < quantity:
            raise ValueError('not enough quantity at that price to remove')

        self.purchases[symbol][og_purchase_price] -= quantity

        if self.purchases[symbol][og_purchase_price] == 0:
            del self.purchases[symbol][og_purchase_price]

        if not self.purchases[symbol]:
            del self.purchases[symbol]

    def to_json_string(self):
        return json.dumps({"purchases": self.purchases})

    # Create from JSON string (class method)
    @classmethod
    def from_json_string(cls, json_string):
        data = json.loads(json_string)
        ph = cls()
        ph.purchases = data.get("purchases", {})
        return ph


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
