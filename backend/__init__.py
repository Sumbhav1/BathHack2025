from .backend_service import BackendService
from .audio_manager import AudioManager
from .feature_processor import FeatureProcessor

# This makes BackendService directly importable from the backend package
# e.g., from backend import BackendService

__all__ = [
    'BackendService',
    'AudioManager',
    'FeatureProcessor'
]