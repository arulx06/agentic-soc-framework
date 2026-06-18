"""Training skeleton for the attack detector."""

from sklearn.ensemble import RandomForestClassifier


def train_detector(X, y):
    """Train a simple RandomForestClassifier placeholder."""
    model = RandomForestClassifier(random_state=42)
    model.fit(X, y)
    return model
