from .adaptive_predictor import AdaptivePredictor

# Ye file ek simple cost model define karta hai.
# Purely throughput estimation ke liye AdaptivePredictor use hota hai.
class CostModel:
    """
    Clean cost model with NO ML, NO sklearn, NO model_path.
    Only adaptive throughput estimation is used.
    """

    def __init__(self):
        # Sirf adaptive predictor ka instance create kar rahe hain.
        # Koi heavy ML model nahi, seedha online observation se adjust hota hai.
        self.adaptive = AdaptivePredictor()

    def predict_seconds(self, *, chunk_size: int, suffix: str, sample=None) -> float:
        """
        Predict encryption time.
        Pure size-based adaptive model.
        """
        # Predict karne ke liye AdaptivePredictor ka predict method call karte hain.
        # chunk_size aur suffix pass karte hain; sample optional hai.
        return self.adaptive.predict(chunk_size, suffix, sample)

    def observe(self, *, chunk_size: int, suffix: str, actual_s: float, sample=None):
        """
        Update model with real observed time.
        """
        # Jab real measured time mile to is function ko call karo taaki predictor update ho jaye.
        # actual_s = observed seconds, wo adaptive predictor me bhej rahe hain.
        self.adaptive.observe(chunk_size, suffix, actual_s, sample)
