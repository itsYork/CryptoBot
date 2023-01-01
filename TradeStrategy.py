import csv

class TradeStrategy:
    def __init__(self, investment_amount, range_percent):
        self.investment_amount = investment_amount
        self.range_percent = range_percent

    def determine_best_grid_params(self):
        """Determines the best grid size and investment amount based on the investment amount and range to trade in.

        Returns:
            A tuple containing the grid size (int) and investment amount per grid (float).
        """
        range_percent = self.range_percent
        # Calculate the grid size based on the range to trade in
        grid_size = int(1 / range_percent)

        # Calculate the investment amount per grid
        investment_per_grid = self.investment_amount / grid_size

        return grid_size, investment_per_grid

    def divide_investment(self, crypto_prices):
        """Divides an investment amount among a list of cryptocurrencies.

        Args: crypto_prices (list): A list of tuples containing the names (str) and prices (float) of the
        cryptocurrencies to invest in.

        Returns:
            A list of investment amounts (float) for each cryptocurrency.
        """
        # Calculate the weight of each cryptocurrency
        total_price = sum(price for _, price in crypto_prices)
        weights = [price / total_price for _, price in crypto_prices]

        # Calculate the allocation for each cryptocurrency
        allocations = [weight * self.investment_amount for weight in weights]

        return allocations

    def create_orders_for_range(self, range_percent, grid_params, price, side):
        """Creates a list of orders for a given range, grid size, and investment amount.

        Args:
            range_percent (float): The range to trade in.
            grid_params (tuple): A tuple containing the grid size (int) and investment amount per grid (float).
            price (float): The current price of the cryptocurrency.
            side (str): The side of the orders ("buy" or "sell").

        Returns:
            A list of orders (list). Each order is a dictionary with keys "side" (str), "price" (float), and "size" (float).
        """
        grid_size, investment_per_grid = grid_params
        orders = []
        for i in range(1, grid_size + 1):
            # Calculate the price for the current order
            if side == "buy":
                order_price = price - range_percent * price * i / grid_size
            else:
                order_price = price + range_percent * price * i / grid_size
            # Create the order
            order = {
                "side": side,
                "price": order_price,
                "size": investment_per_grid / order_price
            }
            orders.append(order)
        return orders

    def save_orders_to_csv(self, orders, filename):
        """Saves a list of orders to a CSV file.

        Args:
            orders (list): A list of orders. Each order is a dictionary with keys "side" ((str), "price" (float), and "size" (float).
            filename (str): The name of the CSV file to save the orders to.
        """
        # Open the CSV file in write mode
        with open(filename, "w", newline="") as csv_file:
            # Create a CSV writer
            writer = csv.DictWriter(csv_file, fieldnames=["side", "price", "size"])
            # Write the headers
            writer.writeheader()
            # Write the orders
            writer.writerows(orders)

# Example usage
investment_amount = 3000
range_percent = 0.01
ts = TradeStrategy(investment_amount, range_percent)
crypto_prices = [('BTC', 16000), ('ETH', 1200), ('XRP', 0.34)]
allocations = ts.divide_investment(crypto_prices)

# Example usage (continued)
for (crypto, price), allocation in zip(crypto_prices, allocations):
    grid_params = ts.determine_best_grid_params()
    if grid_params == (0, 0):
        # Investment amount is not high enough, skip creating orders
        continue
    # Set the range to trade in (e.g. 10% for a 10% range)
    range_percent = 0.1
    buy_orders = ts.create_orders_for_range(range_percent, grid_params, price, "buy")
    sell_orders = ts.create_orders_for_range(range_percent, grid_params, price, "sell")
    print(f'{crypto}:')
    print("Buy orders:")
    print(buy_orders)
    print("Sell orders:")
    print(sell_orders)

    # Save the orders to a CSV file
    ts.save_orders_to_csv(buy_orders, f"{crypto}_buy_orders.csv")
    ts.save_orders_to_csv(sell_orders, f"{crypto}_sell_orders.csv")
