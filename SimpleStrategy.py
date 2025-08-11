from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame


class SimpleStrategy(IStrategy):
    """Basic EMA crossover strategy for Freqtrade."""

    timeframe = '1h'
    minimal_roi = {"0": 0.05}
    stoploss = -0.1
    trailing_stop = False

    def populate_indicators(self, df: DataFrame, metadata: dict) -> DataFrame:
        df['ema_fast'] = df['close'].ewm(span=12, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=26, adjust=False).mean()
        return df

    def populate_buy_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df.loc[(df['ema_fast'] > df['ema_slow']), 'buy'] = 1
        return df

    def populate_sell_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df.loc[(df['ema_fast'] < df['ema_slow']), 'sell'] = 1
        return df
