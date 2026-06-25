# SkyrimNet XTTS Modal Worker

Modal deployment for a SkyrimNet-compatible XTTS HTTP endpoint.

Routes:

- `GET /ping`
- `GET /health`
- `POST /tts_to_audio/`
- `POST /create_and_store_latents`

The app runs the Mantella-compatible XTTS API server inside Modal, adds SkyrimNet health and latent routes, and stores downloaded models, generated audio, speaker samples, and latent JSON files in the Modal Volume `skyrimnet-xtts-cache`.

The upstream package has conflicting dependency metadata, so the Modal image installs runtime dependencies from `requirements.txt` and then installs the server source with `--no-deps`.

## Deploy

```powershell
$env:PYTHONIOENCODING='utf-8'
python -m modal deploy modal_app.py
```

The default GPU is `L4`. To try another GPU before deploy:

```powershell
$env:XTTS_MODAL_GPU='A10G'
python -m modal deploy modal_app.py
```

## SkyrimNet Config

Set `XTTS.yaml` to the deployed Modal base URL:

```yaml
endpoint: https://YOUR-MODAL-ENDPOINT.modal.run
language: ru
```

Keep the base URL only. Do not include `/tts_to_audio/` in the config value.

## Notes

- Do not commit API keys or private voice assets.
- First cold start downloads XTTS model files into the Modal Volume.
- Put reusable speaker WAV files under `/cache/speakers/<language>/<speaker>/` in the Modal Volume, or let `/create_and_store_latents` store uploaded WAV data.
