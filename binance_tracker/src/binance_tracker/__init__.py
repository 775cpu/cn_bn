from .config import Settings

__all__ = ["BinanceTracker", "Settings"]


def __getattr__(name: str):
	if name == "BinanceTracker":
		from .service import BinanceTracker
		return BinanceTracker
	raise AttributeError(name)
