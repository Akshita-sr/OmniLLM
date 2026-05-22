"""HRI module — task classifier, language detector, and the streamlined
``process_interaction`` pipeline that drives Pepper."""

from omnillm.hri.classifier import HRITaskClassifier, HRITaskType
from omnillm.hri.language_detector import LanguageDetector
from omnillm.hri.pipeline import process_interaction

__all__ = [
    "HRITaskClassifier",
    "HRITaskType",
    "LanguageDetector",
    "process_interaction",
]
