import gradio as gr
from huggingface_hub import InferenceClient
import os
import base64
from pathlib import Path
import threading
import time
import logging

# Configuration
LOCAL_MODELS = ["tiiuae/Falcon-H1-0.5B-Instruct"]
API_MODELS = ["openai/gpt-oss-20b"]
DEFAULT_SYSTEM_MESSAGE = "You are an expert assistant for Magic: The Gathering. You're name is Smart Confidant, but people tend to call you Bob."
TITLE = "🎓🧙🏻‍♂️ Smart Confidant 🧙🏻‍♂️🎓"

# Resource logging configuration
RESOURCE_LOGGING_ENABLED = True
RESOURCE_LOG_INTERVAL_SEC = 15

# Create model options with labels
MODEL_OPTIONS = []
for model in LOCAL_MODELS:
    MODEL_OPTIONS.append(f"{model} (local)")
for model in API_MODELS:
    MODEL_OPTIONS.append(f"{model} (api)")

pipe = None
stop_inference = False

ASSETS_DIR = Path(__file__).parent / "assets"
BACKGROUND_IMAGE_PATH = ASSETS_DIR / "confidant_pattern.png"
try:
    with open(BACKGROUND_IMAGE_PATH, "rb") as _img_f:
        _encoded_img = base64.b64encode(_img_f.read()).decode("ascii")
        BACKGROUND_DATA_URL = f"data:image/png;base64,{_encoded_img}"
except Exception as e:
    print(f"Error loading background image: {e}")
    BACKGROUND_DATA_URL = ""

# Fancy styling
fancy_css = f"""
    html, body, #root {{
        background-image: url('{BACKGROUND_DATA_URL}');
        background-repeat: repeat;
        background-size: auto;
        background-color: transparent;
    }}
    .gradio-container {{
        max-width: 700px;
        margin: 0 auto;
        padding: 20px;
        background-color: #2d2d2d;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        border-radius: 10px;
        font-family: 'Arial', sans-serif;
    }}
    .gr-button {{
        background-color: #4CAF50;
        color: white;
        border: none;
        border-radius: 5px;
        padding: 10px 20px;
        cursor: pointer;
        transition: background-color 0.3s ease;
    }}
    .gr-button:hover {{
        background-color: #45a049;
    }}
    .gr-slider input {{
        color: #4CAF50;
    }}
    .gr-chat {{
        font-size: 16px;
    }}
    #title {{
        text-align: center;
        font-size: 2em;
        margin-bottom: 20px;
        color: #333;
    }}
    """

def _configure_basic_logging():
    if len(logging.getLogger().handlers) == 0:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
        )


def _resource_logger_worker(interval_seconds: int):
    try:
        import psutil

        process = psutil.Process(os.getpid())
        # Prime CPU percent calculations
        psutil.cpu_percent(interval=None)
        process.cpu_percent(interval=None)

        while True:
            system_cpu_percent = psutil.cpu_percent(interval=None)
            system_mem_percent = psutil.virtual_memory().percent
            process_rss_mb = process.memory_info().rss / (1024 * 1024)
            process_cpu_percent = process.cpu_percent(interval=None)

            logging.info(
                f"System CPU: {system_cpu_percent:.1f}%, System Mem: {system_mem_percent:.1f}%, "
                f"Process RSS: {process_rss_mb:.1f} MB, Process CPU: {process_cpu_percent:.1f}%"
            )

            time.sleep(interval_seconds)
    except ImportError:
        logging.warning("psutil not installed; resource logging disabled.")
    except Exception as e:
        logging.exception(f"Resource logger stopped due to error: {e}")


def start_resource_logger():
    _configure_basic_logging()
    thread = threading.Thread(
        target=_resource_logger_worker,
        args=(RESOURCE_LOG_INTERVAL_SEC,),
        daemon=True,
        name="resource-logger",
    )
    thread.start()
    return thread

def respond(
    message,
    history: list[dict[str, str]],
    system_message,
    max_tokens,
    temperature,
    top_p,
    hf_token: gr.OAuthToken,
    selected_model: str,
):
    global pipe

    # Build messages from history
    messages = [{"role": "system", "content": system_message}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    # Determine if model is local or API and extract model name
    is_local = selected_model.endswith("(local)")
    model_name = selected_model.replace(" (local)", "").replace(" (api)", "")
    
    response = ""

    if is_local:
        print(f"[MODE] local - {model_name}")
        from transformers import pipeline
        import torch
        if pipe is None or pipe.model.name_or_path != model_name:
            pipe = pipeline("text-generation", model=model_name)

        # Build prompt as plain text
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])

        outputs = pipe(
            prompt,
            max_new_tokens=max_tokens,
            do_sample=True,
            temperature=temperature,
            top_p=top_p,
        )

        response = outputs[0]["generated_text"][len(prompt):]
        yield response.strip()

    else:
        print(f"[MODE] api - {model_name}")

        if hf_token is None or not getattr(hf_token, "token", None):
            yield "⚠️ Please log in with your Hugging Face account first."
            return

        client = InferenceClient(token=hf_token.token, model=model_name)

        for chunk in client.chat_completion(
            messages,
            max_tokens=max_tokens,
            stream=True,
            temperature=temperature,
            top_p=top_p,
        ):
            choices = chunk.choices
            token = ""
            if len(choices) and choices[0].delta.content:
                token = choices[0].delta.content
            response += token
            yield response


with gr.Blocks(css=fancy_css) as demo:
    gr.LoginButton()
    gr.Markdown(f"<h1 style='text-align: center;'>{TITLE}</h1>")
    
    # Create custom chatbot with avatar images
    chatbot = gr.Chatbot(
        type="messages",
        avatar_images=(str(ASSETS_DIR / "monster_icon.png"), str(ASSETS_DIR / "smart_confidant_icon.png"))
    )
    
    # Create additional inputs in an accordion
    with gr.Accordion("⚙️ Additional Settings", open=False):
        system_message = gr.Textbox(value=DEFAULT_SYSTEM_MESSAGE, label="System message")
        max_tokens = gr.Slider(minimum=1, maximum=2048, value=512, step=1, label="Max new tokens")
        temperature = gr.Slider(minimum=0.1, maximum=2.0, value=0.7, step=0.1, label="Temperature")
        top_p = gr.Slider(minimum=0.1, maximum=1.0, value=0.95, step=0.05, label="Top-p (nucleus sampling)")
        selected_model = gr.Radio(choices=MODEL_OPTIONS, label="Select Model", value=MODEL_OPTIONS[0])
    
    # Create ChatInterface with the custom chatbot and pre-rendered additional inputs
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

if __name__ == "__main__":
    if RESOURCE_LOGGING_ENABLED:
        start_resource_logger()
    demo.launch()
