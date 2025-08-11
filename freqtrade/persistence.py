from dataclasses import dataclass

@dataclass
class Trade:
    stake_amount: float = 0.0
    nr_of_successful_entries: int = 0
