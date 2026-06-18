"""Evaluation helpers for detector performance."""


def evaluate_detector(model, X_test, y_test):
    """Return placeholder evaluation metrics."""
    predictions = model.predict(X_test)
    return {
        "accuracy": None,
        "predictions": predictions.tolist(),
        "true_labels": y_test.tolist(),
    }
