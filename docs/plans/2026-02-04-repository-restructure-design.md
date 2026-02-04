# Repository Restructure Design

**Date:** 2026-02-04
**Status:** Approved
**Context:** Lambda-only project with unnecessary library/deployment separation

## Problem

The current structure creates friction for a Lambda-only deployment:

- Makefile is in `lambda/`, requiring `cd lambda` for all operations
- Separate `vision_llm/` package suggests it's a reusable library, but it's only used in this Lambda
- `cp -r ../vision_llm` hack in Makefile to work around nested structure
- Split between root `pyproject.toml` and `lambda/` build tooling is confusing

## Solution

Flatten into a standard Python project with Lambda deployment at root.

### Target Structure

```
vibecast/                   # repo root
├── pyproject.toml          # Project config, dependencies
├── Makefile                # All build/deploy commands
├── template.yaml           # SAM template
├── samconfig.toml          # SAM deployment config
├── Dockerfile              # Lambda container build
├── README.md
├── vibecast/               # Python package (flat layout)
│   ├── __init__.py
│   ├── handler.py          # Lambda entry point
│   ├── processor.py        # Orchestration logic
│   ├── config.py           # Configuration
│   ├── s3_utils.py         # S3 operations
│   ├── fisheye.py          # Image unwarping
│   ├── llm.py              # LLM client
│   ├── models.py           # Data models
│   ├── prompts.py          # Prompt management
│   ├── utils.py            # Utilities
│   └── prompts/            # Prompt templates
│       └── *.txt
├── tests/                  # Test suite
│   ├── fixtures/
│   └── test_*.py
├── events/                 # SAM test events
│   └── *.json
├── data/                   # Local dev data
│   ├── ftp_uploads/
│   ├── unwarped/
│   └── results/
└── docs/                   # Documentation
    └── plans/
```

## Changes by File

### Dockerfile

**Before:**
```dockerfile
COPY pyproject.toml uv.lock README.md ${LAMBDA_TASK_ROOT}/
COPY vision_llm/ ${LAMBDA_TASK_ROOT}/vision_llm/
RUN uv pip install --system --no-cache ${LAMBDA_TASK_ROOT}
COPY lambda/handler.py lambda/processor.py ... ${LAMBDA_TASK_ROOT}/
CMD ["handler.lambda_handler"]
```

**After:**
```dockerfile
COPY pyproject.toml uv.lock README.md ${LAMBDA_TASK_ROOT}/
COPY vibecast/ ${LAMBDA_TASK_ROOT}/vibecast/
RUN uv pip install --system --no-cache ${LAMBDA_TASK_ROOT}
CMD ["vibecast.handler.lambda_handler"]
```

### template.yaml

**Before:**
```yaml
Metadata:
  Dockerfile: lambda/Dockerfile
  DockerContext: ..
```

**After:**
```yaml
Metadata:
  Dockerfile: Dockerfile
  DockerContext: .
```

### pyproject.toml

**Before:**
```toml
[tool.setuptools.packages.find]
include = ["vision_llm*"]
```

**After:**
```toml
[tool.setuptools.packages.find]
include = ["vibecast*"]
```

### Makefile

**Before (in lambda/):**
```makefile
build:
	cp -r ../vision_llm ./vision_llm
	sam build --debug
	rm -rf ./vision_llm

update-deps:
	cd .. && uv lock --upgrade-package llm-inference && uv sync
```

**After (at root):**
```makefile
build:
	sam build --debug

update-deps:
	uv lock --upgrade-package llm-inference && uv sync
```

## Migration Checklist

1. **Move files:**
   - `vision_llm/*.py` → `vibecast/`
   - `vision_llm/prompts/` → `vibecast/prompts/`
   - `lambda/handler.py` → `vibecast/handler.py`
   - `lambda/processor.py` → `vibecast/processor.py`
   - `lambda/config.py` → `vibecast/config.py`
   - `lambda/s3_utils.py` → `vibecast/s3_utils.py`
   - `lambda/Makefile` → `Makefile` (at root)
   - `lambda/template.yaml` → `template.yaml` (at root)
   - `lambda/samconfig.toml` → `samconfig.toml` (at root)
   - `lambda/Dockerfile` → `Dockerfile` (at root)
   - `lambda/events/` → `events/` (at root)

2. **Update imports:**
   - All `from vision_llm import ...` → `from vibecast import ...`
   - All `from vision_llm.X import Y` → `from vibecast.X import Y`
   - Test files: `tests/test_*.py` imports

3. **Update file references:**
   - `vibecast/prompts.py` - prompt file paths
   - `Dockerfile` - CMD handler path
   - `template.yaml` - Dockerfile location and context
   - `pyproject.toml` - package name
   - `.github/workflows/*` - remove any `cd lambda` commands

4. **Cleanup:**
   - Delete `lambda/` directory
   - Delete `vision_llm/` directory
   - Remove `.aws-sam/` (will rebuild)

5. **Verify:**
   - Run tests: `pytest`
   - Build locally: `make build`
   - Test local invoke: `sam local invoke ProcessImageFunction -e events/test_unwarp.json`
   - Deploy to test environment

## Benefits

1. **Simpler workflow** - Run `make build`, `make deploy` from root without `cd lambda`
2. **No file copying hacks** - Dockerfile context is `.`, copies `vibecast/` directly
3. **Standard Python layout** - Package named after project, follows conventions
4. **Clearer intent** - Structure matches purpose (Lambda deployment, not reusable library)
5. **Easier onboarding** - New contributors see standard layout, know where to find things

## Risks

None significant. This is a pure refactor with no functional changes. The main work is mechanical (moving files, updating imports).
