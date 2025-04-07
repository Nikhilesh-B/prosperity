from typing import Dict, List
from datamodel import OrderDepth, TradingState, Order

LIMIT_RAINFOREST_RESIN = 50
LIMIT_KELP = 50

class Trader:
    def run(self, state: TradingState) -> Dict[str, List[Order]]:
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
            else:
                limit = 0

            # Retrieve the Order Depth containing all the market BUY and SELL orders
            order_depth: OrderDepth = state.order_depths[product]

            # Initialize the list of Orders to be sent as an empty list
            orders: list[Order] = []

            expected_price = self.calculate_expected_price(order_depth)


            current_position = state.position[product]

            # If statement checks if there are any SELL orders in the market
            if order_depth.sell_orders:
                # Sort all the available sell orders by their price,
                # and select only the sell order with the lowest price
                sorted_sell_orders_prices = sorted(order_depth.sell_orders.keys(), reverse=True)
                for sell_order_price in sorted_sell_orders_prices:
                    #volume when selling is negative
                    volume = order_depth.sell_orders[sell_order_price]
                    if sell_order_price < expected_price and current_position + volume >= -limit:
                        print("BUY", str(-volume) + "x", sell_order_price)
                        orders.append(Order(product, sell_order_price, -volume))
                        
            
            # The below code block is similar to the one above,
            # the difference is that it find the highest bid (buy order)
            # If the price of the order is higher than the fair value
            # This is an opportunity to sell at a premium
            if order_depth.buy_orders:
                sorted_buy_orders_prices = sorted(order_depth.buy_orders.keys())

                for buy_order_price in sorted_buy_orders_prices:
                    volume = order_depth.buy_orders[buy_order_price]
                    #volume when buying is positive
                    if buy_order_price > expected_price and current_position + volume <= limit:
                        print("SELL", str(volume) + "x", buy_order_price)
                        orders.append(Order(product, buy_order_price, volume))


            # Add all the above the orders to the result dict
            result[product] = orders

        # String value holding Trader state data required. It will be delivered as TradingState.traderData on next execution.
        traderData = "SAMPLE"

        conversions = 1

        # Return the dict of orders
        # These possibly contain buy or sell orders
        # Depending on the logic above

        return result, conversions, traderData

    def calculate_expected_price(self, order_depth: OrderDepth) -> float:
        buy_orders = order_depth.buy_orders
        sell_orders = order_depth.sell_orders

        sum = 0
        count = 0

        for price, volume in buy_orders.items():
            sum += price * abs(volume)
            count += abs(volume)

        if count == 0:
            return 0

        return sum / count
