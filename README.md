# SkyrimNet XTTS RunPod Serverless Worker

Минимальный Docker worker для SkyrimNet XTTS.

Идея: образ не хранит модели и не переустанавливает XTTS. Он ожидает, что RunPod Network Volume уже примонтирован, а внутри него есть готовая установка:

```text
/runpod-volume/skyrimnet-tts
/runpod-volume/skyrimnet-tts/.venv/bin/python
```

В обычных Pods RunPod часто монтирует volume как `/workspace`, а в Serverless Network Volume монтируется как `/runpod-volume`. Worker умеет найти оба варианта.

## Важно

Этот вариант нужен для Serverless HTTP / Load Balancing endpoint, где SkyrimNet может обращаться к обычным HTTP endpoint:

```text
/health
/tts_to_audio
/create_and_store_latents
```

RunPod Load Balancer также проверяет `/ping`. Worker поднимает маленький proxy на `8888`: `/ping` отвечает сразу, чтобы Load Balancer не зависал во время cold start, остальные запросы проксируются в XTTS.

Если в RunPod выбран только обычный queue/job endpoint с `/run`, SkyrimNet напрямую с ним работать не сможет без отдельного адаптера.

## Сборка образа

В папке с этим проектом:

```powershell
docker build -t YOUR_DOCKERHUB_NAME/skyrimnet-xtts-worker:latest .
docker push YOUR_DOCKERHUB_NAME/skyrimnet-xtts-worker:latest
```

Замени `YOUR_DOCKERHUB_NAME` на свой Docker Hub или GHCR namespace.

## Настройка RunPod

1. Открой RunPod -> Serverless -> New Endpoint.
2. Выбери custom Docker image.
3. Docker image:

```text
YOUR_DOCKERHUB_NAME/skyrimnet-xtts-worker:latest
```

4. GPU: начни с A4000 / A4500 / RTX 4000 / A40.
5. Region / data center: `EU-RO-1`, чтобы совпадало с твоим volume.
6. Network Volume: `unique_silver_turkey_volume`.
7. Network Volume в Serverless будет доступен как `/runpod-volume`.
8. HTTP port: `8888`.
9. Environment variables:

```text
PORT=8888
PORT_HEALTH=8888
XTTS_PORT=8889
XTTS_DIR=auto
LOG_DIR=auto
```

10. Workers:

```text
Min workers: 0
Max workers: 1
```

Для игры лучше перед запуском поставить active/min workers `1`, чтобы не ждать cold start. После игры вернуть `0`, чтобы не жрало деньги.

## Проверка

После запуска endpoint открой:

```text
https://YOUR_RUNPOD_ENDPOINT/health
```

Ожидаемый ответ примерно такой:

```json
{"status":"healthy","model_loaded":true}
```

В SkyrimNet в `XTTS.yaml` указывать нужно базовый URL без `/lab`:

```yaml
endpoint: "https://YOUR_RUNPOD_ENDPOINT"
```

## Если не стартует

Смотри логи endpoint. Этот worker специально падает с понятной ошибкой, если:

- volume не примонтирован в `/runpod-volume` или `/workspace`;
- выбран не тот volume;
- внутри volume нет `skyrimnet-tts`;
- нет виртуального окружения `skyrimnet-tts/.venv/bin/python`;
- порт `8888` занят Jupyter или другим процессом.
