from collections import defaultdict

class AdaptivePredictor:
    """
    Online throughput estimator.
    Predicts: seconds = bytes / bytes_per_second
    """

    def __init__(self, alpha=0.25):
        # Smoothing factor - kitna purana data ko weight dena hai
        self.alpha = alpha
        # Default throughput: 20 MB/s se start karte hain
        self.rate_bps = 20 * 1024 * 1024
        # Har file type ke liye alag rate store karte hain
        self.type_rate = defaultdict(lambda: self.rate_bps)

    def predict(self, chunk_size: int, suffix: str, sample=None) -> float:
        """
        Predict encryption time based purely on current throughput estimate.
        """
        # File type ke aadhaar par current rate nikalo
        rate = self.type_rate[suffix]
        # Time = size / speed se calculate karo
        return chunk_size / max(1.0, rate)

    def observe(self, chunk_size: int, suffix: str, actual_s: float, sample=None):
        """
        Update throughput using exponential smoothing.
        """
        # Actual rate = bytes / seconds
        observed_rate = chunk_size / max(1e-6, actual_s)
        # Purana rate nikalo
        current_rate = self.type_rate[suffix]
        # Exponential smoothing se naya rate calculate karo: 75% purana + 25% naya
        self.type_rate[suffix] = (1 - self.alpha) * current_rate + self.alpha * observed_rate
