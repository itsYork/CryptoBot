class IStrategy:
    """Minimal strategy interface placeholder."""
    timeframe: str = "1h"
    can_short: bool = False

    def __init__(self, *args, **kwargs):
        pass
