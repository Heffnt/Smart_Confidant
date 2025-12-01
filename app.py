"""
Smart Confidant - A Magic: The Gathering chatbot that uses HuggingFace API models.
"""

import gradio as gr
from huggingface_hub import InferenceClient
import os
import base64
from pathlib import Path
from datetime import datetime
from threading import Lock

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ============================================================================
# Configuration
# ============================================================================

API_MODELS = ["meta-llama/Llama-3.2-3B-Instruct"]
DEFAULT_SYSTEM_MESSAGE = "You are an expert assistant for Magic: The Gathering. You're name is Smart Confidant, but people tend to call you Bob."
TITLE = "🎓🧙🏻‍♂️ Smart Confidant 🧙🏻‍♂️🎓"
MODEL_OPTIONS = list(API_MODELS)

# Debug logging
debug_logs = []
debug_lock = Lock()
MAX_LOG_LINES = 100

def log_debug(message, level="INFO"):
    """Add timestamped message to debug log."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] {message}"
    with debug_lock:
        debug_logs.append(log_entry)
        if len(debug_logs) > MAX_LOG_LINES:
            debug_logs.pop(0)
    print(log_entry)

# ============================================================================
# Assets
# ============================================================================

ASSETS_DIR = Path(__file__).parent / "assets"
ASSETS_DIR_ABSOLUTE = str(ASSETS_DIR)

# Load background image as base64 for CSS
BACKGROUND_IMAGE_PATH = ASSETS_DIR / "confidant_pattern.png"
try:
    with open(BACKGROUND_IMAGE_PATH, "rb") as f:
        BACKGROUND_DATA_URL = f"data:image/png;base64,{base64.b64encode(f.read()).decode('ascii')}"
    log_debug("Background image loaded successfully")
except Exception as e:
    log_debug(f"Error loading background image: {e}", "ERROR")
    BACKGROUND_DATA_URL = ""

# CSS for tiled background and centered title
CUSTOM_CSS = f"""
body, .gradio-container, .main, .contain {{
    background-image: url('{BACKGROUND_DATA_URL}') !important;
    background-repeat: repeat !important;
    background-attachment: fixed !important;
    background-color: transparent !important;
}}
.gradio-container {{
    background: transparent !important;
}}
h1 {{
    text-align: center !important;
}}
"""

# ============================================================================
# Chat Response Handler
# ============================================================================

def respond(message, history: list[dict], system_message, max_tokens, temperature, top_p, selected_model):
    """Handle chat responses via HuggingFace API."""
    log_debug(f"Message: '{message[:50]}...' | Model: {selected_model}")

    messages = [{"role": "system", "content": system_message}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    try:
        hf_token = os.environ.get("HF_TOKEN")
        client = InferenceClient(api_key=hf_token)
        completion = client.chat.completions.create(
            model=selected_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
        )
        response = completion.choices[0].message.content
        log_debug(f"Response received ({len(response)} chars)")
        yield response
    except Exception as e:
        log_debug(f"Error: {e}", "ERROR")
        yield f"Error: {str(e)}"

# ============================================================================
# Gradio UI
# ============================================================================

gr.set_static_paths(paths=[ASSETS_DIR_ABSOLUTE])

with gr.Blocks() as demo:
    gr.Markdown(f"# {TITLE}")

    chatbot = gr.Chatbot()

    settings_panel = gr.Accordion("Settings", open=False, render=False)

    gr.ChatInterface(
        fn=respond,
        chatbot=chatbot,
        additional_inputs=[
            gr.Textbox(value=DEFAULT_SYSTEM_MESSAGE, label="System message", render=False),
            gr.Slider(minimum=1, maximum=2048, value=512, step=1, label="Max tokens", render=False),
            gr.Slider(minimum=0.1, maximum=2.0, value=0.7, step=0.1, label="Temperature", render=False),
            gr.Slider(minimum=0.1, maximum=1.0, value=0.95, step=0.05, label="Top-p", render=False),
            gr.Radio(choices=MODEL_OPTIONS, label="Model", value=MODEL_OPTIONS[0], render=False),
        ],
        additional_inputs_accordion=settings_panel,
    )

# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    log_debug("=" * 40)
    log_debug("Smart Confidant Starting")
    log_debug(f"HF_TOKEN: {'Yes' if os.environ.get('HF_TOKEN') else 'No'}")
    log_debug("=" * 40)

    port = int(os.environ.get("PORT", 8080))
    demo.launch(
        server_name="0.0.0.0",
        server_port=port,
        allowed_paths=[ASSETS_DIR_ABSOLUTE],
        css=CUSTOM_CSS,
        theme=gr.themes.Soft(primary_hue="green"),
    )
