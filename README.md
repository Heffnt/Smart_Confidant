# 🎓🧙🏻‍♂️ Smart Confidant 🧙🏻‍♂️🎓

An AI chatbot assistant for Magic: The Gathering, built with [Gradio](https://gradio.app) and Hugging Face models.

## Features

- 🎨 Custom themed UI with Magic: The Gathering aesthetics
- 🤖 Multiple model support (local and API-based)
- 💬 Chat history with custom avatars
- ⚙️ Configurable generation parameters (temperature, max tokens, top-p)
- 📊 Resource monitoring (CPU, memory usage)

## Setup

### Local Development (Windows/Mac/Linux)

```bash
# 1. Set up environment variables (for API models):
cp env.example .env
# Edit .env and add your HuggingFace token

# 2. Create conda environment
conda env create -f environment.yml

# 3. Activate environment
conda activate smart-confidant

# 4. Install dependencies with uv
pip install uv
uv pip install -e .

# 5. Run the application
python app.py
```

The app will be available at `http://localhost:8012`

### Linux Deployment

Deploy to a remote server in one command:
```bash
# 1. Set up your HuggingFace token (for API models):
cp env.example .env
# Edit .env and add your token

# 2. Deploy:
./deploy.sh
```

This script will:
- Load HF_TOKEN from `.env` file (if present)
- Handle SSH key authentication
- Copy your code to the server
- Install micromamba
- Set up environment
- Install dependencies with uv
- Start the application
- Pass HF_TOKEN to enable API models

The app will be available at `http://your-server:8012`

**Note:** To use API models, you need a HuggingFace API token:
1. Go to https://huggingface.co/settings/tokens
2. Create a new token (read access is sufficient)
3. Copy `env.example` to `.env` and add your token: `HF_TOKEN=hf_...`
4. The `.env` file is git-ignored for security

## Available Models

### API Models (require HF_TOKEN)
- **HuggingFaceH4/zephyr-7b-beta** (7B params) - Recommended: Best quality for chat

### Local Models (run on your device)
- **arnir0/Tiny-LLM** - Very small model for testing

API models are recommended as they're free with HuggingFace's Inference API and don't require local compute resources. Start with **zephyr-7b-beta** or **gemma-2-2b-it** for best results.

## Configuration

Key configuration variables at the top of `app.py`:
- `LOCAL_MODELS`: List of local models to use
- `API_MODELS`: List of API models to use (all free with HF Inference API)
- `DEFAULT_SYSTEM_MESSAGE`: Default system prompt

## Requirements

- Conda/Mamba (for local development)
- Git Bash (for running `deploy.sh` on Windows)

Python dependencies are managed in `pyproject.toml`.
