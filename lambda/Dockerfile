FROM public.ecr.aws/lambda/python:3.12

# Install system dependencies for OpenCV
RUN dnf install -y \
    mesa-libGL \
    libXext \
    libSM \
    libXrender \
    git \
    && dnf clean all

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files and source code
COPY pyproject.toml uv.lock README.md ${LAMBDA_TASK_ROOT}/
COPY vision_llm/ ${LAMBDA_TASK_ROOT}/vision_llm/

# Install dependencies using uv
RUN uv pip install --system --no-cache ${LAMBDA_TASK_ROOT}

# Copy lambda handler code
COPY lambda/handler.py lambda/processor.py lambda/config.py lambda/s3_utils.py ${LAMBDA_TASK_ROOT}/

# Set the handler
CMD ["handler.lambda_handler"]
