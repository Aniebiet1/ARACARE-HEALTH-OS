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


FALLBACK_MODEL = "base"   # ~150 MB in int8: fits on a busy 8 GB laptop where "small" does not


class ASRUnavailable(RuntimeError):
    """Whisper could not be loaded or run (usually not enough free memory)."""


def _load():
    global _model
    with _lock:
        if _model is None:
            from faster_whisper import WhisperModel
            names = [settings.whisper_model]
            if settings.whisper_model not in ("tiny", "tiny.en", FALLBACK_MODEL):
                names.append(FALLBACK_MODEL)
            for i, name in enumerate(names):
                log.info("Loading Whisper model %s (first run downloads the weights)", name)
                try:
                    _model = WhisperModel(name, device=settings.whisper_device, compute_type=settings.whisper_compute)
                    break
                except (RuntimeError, MemoryError) as e:   # ctranslate2 reports out-of-memory as "mkl_malloc: failed to allocate memory"
                    if i + 1 < len(names):
                        log.warning("Whisper %s could not load (%s); falling back to %s", name, e, names[i + 1])
                    else:
                        raise ASRUnavailable(f"Whisper could not load: {e}") from e
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
