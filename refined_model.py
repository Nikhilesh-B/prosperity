from typing import Dict, List, Tuple, Any
from datamodel import OrderDepth, TradingState, Order, Listing, Observation, ProsperityEncoder, Symbol, Trade
import jsonpickle

LIMIT_RAINFOREST_RESIN = 50
LIMIT_KELP = 50
LIMIT_SQUID_INK = 50


class PRODUCTS:
    RAINFOREST_RESIN = "RAINFOREST_RESIN"
    KELP = "KELP"
    SQUID_INK = "SQUID_INK"


PARAMS = {
    PRODUCTS.RAINFOREST_RESIN: {
    },
    PRODUCTS.KELP: {
    },
    PRODUCTS.SQUID_INK: {
    },
}


class PurchaseHistory:
    def __init__(self) -> None:
        self.purchases: Dict[str, Dict[int, int]] = {}

    def add_purchase(self, product: str, price: int, quantity: int) -> None:
        if product not in self.purchases:
            self.purchases[product] = {}

        if price not in self.purchases[product]:
            self.purchases[product][price] = quantity
        else:
            self.purchases[product][price] += quantity

    def remove_purchases(self, product: str, og_purchase_price: int, quantity: int) -> None:
        if product not in self.purchases:
            raise ValueError('product not in purchase history')

        if og_purchase_price not in self.purchases[product]:
            raise ValueError('purchase price not found in history')

        if self.purchases[product][og_purchase_price] < quantity:
            raise ValueError('not enough quantity at that price to remove')

        self.purchases[product][og_purchase_price] -= quantity

        if self.purchases[product][og_purchase_price] == 0:
            del self.purchases[product][og_purchase_price]

        if not self.purchases[product]:
            del self.purchases[product]


class TraderDataObject:
    def __init__(self) -> None:
        self.purchase_history = PurchaseHistory()
        # Add other history fields here as needed

    def to_json_string(self):
        return jsonpickle.encode(self)

    @classmethod
    def from_json_string(cls, json_string):
        if not json_string:
            return cls()
        return jsonpickle.decode(json_string)


class Trader:
    def __init__(self):
        self.LIMITS = {
            PRODUCTS.RAINFOREST_RESIN: LIMIT_RAINFOREST_RESIN,
            PRODUCTS.KELP: LIMIT_KELP,
            PRODUCTS.SQUID_INK: LIMIT_SQUID_INK,
        }

    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], int, str]:
        """
        Only method required. It takes all buy and sell orders for all symbols as an input,
        and outputs a list of orders to be sent
        """
        if state.traderData:
            traderDataObject = TraderDataObject.from_json_string(state.traderData)
        else:
            traderDataObject = TraderDataObject()

        # Iterate over all the keys (the available products) contained in the order dephts
        result: Dict[str, List[Order]] = {}

        purchase_history = traderDataObject.purchase_history

        for product, order_depth in state.order_depths.items():
            if product == PRODUCTS.RAINFOREST_RESIN:
                orders = self.trade_rainforest_resin(state, order_depth)
                result[product] = orders
            else:
                orders = self.trade_other_products(
                    state, order_depth, product, purchase_history)
                result[product] = orders

        # No conversions in this example
        conversions = 0

        traderDataObject.purchase_history = purchase_history
        traderData = traderDataObject.to_json_string()
        logger.flush(state, result, conversions, traderData)
        return result, conversions, traderData

    def trade_rainforest_resin(self, state: TradingState, order_depth: OrderDepth) -> List[Order]:
        current_position = state.position.get(PRODUCTS.RAINFOREST_RESIN, 0)
        limit = self.LIMITS[PRODUCTS.RAINFOREST_RESIN]

        # We need both buy_orders and sell_orders to determine a mid-price
        if not order_depth.buy_orders or not order_depth.sell_orders:
            return []

        buys_sorted = sorted(list(order_depth.buy_orders.keys()))
        sells_sorted = sorted(
            list(order_depth.sell_orders.keys()), reverse=True)

        our_buy_price = 9999
        our_sell_price = 10001

        orders = []

        for sell_order_price in sells_sorted:
            volume = order_depth.sell_orders[sell_order_price]
            # volume is negative
            if sell_order_price <= our_buy_price and current_position - volume <= limit:
                logger.print("BUY", str(-volume) + "x", sell_order_price)
                orders.append(Order(PRODUCTS.RAINFOREST_RESIN,
                              sell_order_price, -volume))

        for buy_order_price in buys_sorted:
            volume = order_depth.buy_orders[buy_order_price]
            # volume is positive
            if buy_order_price >= our_sell_price and current_position - volume >= -limit:
                logger.print("SELL", str(volume) + "x", buy_order_price)
                orders.append(Order(PRODUCTS.RAINFOREST_RESIN,
                              buy_order_price, -volume))

        return orders

    def trade_other_products(self, state: TradingState, order_depth: OrderDepth, product: str, purchase_history: PurchaseHistory) -> List[Order]:
        current_position = state.position.get(product, 0)
        limit = self.LIMITS[product]

        # We need both buy_orders and sell_orders to determine a mid-price
        if not order_depth.buy_orders or not order_depth.sell_orders:
            return []

        buy_orders_sorted = sorted(list(order_depth.buy_orders.keys()))
        sell_orders_sorted = sorted(list(order_depth.sell_orders.keys()))

        expected_price = self.calculate_expected_price(order_depth=order_depth)
        orders = []

        # Buy orders
        for sell_order_price in sell_orders_sorted:
            volume = order_depth.sell_orders[sell_order_price]
            if sell_order_price < expected_price and current_position - volume <= limit:
                logger.print("BUY", str(-volume) + "x", sell_order_price)
                purchase_history.add_purchase(
                    product=product, price=sell_order_price, quantity=-volume)
                orders.append(Order(product, sell_order_price, -volume))

        # Sell orders
        if product in purchase_history.purchases:
            orders.extend(self.process_sell_orders(
                product, order_depth, purchase_history, current_position))

        return orders

    def process_sell_orders(self, product: str, order_depth: OrderDepth, purchase_history: PurchaseHistory, current_position: int) -> List[Order]:
        orders = []
        purchase_prices = sorted(purchase_history.purchases[product].keys())
        buy_prices = sorted(list(order_depth.buy_orders.keys()))
        limit = self.LIMITS[product]

        available_position = current_position
        i = 0  # Purchase price index
        j = 0  # Buy order price index

        while i < len(purchase_prices) and j < len(buy_prices):
            purchase_price = purchase_prices[i]
            buy_price = buy_prices[j]

            if buy_price > purchase_price:
                purchase_qty = purchase_history.purchases[product][purchase_price]
                buy_qty = order_depth.buy_orders[buy_price]
                sell_qty = min(purchase_qty, buy_qty)

                if available_position - sell_qty >= -limit:
                    logger.print("SELL", f"{sell_qty}x", buy_price)
                    orders.append(Order(product, buy_price, -sell_qty))

                    purchase_history.remove_purchases(
                        product=product,
                        og_purchase_price=purchase_price,
                        quantity=sell_qty
                    )
                    available_position -= sell_qty
                    order_depth.buy_orders[buy_price] -= sell_qty

                    if order_depth.buy_orders[buy_price] == 0:
                        j += 1

                    if product not in purchase_history.purchases:
                        break

                    if purchase_price not in purchase_history.purchases[product]:
                        i += 1

                    if product in purchase_history.purchases and purchase_price in purchase_history.purchases[product] and purchase_history.purchases[product][purchase_price] == 0:
                        i += 1
                else:
                    break
            else:
                j += 1

        return orders

    def mid_price(self, order_depth: OrderDepth) -> float:
        buy_orders = order_depth.buy_orders
        sell_orders = order_depth.sell_orders

        return (max(buy_orders.keys()) + min(sell_orders.keys())) / 2

    def weighted_price(self, order_depth: OrderDepth) -> float:
        buy_orders = order_depth.buy_orders
        sell_orders = order_depth.sell_orders

        best_buy = max(buy_orders.keys())
        best_sell = min(sell_orders.keys())

        best_buy_volume = buy_orders[best_buy]
        best_sell_volume = abs(sell_orders[best_sell])

        Wa = best_buy_volume / (best_buy_volume + best_sell_volume)
        Wb = best_sell_volume / (best_buy_volume + best_sell_volume)

        return Wa * best_sell + Wb * best_buy

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
