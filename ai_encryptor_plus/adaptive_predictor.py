import psutil
from collections import defaultdict

class AdaptivePredictor:
    """
    Online throughput estimator.
    Predicts: seconds = bytes / bytes_per_second
    """

    def __init__(self, alpha=0.25):
        # Smoothing factor - kitna purana data ko weight dena hai
        self.alpha = alpha
        # Dynamic initial rate based on system resources
        self.rate_bps = self._estimate_initial_rate()
        # Har file type ke liye alag rate store karte hain
        self.type_rate = defaultdict(lambda: self.rate_bps)

    def _estimate_initial_rate(self) -> float:
        """
        Estimate initial throughput based on CPU and available memory.
        Falls back to conservative 10 MB/s if estimation fails.
        """
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            available_mem = psutil.virtual_memory().available
            # CPU efficiency factor: 0.5 to 1.0 based on load
            cpu_factor = max(0.5, 1.0 - (cpu_percent / 200.0))
            # Memory factor: estimate based on available RAM (in bytes to MB/s)
            mem_factor = min(1.0, available_mem / (2 * 1024**3))
            # Base rate adjusted by system conditions
            base_rate = 10 * 1024 * 1024  # 10 MB/s base
            return base_rate * cpu_factor * (0.8 + 0.4 * mem_factor)
        except:
            # Conservative default if system info unavailable
            return 10 * 1024 * 1024

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
