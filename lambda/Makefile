.PHONY: build invoke-local test-mock test-local deploy clean

# Build the Lambda container image
build:
	cp -r ../vision_llm ./vision_llm
	sam build --debug
	rm -rf ./vision_llm

# Run Lambda locally with SAM (requires Docker)
invoke-local: build
	sam local invoke ProcessImageFunction -e events/test_unwarp.json

invoke-local-analyze: build
	sam local invoke ProcessImageFunction -e events/test_with_analysis.json

# Test with mocked S3 (no Docker, no AWS needed)
test-mock:
	python test_local.py --mock

# Test validation/error handling
test-validate:
	python test_local.py --validate

# Test with a local fisheye image file
test-file:
	@echo "Usage: make test-file FILE=/path/to/fisheye.jpg"
	@test -n "$(FILE)" || (echo "ERROR: FILE not specified" && exit 1)
	python test_local.py --local-file $(FILE)

# Invoke deployed Lambda remotely
run-remote:
	@echo "Usage: make run-remote URI=s3://bucket/image.jpg [ARGS='--views N']"
	@test -n "$(URI)" || (echo "ERROR: URI not specified" && exit 1)
	python cli.py $(URI) $(ARGS)

# Deploy to AWS
deploy: build
	sam deploy --resolve-image-repos

deploy-yes: build
	sam deploy --resolve-image-repos --no-confirm-changeset

deploy-guided: build
	sam deploy --guided --resolve-image-repos

# Clean build artifacts
clean:
	rm -rf .aws-sam ./vision_llm __pycache__ */__pycache__

# Show help
help:
	@echo "Available targets:"
	@echo "  build                - Build the Lambda package"
	@echo "  invoke-local         - Run Lambda locally with SAM (Docker required)"
	@echo "  invoke-local-analyze - Run with LLM analysis via SAM"
	@echo "  test-mock            - Test with mocked S3 (no AWS/Docker needed)"
	@echo "  test-validate        - Test error handling"
	@echo "  test-file FILE=x     - Test with a local image file"
	@echo "  run-remote URI=...   - Invoke deployed Lambda"
	@echo "  deploy               - Deploy to AWS"
	@echo "  deploy-yes           - Deploy without confirmation prompt"
	@echo "  deploy-guided        - Interactive deployment"
	@echo "  clean                - Remove build artifacts"
