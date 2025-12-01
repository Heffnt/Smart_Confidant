# Smart Confidant

An AI chatbot assistant for Magic: The Gathering, built with [Gradio](https://gradio.app) and Hugging Face models.

## Features

- Custom themed UI with Magic: The Gathering aesthetics
- Multiple HuggingFace API model options
- Chat history with custom avatars
- Configurable generation parameters (temperature, max tokens, top-p)

## Setup

### Prerequisites

1. **Docker** - Install from https://docs.docker.com/get-docker/
2. **HuggingFace Token** (for API models):
   - Go to https://huggingface.co/settings/tokens
   - Create a new token (read access is sufficient)
   - Copy `env.example` to `.env` and add your token: `HF_TOKEN=hf_...`

### Local Development

```bash
# 1. Set up environment variables:
cp env.example .env
# Edit .env and add your HuggingFace token

# 2. Install dependencies with uv
pip install uv
uv pip install -r requirements.txt

# 3. Run the application
python app.py
```

The app will be available at `http://localhost:8080`

## Cloud Deployment

Deploy to GCP Cloud Run, Azure Container Apps, or AWS App Runner with a single script:

```bash
python deploy.py
```

This script will:
1. Build the Docker image locally
2. Push to Docker Hub
3. Prompt you to select a cloud provider (GCP, Azure, or AWS)
4. Deploy using the provider's CLI

### Cloud CLI Requirements

Install the CLI for your target cloud before running `deploy.py`:

| Provider | CLI | Install Link |
|----------|-----|--------------|
| GCP | `gcloud` | https://cloud.google.com/sdk/docs/install |
| Azure | `az` | https://docs.microsoft.com/en-us/cli/azure/install-azure-cli |
| AWS | `aws` | https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html |

### Setting HF_TOKEN in Cloud

After deployment, set the `HF_TOKEN` environment variable in your cloud provider's console:

- **GCP Cloud Run**: Service details -> Edit & Deploy -> Variables & Secrets
- **Azure Container Apps**: Application -> Containers -> Environment variables
- **AWS App Runner**: Service -> Configuration -> Environment variables

## Available Models

### API Models (require HF_TOKEN)
- **meta-llama/Llama-3.2-3B-Instruct** - Default model

All chat completions are routed through the HuggingFace Inference API, so no heavy local downloads or GPU requirements are needed.

## Configuration

Key configuration variables at the top of `app.py`:
- `API_MODELS`: List of API models to use
- `DEFAULT_SYSTEM_MESSAGE`: Default system prompt

Key configuration variables at the top of `deploy.py`:
- `DOCKER_USER`: Your Docker Hub username
- `DOCKER_IMAGE`: Image name
- `SERVICE_NAME`: Cloud service name
- `REGION_*`: Deployment regions for each cloud
