class TradeStrategy:
    def __init__(self, investment_amount, range_percent):
        self.investment_amount = investment_amount
        self.range_percent = range_percent

    def determine_best_grid_params(self):
        """Determines the best grid size and investment amount based on the investment amount and range to trade in.

        Returns:
            A tuple containing the grid size and investment amount per grid.
        """
        range_percent = self.range_percent
        # Calculate the grid size based on the range to trade in
        grid_size = int(1 / range_percent)

        # Calculate the investment amount per grid
        investment_per_grid = self.investment_amount / grid_size

        return grid_size, investment_per_grid

    def divide_investment(self, crypto_prices):
        """Divides an investment amount among a list of cryptocurrencies.

        Args:
            crypto_prices: A list of tuples containing the names and prices of the cryptocurrencies to invest in.

        Returns:
            A list of investment amounts for each cryptocurrency.
        """
        # Calculate the weight of each cryptocurrency
        total_price = sum(price for _, price in crypto_prices)
        weights = [price / total_price for _, price in crypto_prices]

        # Calculate the allocation for each cryptocurrency
        allocations = [weight * self.investment_amount for weight in weights]

        return allocations

    def create_orders(self, grid_params, price, side):
        """Creates a list of orders for a given grid size and investment amount.

        Args:
            grid_params: A tuple containing the grid size and investment amount per grid.
            price: The current price of the cryptocurrency.
            side: The side of the orders ("buy" or "sell").

        Returns:
            A list of orders.
        """
        grid_size, investment_per_grid = grid_params
        orders = []
        for i in range(1, grid_size + 1):
            # Calculate the price for the current order
            if side == "buy":
                order_price = price - self.range_percent * price * i / grid_size
            else:
                order_price = price + self.range_percent * price * i / grid_size
            # Create the order
            order = {
                "side": side,
                "price": order_price,
                "size": investment_per_grid / order_price
            }
            orders.append(order)
        return orders
