"""Local speech-to-text with Whisper (open source, MIT) via faster-whisper. No API, no cost, audio stays on the box."""
import logging
import threading

from ...config import settings

log = logging.getLogger("aracare.scribe.asr")
_model = None
_lock = threading.Lock()
_warned = False

# Biasing the decoder toward local clinical vocabulary noticeably helps accented speech.
MEDICAL_PROMPT = ("Nigerian hospital consultation. Malaria, typhoid, hypertension, Amlodipine, Artemether-Lumefantrine, "
                  "Coartem, Lonart, Paracetamol, Amoxicillin, Augmentin, Ciprofloxacin, Metformin, Lisinopril, "
                  "FBC, RDT, Widal, SpO2, blood pressure, penicillin allergy.")


def engine_name() -> str:
    if settings.asr_engine == "none":
        return "none"
    try:
        import faster_whisper  # noqa: F401
        return f"faster-whisper:{settings.whisper_model}"
    except Exception as e:  # not installed, or installed but broken (e.g. ctranslate2.dll missing on Windows)
        global _warned
        if not isinstance(e, ImportError) and not _warned:
            log.warning("faster-whisper is installed but cannot load (%s); dictation falls back to typing", e)
            _warned = True
        return "none"


def available() -> bool:
    return engine_name() != "none"


def _load():
    global _model
    with _lock:
        if _model is None:
            from faster_whisper import WhisperModel
            log.info("Loading Whisper model %s (first run downloads the weights)", settings.whisper_model)
            _model = WhisperModel(settings.whisper_model, device=settings.whisper_device,
                                  compute_type=settings.whisper_compute)
    return _model


def warm() -> None:
    """Load the model ahead of the first dictation (downloads the weights on a fresh box)."""
    if available():
        _load()


def transcribe(path: str, language: str | None = "en") -> str:
    model = _load()
    segments, _info = model.transcribe(path, language=language, vad_filter=True, beam_size=settings.whisper_beam_size,
                                       initial_prompt=MEDICAL_PROMPT, condition_on_previous_text=False)
    return " ".join(s.text.strip() for s in segments).strip()
