"""Trust score manager placeholder."""


class TrustManager:
    def __init__(self, score=100):
        self.score = score

    def reward(self, amount=1):
        self.score += amount
        return self.score

    def penalize(self, amount=5):
        self.score -= amount
        return self.score
