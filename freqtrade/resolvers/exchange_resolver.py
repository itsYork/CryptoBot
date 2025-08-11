class Exchange:
    def __init__(self) -> None:
        self._markets = {}

class ExchangeResolver:
    @staticmethod
    def load_exchange(config, validate: bool = True):
        return Exchange()
