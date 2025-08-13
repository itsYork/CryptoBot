import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from utils.grid import symmetric_grid


def test_symmetric_grid():
    grid = symmetric_grid(anchor=100, step=10, levels=2)
    assert grid == [80, 90, 100, 110, 120]
