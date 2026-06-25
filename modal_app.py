import base64
import os
import re
from pathlib import Path
from typing import Any

import modal


APP_NAME = "skyrimnet-xtts"
CACHE_VOLUME_NAME = "skyrimnet-xtts-cache"
CACHE_PATH = Path("/cache")
GPU_TYPE = os.environ.get("XTTS_MODAL_GPU", "L4")


cache_volume = modal.Volume.from_name(CACHE_VOLUME_NAME, create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "build-essential",
        "espeak-ng",
        "ffmpeg",
        "git",
        "libsndfile1",
        "portaudio19-dev",
        "python3-dev",
    )
    .pip_install_from_requirements("requirements.txt")
    .run_commands(
        "python -m pip install --no-deps "
        "git+https://github.com/art-from-the-machine/xtts-api-server-mantella.git"
    )
)

app = modal.App(APP_NAME)


def _safe_name(value: str, fallback: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return value or fallback


def _configure_xtts_environment() -> None:
    os.environ.setdefault("DEVICE", "cuda")
    os.environ.setdefault("MODEL_SOURCE", "local")
    os.environ.setdefault("MODEL_VERSION", "v2.0.2")
    os.environ.setdefault("LOWVRAM_MODE", "false")
    os.environ.setdefault("DEEPSPEED", "false")
    os.environ.setdefault("USE_CACHE", "true")
    os.environ.setdefault("OUTPUT", str(CACHE_PATH / "output"))
    os.environ.setdefault("MODEL", str(CACHE_PATH / "xtts_models"))
    os.environ.setdefault("SPEAKER", str(CACHE_PATH / "speakers"))
    os.environ.setdefault("LATENT_SPEAKER", str(CACHE_PATH / "latent_speaker_folder"))


def _decode_audio_payload(value: str) -> bytes:
    if "," in value and value.strip().lower().startswith("data:"):
        value = value.split(",", 1)[1]
    return base64.b64decode(value)


async def _read_latent_request(request: Any, xtts: Any) -> tuple[str, str, str | list[str] | None]:
    content_type = request.headers.get("content-type", "")
    language = "ru"
    speaker_name = "speaker"
    speaker_wav: str | list[str] | None = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        language = str(form.get("language") or form.get("lang") or language).lower()
        speaker_name = str(
            form.get("speaker_name")
            or form.get("speaker")
            or form.get("voice_id")
            or form.get("name")
            or speaker_name
        )
        upload = None
        for key in ("speaker_wav", "speaker_file", "audio", "file", "wav"):
            candidate = form.get(key)
            if hasattr(candidate, "filename") and hasattr(candidate, "read"):
                upload = candidate
                break
        if upload is not None:
            clean_speaker = _safe_name(speaker_name, "speaker")
            clean_file = _safe_name(upload.filename or f"{clean_speaker}.wav", f"{clean_speaker}.wav")
            dest_dir = Path(xtts.speaker_folder) / language / clean_speaker
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / clean_file
            dest_path.write_bytes(await upload.read())
            speaker_wav = str(dest_path)
            speaker_name = clean_speaker
    elif "application/json" in content_type:
        payload = await request.json()
        language = str(payload.get("language") or payload.get("lang") or language).lower()
        speaker_name = str(
            payload.get("speaker_name")
            or payload.get("speaker")
            or payload.get("voice_id")
            or payload.get("name")
            or speaker_name
        )
        speaker_wav = (
            payload.get("speaker_wav")
            or payload.get("speaker_path")
            or payload.get("wav_path")
            or payload.get("path")
        )
        audio_b64 = payload.get("audio_base64") or payload.get("wav_base64") or payload.get("audio")
        if audio_b64 and isinstance(audio_b64, str):
            clean_speaker = _safe_name(speaker_name, "speaker")
            dest_dir = Path(xtts.speaker_folder) / language / clean_speaker
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / f"{clean_speaker}.wav"
            dest_path.write_bytes(_decode_audio_payload(audio_b64))
            speaker_wav = str(dest_path)
            speaker_name = clean_speaker
    else:
        query = request.query_params
        language = str(query.get("language") or query.get("lang") or language).lower()
        speaker_name = str(
            query.get("speaker_name")
            or query.get("speaker")
            or query.get("voice_id")
            or query.get("name")
            or speaker_name
        )
        body = await request.body()
        if body:
            clean_speaker = _safe_name(speaker_name, "speaker")
            dest_dir = Path(xtts.speaker_folder) / language / clean_speaker
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / f"{clean_speaker}.wav"
            dest_path.write_bytes(body)
            speaker_wav = str(dest_path)
            speaker_name = clean_speaker

    speaker_name = _safe_name(speaker_name, "speaker")
    return speaker_name, language, speaker_wav


def _install_extra_routes(api: Any, xtts_server: Any) -> None:
    if getattr(api.state, "skyrimnet_modal_routes_installed", False):
        return

    from fastapi import HTTPException, Request

    @api.get("/ping")
    async def ping() -> str:
        return "ok"

    @api.get("/health")
    async def health() -> dict[str, Any]:
        xtts = xtts_server.XTTS
        return {
            "status": "healthy",
            "model_loaded": hasattr(xtts, "model"),
            "device": getattr(xtts, "device", None),
            "model_version": getattr(xtts, "model_version", None),
            "latents_loaded": len(getattr(xtts, "latents_cache", {})),
            "cache_volume": CACHE_VOLUME_NAME,
        }

    @api.post("/create_and_store_latents")
    @api.post("/create_and_store_latents/")
    async def create_and_store_latents(request: Request) -> dict[str, Any]:
        xtts = xtts_server.XTTS
        speaker_name, language, speaker_wav = await _read_latent_request(request, xtts)
        language = language[:2].lower()
        latent_path = Path(xtts.latent_speaker_folder) / language / f"{speaker_name}.json"

        if speaker_wav is None:
            if latent_path.exists():
                return {
                    "status": "ok",
                    "speaker": speaker_name,
                    "language": language,
                    "latent_path": str(latent_path),
                    "created": False,
                }
            try:
                speaker_wav = xtts.get_speaker_wav(speaker_name, language)
            except Exception as exc:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "No speaker audio was provided and no existing speaker was found "
                        f"for '{speaker_name}' in language '{language}': {exc}"
                    ),
                ) from exc

        xtts.get_or_create_latents(speaker_name, speaker_wav, language)
        cache_volume.commit()
        return {
            "status": "ok",
            "speaker": speaker_name,
            "language": language,
            "latent_path": str(latent_path),
            "created": True,
        }

    api.state.skyrimnet_modal_routes_installed = True


@app.function(
    image=image,
    gpu=GPU_TYPE,
    timeout=1800,
    scaledown_window=300,
    max_containers=1,
    volumes={CACHE_PATH: cache_volume},
)
@modal.asgi_app()
def web():
    _configure_xtts_environment()

    for folder in ("output", "xtts_models", "speakers", "latent_speaker_folder"):
        (CACHE_PATH / folder).mkdir(parents=True, exist_ok=True)

    from xtts_api_server import server as xtts_server

    _install_extra_routes(xtts_server.app, xtts_server)
    return xtts_server.app
