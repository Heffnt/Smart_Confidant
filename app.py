"""
Smart Confidant - A Magic: The Gathering chatbot with support for local and API-based LLMs.
Supports both local transformers models and HuggingFace API models with custom theming.
"""

import gradio as gr
from gradio.themes.base import Base
from huggingface_hub import InferenceClient
import os
import base64
from pathlib import Path
import traceback
from datetime import datetime
from threading import Lock

# ============================================================================
# Configuration
# ============================================================================

LOCAL_MODELS = ["arnir0/Tiny-LLM"]
API_MODELS = ["google/gemma-2-2b-it", "HuggingFaceH4/zephyr-7b-beta"]
DEFAULT_SYSTEM_MESSAGE = "You are an expert assistant for Magic: The Gathering. You're name is Smart Confidant, but people tend to call you Bob."
TITLE = "🎓🧙🏻‍♂️ Smart Confidant 🧙🏻‍♂️🎓"

# Create labeled model options for the radio selector
MODEL_OPTIONS = []
for model in LOCAL_MODELS:
    MODEL_OPTIONS.append(f"{model} (local)")
for model in API_MODELS:
    MODEL_OPTIONS.append(f"{model} (api)")

# Global state for local model pipeline (cached across requests)
pipe = None
stop_inference = False

# Debug logging setup with thread-safe access
debug_logs = []
debug_lock = Lock()
MAX_LOG_LINES = 100

# ============================================================================
# Debug Logging Functions
# ============================================================================

def log_debug(message, level="INFO"):
    """Add timestamped message to debug log (thread-safe, rotating buffer)."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] {message}"
    with debug_lock:
        debug_logs.append(log_entry)
        if len(debug_logs) > MAX_LOG_LINES:
            debug_logs.pop(0)
    print(log_entry)
    return "\n".join(debug_logs)

def get_debug_logs():
    """Retrieve all debug logs as a single string."""
    with debug_lock:
        return "\n".join(debug_logs)

# ============================================================================
# Asset Loading & Theme Configuration
# ============================================================================

# Load background image as base64 data URL for CSS injection
ASSETS_DIR = Path(__file__).parent / "assets"
BACKGROUND_IMAGE_PATH = ASSETS_DIR / "confidant_pattern.png"
try:
    with open(BACKGROUND_IMAGE_PATH, "rb") as _img_f:
        _encoded_img = base64.b64encode(_img_f.read()).decode("ascii")
        BACKGROUND_DATA_URL = f"data:image/png;base64,{_encoded_img}"
    log_debug("Background image loaded successfully")
except Exception as e:
    log_debug(f"Error loading background image: {e}", "ERROR")
    BACKGROUND_DATA_URL = ""

class TransparentTheme(Base):
    """Custom Gradio theme with transparent body background to show tiled image."""
    def __init__(self):
        super().__init__()
        super().set(
            body_background_fill="*neutral_950",
            body_background_fill_dark="*neutral_950",
        )

# Custom CSS for dark theme with tiled background image
# Uses aggressive selectors to override Gradio's default styling
fancy_css = f"""
    /* Tiled background image on page body */
    body {{
        background-image: url('{BACKGROUND_DATA_URL}') !important;
        background-repeat: repeat !important;
        background-size: auto !important;
        background-attachment: fixed !important;
        background-color: #1a1a1a !important;
    }}
    
    /* Make Gradio wrapper divs transparent to show background */
    gradio-app,
    .gradio-container,
    .gradio-container > div,
    .gradio-container > div > div,
    .main,
    .contain,
    [class*="svelte"] > div,
    div[class*="wrap"]:not(.gr-button):not([class*="input"]):not([class*="textbox"]):not([class*="bubble"]):not([class*="message"]),
    div[class*="container"]:not([class*="input"]):not([class*="button"]) {{
        background: transparent !important;
        background-color: transparent !important;
        background-image: none !important;
    }}
    
    /* Center and constrain main container */
    .gradio-container {{
        max-width: 700px !important;
        margin: 0 auto !important;
        padding: 20px !important;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1) !important;
        border-radius: 10px !important;
        font-family: 'Arial', sans-serif !important;
    }}
    
    /* Green title banner */
    #title {{
        text-align: center !important;
        font-size: 2em !important;
        margin-bottom: 20px !important;
        color: #ffffff !important;
        background-color: #4CAF50 !important;
        padding: 20px !important;
        border-radius: 10px !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3) !important;
    }}
    
    /* Dark grey backgrounds for chatbot and settings components */
    .block.svelte-12cmxck {{
        background-color: rgba(60, 60, 60, 0.95) !important;
        border-radius: 10px !important;
    }}
    
    div[class*="bubble-wrap"],
    div[class*="message-wrap"] {{
        background-color: rgba(60, 60, 60, 0.95) !important;
        border-radius: 10px !important;
        padding: 15px !important;
    }}
    
    .label-wrap,
    div[class*="accordion"] {{
        background-color: rgba(60, 60, 60, 0.95) !important;
        border-radius: 10px !important;
    }}
    
    /* White text for readability on dark backgrounds */
    .block.svelte-12cmxck,
    .block.svelte-12cmxck *,
    div[class*="bubble-wrap"] *,
    div[class*="message-wrap"] *,
    .label-wrap,
    .label-wrap * {{
        color: #ffffff !important;
    }}
    
    /* Green buttons with hover effect */
    .gr-button,
    button {{
        background-color: #4CAF50 !important;
        background-image: none !important;
        color: white !important;
        border: none !important;
        border-radius: 5px !important;
        padding: 10px 20px !important;
        cursor: pointer !important;
        transition: background-color 0.3s ease !important;
    }}
    .gr-button:hover,
    button:hover {{
        background-color: #45a049 !important;
    }}
    .gr-slider input {{
        color: #4CAF50 !important;
    }}
    """

# ============================================================================
# Chat Response Handler
# ============================================================================

def respond(
    message,
    history: list[dict[str, str]],
    system_message,
    max_tokens,
    temperature,
    top_p,
    selected_model: str,
):
    """
    Handle chat responses using either local transformers models or HuggingFace API.
    
    Args:
        message: User's input message
        history: List of previous messages in conversation
        system_message: System prompt to guide model behavior
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature (higher = more random)
        top_p: Nucleus sampling threshold
        selected_model: Model identifier with "(local)" or "(api)" suffix
    
    Yields:
        str: Generated response text or error message
    """
    global pipe
    
    try:
        log_debug(f"New message received: '{message[:50]}...'")
        log_debug(f"Selected model: {selected_model}")
        log_debug(f"Parameters - max_tokens: {max_tokens}, temp: {temperature}, top_p: {top_p}")

        # Build complete message history with system prompt
        messages = [{"role": "system", "content": system_message}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        log_debug(f"Message history length: {len(messages)}")

        # Parse model type and name from selection
        is_local = selected_model.endswith("(local)")
        model_name = selected_model.replace(" (local)", "").replace(" (api)", "")
        
        response = ""

        if is_local:
            # ===== LOCAL MODEL PATH =====
            log_debug(f"Using LOCAL mode with model: {model_name}")
            try:
                from transformers import pipeline
                import torch
                log_debug("Transformers imported successfully")
                
                # Load or reuse cached pipeline
                if pipe is None or pipe.model.name_or_path != model_name:
                    log_debug(f"Loading model pipeline for: {model_name}")
                    pipe = pipeline("text-generation", model=model_name)
                    log_debug("Model pipeline loaded successfully")
                else:
                    log_debug("Using cached model pipeline")

                # Format conversation as plain text prompt
                prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
                log_debug(f"Prompt length: {len(prompt)} characters")

                # Run inference
                log_debug("Starting inference...")
                outputs = pipe(
                    prompt,
                    max_new_tokens=max_tokens,
                    do_sample=True,
                    temperature=temperature,
                    top_p=top_p,
                )
                log_debug("Inference completed")

                # Extract new tokens only (strip original prompt)
                response = outputs[0]["generated_text"][len(prompt):]
                log_debug(f"Response length: {len(response)} characters")
                yield response.strip()

            except ImportError as e:
                error_msg = f"Import error: {str(e)}"
                log_debug(error_msg, "ERROR")
                log_debug(traceback.format_exc(), "ERROR")
                yield f"❌ Import Error: {str(e)}\n\nPlease check log.txt for details."
            except Exception as e:
                error_msg = f"Local model error: {str(e)}"
                log_debug(error_msg, "ERROR")
                log_debug(traceback.format_exc(), "ERROR")
                yield f"❌ Local Model Error: {str(e)}\n\nPlease check log.txt for details."

        else:
            # ===== API MODEL PATH =====
            log_debug(f"Using API mode with model: {model_name}")
            
            try:
                # Check for HuggingFace API token
                hf_token = os.environ.get("HF_TOKEN", None)
                if hf_token:
                    log_debug("HF_TOKEN found in environment")
                else:
                    log_debug("No HF_TOKEN in environment - API call will likely fail", "WARN")
                
                # Create HuggingFace Inference client
                log_debug("Creating InferenceClient...")
                client = InferenceClient(
                    provider="auto",
                    api_key=hf_token,
                )
                log_debug("InferenceClient created successfully")

                # Call chat completion API
                log_debug("Starting chat completion...")
                completion = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                )
                
                response = completion.choices[0].message.content
                log_debug(f"Completion received. Response length: {len(response)} characters")
                yield response
            
            except Exception as e:
                error_msg = f"API error: {str(e)}"
                log_debug(error_msg, "ERROR")
                log_debug(traceback.format_exc(), "ERROR")
                yield f"❌ API Error: {str(e)}\n\nPlease check log.txt for details."

    except Exception as e:
        error_msg = f"Unexpected error in respond function: {str(e)}"
        log_debug(error_msg, "ERROR")
        log_debug(traceback.format_exc(), "ERROR")
        yield f"❌ Unexpected Error: {str(e)}\n\nPlease check log.txt for details."


# ============================================================================
# Gradio UI Definition
# ============================================================================

with gr.Blocks(theme=TransparentTheme(), css=fancy_css) as demo:
    # Title banner
    gr.Markdown(f"<h1 id='title' style='text-align: center;'>{TITLE}</h1>")
    
    # Chatbot component with custom avatar icons
    chatbot = gr.Chatbot(
        type="messages",
        avatar_images=(str(ASSETS_DIR / "monster_icon.png"), str(ASSETS_DIR / "smart_confidant_icon.png"))
    )
    
    # Collapsible settings panel
    with gr.Accordion("⚙️ Additional Settings", open=False):
        system_message = gr.Textbox(value=DEFAULT_SYSTEM_MESSAGE, label="System message")
        max_tokens = gr.Slider(minimum=1, maximum=2048, value=512, step=1, label="Max new tokens")
        temperature = gr.Slider(minimum=0.1, maximum=2.0, value=0.7, step=0.1, label="Temperature")
        top_p = gr.Slider(minimum=0.1, maximum=1.0, value=0.95, step=0.05, label="Top-p (nucleus sampling)")
        selected_model = gr.Radio(choices=MODEL_OPTIONS, label="Select Model", value=MODEL_OPTIONS[0])
    
    # Wire up chat interface with response handler
    gr.ChatInterface(
        fn=respond,
        chatbot=chatbot,
        additional_inputs=[
            system_message,
            max_tokens,
            temperature,
            top_p,
            selected_model,
        ],
        type="messages",
    )

# ============================================================================
# Application Entry Point
# ============================================================================

if __name__ == "__main__":
    log_debug("="*50)
    log_debug("Smart Confidant Application Starting")
    log_debug(f"Available models: {MODEL_OPTIONS}")
    log_debug(f"HF_TOKEN present: {'Yes' if os.environ.get('HF_TOKEN') else 'No'}")
    log_debug("="*50)
    
    # Launch on all interfaces for VM/container deployment, with Gradio share link
    demo.launch(server_name="0.0.0.0", server_port=8012, share=True)
