# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Vibecast is an AWS Lambda service that processes fisheye camera images. It unwarps fisheye images into 5 cardinal perspective views (North, South, East, West, Below) and optionally analyzes them with vision LLMs.

## Commands

```bash
# Install dependencies (uses uv)
uv sync --dev

# Lint
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
ruff check .

# Run all tests
pytest

# Run a single test file
pytest tests/test_rotate.py

# Run a single test by name
pytest tests/test_rotate.py::test_rotate_image_90

# Build package
python -m build

# Build and deploy Lambda (requires AWS SAM CLI)
sam build
sam deploy

# Run handler locally (requires env vars set)
python vibecast/handler.py s3://bucket/image.jpg --unwarp --analyze
python vibecast/handler.py s3://bucket/image.jpg --rotate --rotation-angle 15

# Invoke deployed Lambda via CLI
python vibecast/cli.py s3://vibecast-ftp/path/image.jpg --views N S E
```

## Architecture

### Data Flow

1. **Input**: An S3 URI pointing to a fisheye JPEG is passed to the Lambda handler
2. **Fisheye unwarping** (`vibecast/fisheye.py`): Converts the circular fisheye image into 5 rectilinear views using OpenCV remap with equidistant projection math. Views: North/South/East/West (1080×810) and Below (1080×1080 center crop)
3. **LLM analysis** (`vibecast/llm.py`): Sends base64-encoded views to a vision LLM via the `llm-inference` library (a private git dependency). Returns parsed JSON or raw string
4. **Results**: Unwarped images and analysis results are uploaded to S3; a summary JSON is also stored

### Module Responsibilities

- **`handler.py`**: Lambda entry point. Routes requests to `process_image`, `models_handler`, or `prompts_handler`. Also has a `s3_trigger_handler` for S3-event-triggered processing. API keys are loaded from AWS Secrets Manager at cold-start **before** any litellm imports — this ordering is critical
- **`processor.py`**: Orchestrates the 4 processing modes (unwarp-only, analyze-only, unwarp+analyze, rotate). The async `process_image_async` is the core; `process_image` is a sync wrapper
- **`fisheye.py`**: Pure image math — equidistant fisheye projection to perspective views using numpy/OpenCV
- **`llm.py`**: Wraps `llm_inference.llm.inference.llm_turn` for multi-provider vision inference. Strips markdown code fences from responses before JSON parsing
- **`models.py`**: Registry of supported models (OpenAI, Anthropic, Google, Novita) as `ModelInfo` dataclasses
- **`prompts.py`**: Versioned prompt storage. Prompts are `prompt_{name}_{version}.txt` files in S3 (or `vibecast/prompts/` locally as fallback). S3 takes precedence
- **`s3_utils.py`**: Thin boto3 wrappers for image/JSON download and upload. Images are always numpy RGB arrays internally; BGR conversion for OpenCV happens here
- **`config.py`**: `Config` class reads required env vars (`INPUT_BUCKET`, `OUTPUT_BUCKET`, `RESULTS_BUCKET`). API keys are fetched lazily from Secrets Manager via `_get_api_key()`

### Key Design Decisions

- **View shortcuts**: `N/S/E/W/B` expand to `North/South/East/West/Below` in `Config.VIEW_SHORTCUTS`
- **`llm-inference` dependency**: This is a private git package (`git+https://github.com/aidan3e4/llm-inference.git@main`) — not on PyPI. It wraps litellm
- **API key loading order in `handler.py`**: Secrets Manager keys are injected into `os.environ` at module import time before litellm (which reads env vars directly at import) is loaded via `vibecast` imports
- **Prompts bucket**: Falls back to `RESULTS_BUCKET` if `PROMPTS_BUCKET` is not set
- **Deployment**: Container image Lambda (Dockerfile uses `public.ecr.aws/lambda/python:3.12`). SAM template is `template.yaml`; default function name is `vibecast-process-image`

### Required Environment Variables (Lambda)

| Variable | Purpose |
|---|---|
| `INPUT_BUCKET` | Source bucket for fisheye images |
| `OUTPUT_BUCKET` | Destination for unwarped views |
| `RESULTS_BUCKET` | Destination for JSON results and prompts |
| `OPENAI_API_KEY` or `OPENAI_SECRET_NAME` | LLM credentials |
| `ANTHROPIC_API_KEY` or `ANTHROPIC_SECRET_NAME` | Optional |
| `GOOGLE_API_KEY` or `GOOGLE_SECRET_NAME` | Optional |
| `NOVITA_API_KEY` or `NOVITA_SECRET_NAME` | Optional |

### Tests

Tests are in `tests/` and use `pytest-asyncio` with `asyncio_mode = "auto"` (no `@pytest.mark.asyncio` needed). S3 operations are mocked with `unittest.mock.patch` targeting `vibecast.processor.*`. Test fixtures (images) live in `tests/fixtures/`.
