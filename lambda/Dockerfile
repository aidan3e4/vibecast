FROM public.ecr.aws/lambda/python:3.12

# Install system dependencies for OpenCV
RUN dnf install -y \
    mesa-libGL \
    libXext \
    libSM \
    libXrender \
    && dnf clean all

# Copy requirements and install Python dependencies
COPY lambda/requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Copy application code
COPY lambda/handler.py lambda/processor.py lambda/config.py lambda/s3_utils.py ${LAMBDA_TASK_ROOT}/
COPY vision_llm/ ${LAMBDA_TASK_ROOT}/vision_llm/

# Set the handler
CMD ["handler.lambda_handler"]
