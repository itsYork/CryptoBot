from freqtrade.strategy import IStrategy
from pandas import DataFrame


class SimpleStrategy(IStrategy):
    """Basic EMA crossover strategy for Freqtrade."""

    timeframe = "1h"
    process_only_new_candles = True
    startup_candle_count = 30
    minimal_roi = {"0": 0.05}
    stoploss = -0.1
    trailing_stop = False

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = dataframe["close"].ewm(span=12, adjust=False).mean()
        dataframe["ema_slow"] = dataframe["close"].ewm(span=26, adjust=False).mean()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe["ema_fast"] > dataframe["ema_slow"]), "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe["ema_fast"] < dataframe["ema_slow"]), "exit_long"] = 1
        return dataframe
