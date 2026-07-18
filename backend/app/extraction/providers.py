import io
import os
import tempfile
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ExtractionResult:
    text: str
    confidence: float
    provider: str
    provider_version: str
    unavailable_reason: str | None = None


class OcrProvider(Protocol):
    def extract(self, content: bytes) -> ExtractionResult: ...


class TranscriptionProvider(Protocol):
    def transcribe(self, content: bytes, suffix: str) -> ExtractionResult: ...


class PaddleOcrProvider:
    """Lazy optional provider; install PaddleOCR in a dedicated worker image when enabled."""

    def extract(self, content: bytes) -> ExtractionResult:
        try:
            import numpy as np
            from paddleocr import PaddleOCR
            from PIL import Image
        except ImportError:
            return ExtractionResult("", 0.0, "PADDLE_OCR", "unavailable", "OCR_PROVIDER_NOT_INSTALLED")
        image = np.array(Image.open(io.BytesIO(content)).convert("RGB"))
        engine = PaddleOCR(use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False)
        output = engine.predict(image)
        lines: list[str] = []
        scores: list[float] = []
        for result in output:
            payload = getattr(result, "json", result)
            if isinstance(payload, dict):
                data = payload.get("res", payload)
                lines.extend(str(value) for value in data.get("rec_texts", []) if value)
                scores.extend(float(value) for value in data.get("rec_scores", []) if value is not None)
        confidence = sum(scores) / len(scores) if scores else 0.0
        return ExtractionResult("\n".join(lines), confidence, "PADDLE_OCR", "3.x")


class FasterWhisperProvider:
    """Lazy optional provider using an immediately deleted temporary file for decoder compatibility."""

    def transcribe(self, content: bytes, suffix: str) -> ExtractionResult:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            return ExtractionResult("", 0.0, "FASTER_WHISPER", "unavailable", "TRANSCRIPTION_PROVIDER_NOT_INSTALLED")
        path = ""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
                handle.write(content)
                path = handle.name
            model = WhisperModel("small", device="cpu", compute_type="int8")
            segments, info = model.transcribe(path, vad_filter=True)
            text = " ".join(segment.text.strip() for segment in segments).strip()
            confidence = max(0.0, min(1.0, 1.0 - float(getattr(info, "duration_after_vad", 0) == 0)))
            return ExtractionResult(text, confidence, "FASTER_WHISPER", "1.x")
        finally:
            if path:
                try:
                    os.remove(path)
                except OSError:
                    pass


def get_ocr_provider() -> OcrProvider:
    return PaddleOcrProvider()


def get_transcription_provider() -> TranscriptionProvider:
    return FasterWhisperProvider()
