from __future__ import annotations

import pandas as pd
import pandas_ta as ta


def ema(series: pd.Series, length: int) -> pd.Series:
    """Exponential moving average."""
    return ta.ema(series, length=length)


def adx(df: pd.DataFrame, length: int) -> pd.Series:
    """Average directional index."""
    adx_df = ta.adx(df['high'], df['low'], df['close'], length=length)
    return adx_df[f'ADX_{length}']


def atr(df: pd.DataFrame, length: int) -> pd.Series:
    """Average true range."""
    return ta.atr(high=df['high'], low=df['low'], close=df['close'], length=length)


def donchian(df: pd.DataFrame, length: int) -> pd.DataFrame:
    """Donchian channel high and low."""
    high = df['high'].rolling(length).max()
    low = df['low'].rolling(length).min()
    return pd.DataFrame({'donchian_high': high, 'donchian_low': low})


def vwap(df: pd.DataFrame) -> pd.Series:
    """Volume weighted average price."""
    tp = (df['high'] + df['low'] + df['close']) / 3
    return (tp * df['volume']).cumsum() / df['volume'].cumsum()


def anchored_vwap(df: pd.DataFrame, freq: str = 'W') -> pd.Series:
    """Anchored VWAP reset on a given frequency (default weekly)."""
    tp = (df['high'] + df['low'] + df['close']) / 3
    pv = tp * df['volume']
    grouped = df.groupby(pd.Grouper(freq=freq))
    return grouped.apply(lambda g: pv.loc[g.index].cumsum() / df['volume'].loc[g.index].cumsum()).droplevel(0)
