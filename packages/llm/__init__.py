"""LLM router package — MiMo primary, Gemini fallback.

Exports:
    LLMRouter — main entry, .chat() and .vision()
    LLMCallMeta — observability dataclass
    OCRResult — Pydantic model for receipt OCR
    build_router — factory wired to env settings
"""

from packages.llm.router import LLMCallMeta, LLMRouter
from packages.llm.prompts.receipt_ocr import OCRResult, RECEIPT_OCR_PROMPT
from packages.llm.factory import build_router

__all__ = [
    "LLMRouter",
    "LLMCallMeta",
    "OCRResult",
    "RECEIPT_OCR_PROMPT",
    "build_router",
]
