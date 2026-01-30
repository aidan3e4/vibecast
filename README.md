# Vibecast

Process fisheye images from Reolink W520 cameras. Unwarp them into perspective views and extract insights using a Vision Language Model (OpenAI).

## Features

- **Unwarp fisheye images** into 5 perspective views (North, South, East, West, Below)
- **Analyze images** with a VLM to extract structured insights
- Deployed as an AWS Lambda with S3 integration

## Usage

The Lambda supports three modes:

### 1. Unwarp Only
Convert a fisheye image into 5 perspective views:
```bash
python lambda/handler.py s3://bucket/fisheye.jpg --unwarp
```

### 2. Analyze Only
Analyze an already unwarped image:
```bash
python lambda/handler.py s3://bucket/image.jpg --analyze
```

### 3. Unwarp + Analyze
Unwarp and analyze in one call:
```bash
python lambda/handler.py s3://bucket/fisheye.jpg --unwarp --analyze --views N S E
```

### Remote Invocation
Invoke the deployed Lambda instead of running locally:
```bash
python lambda/handler.py s3://bucket/fisheye.jpg --unwarp --analyze --remote
```

## API

```json
{
  "input_s3_uri": "s3://bucket/image.jpg",
  "unwarp": true,
  "analyze": true,
  "views_to_analyze": ["N", "S", "E", "W", "B"],
  "prompt": "Custom analysis prompt",
  "fov": 90,
  "view_angle": 45
}
```

## Deployment

See [DEPLOY.md](DEPLOY.md) for deployment instructions.

```bash
cd lambda
sam build
sam deploy
```