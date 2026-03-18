from dataclasses import dataclass


@dataclass
class MatchCandidate:
    hsn8: str
    description: str
    category: str
    rate: str
    match_type: str
    score: float
    reason: str
