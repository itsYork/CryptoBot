import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import pandas as pd
import pandas_ta as ta
from utils.indicators import ema, adx, atr, donchian, vwap


def sample_df() -> pd.DataFrame:
    data = {
        'open': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        'high': [2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
        'low': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        'close': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        'volume': [100] * 10,
    }
    return pd.DataFrame(data)


def test_ema():
    df = sample_df()
    res = ema(df['close'], length=3)
    expected = df['close'].ewm(span=3, adjust=False).mean()
    assert abs(res.iloc[-1] - expected.iloc[-1]) < 1e-2


def test_adx():
    df = sample_df()
    res = adx(df, length=3)
    expected = ta.adx(df['high'], df['low'], df['close'], length=3)["ADX_3"]
    assert abs(res.iloc[-1] - expected.iloc[-1]) < 1e-6


def test_atr():
    df = sample_df()
    res = atr(df, length=3)
    expected = ta.atr(df['high'], df['low'], df['close'], length=3)
    assert abs(res.iloc[-1] - expected.iloc[-1]) < 1e-6


def test_donchian():
    df = sample_df()
    res = donchian(df, length=3)
    assert res['donchian_high'].iloc[-1] == 11
    assert res['donchian_low'].iloc[-1] == 7


def test_vwap():
    df = sample_df()
    res = vwap(df)
    tp = (df['high'] + df['low'] + df['close']) / 3
    expected = (tp * df['volume']).cumsum() / df['volume'].cumsum()
    assert abs(res.iloc[-1] - expected.iloc[-1]) < 1e-6
