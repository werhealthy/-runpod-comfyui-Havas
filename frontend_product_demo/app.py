import json
import io
import uuid
import time
import random
from pathlib import Path

import gradio as gr
import requests
from PIL import Image

# ComfyUI gira nello stesso pod
COMFY_URL = "http://127.0.0.1:8188"

# Workflow API esportato da ComfyUI
WORKFLOW_PATH = Path(__file__).parent / "workflow_api.json"


def upload_image_to_comfy(pil_image: Image.Image):
    """
    Carica l'immagine su ComfyUI via /upload/image e restituisce il filename.
    """
    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    buf.seek(0)

    files = {"image": ("upload.png", buf, "image/png")}
    resp = requests.post(f"{COMFY_URL}/upload/image", files=files)
    resp.raise_for_status()
    data = resp.json()
    # Es: {"name": "upload.png", "subfolder": "", "type": "input"}
    return data["name"]


def queue_prompt(prompt_dict: dict):
    client_id = str(uuid.uuid4())
    payload = {"prompt": prompt_dict, "client_id": client_id}
    r = requests.post(f"{COMFY_URL}/prompt", json=payload)
    r.raise_for_status()
    out = r.json()
    return out["prompt_id"], client_id


def wait_for_result(prompt_id: str):
    """
    Fa polling su /history finché il job non è finito e restituisce "outputs".
    """
    while True:
        time.sleep(1)
        r = requests.get(f"{COMFY_URL}/history/{prompt_id}")
        if r.status_code != 200:
            continue
        history = r.json()
        if prompt_id not in history:
            continue
        data = history[prompt_id]
        if "outputs" in data and len(data["outputs"]) > 0:
            return data["outputs"]


def download_first_image(outputs: dict):
    """
    Cerca la prima immagine negli outputs e la scarica via /view.
    """
    for node_id, node_output in outputs.items():
        if "images" not in node_output:
            continue
        img_info = node_output["images"][0]
        params = {
            "filename": img_info["filename"],
            "subfolder": img_info.get("subfolder", ""),
            "type": img_info.get("type", "output"),
        }
        r = requests.get(f"{COMFY_URL}/view", params=params)
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content))
    return None


def run_frontend(input_image, user_prompt, output_format, user_seed, random_seed):
    """
    Funzione chiamata da Gradio.
    """
    if input_image is None or not user_prompt:
        return None

    # Seed: fisso o random
    if random_seed:
        effective_seed = random.randint(0, 2**32 - 1)
    else:
        try:
            effective_seed = int(user_seed)
        except (TypeError, ValueError):
            effective_seed = 42  # fallback

    # 1. Upload immagine a Comfy
    img_name = upload_image_to_comfy(input_image)

    # 2. Carica workflow base (API)
    workflow = json.loads(WORKFLOW_PATH.read_text())

    # NOTA: Nel file API le chiavi dei nodi sono stringhe, es. "49", "57", "1", "6"

    # 3. Patch del workflow con i tuoi parametri

    # a) Immagine nel nodo LoadImage (id 49)
    #    input "image" deve puntare al filename caricato
    workflow["49"]["inputs"]["image"] = img_name

    # b) Prompt utente nel nodo CR Text additional prompt (id 57)
    workflow["57"]["inputs"]["text"] = user_prompt

    # c) Formato → target_size e target_vl_size nel nodo Qwen (id 1)
    if output_format == "Quadrato 1024x1024":
        size = [1024, 1024]
    elif output_format == "16:9 1280x720":
        size = [1280, 720]
    else:
        size = [1024, 1024]

    workflow["1"]["inputs"]["target_size"] = size
    workflow["1"]["inputs"]["target_vl_size"] = size

    # d) Seed nel KSampler (id 6)
    workflow["6"]["inputs"]["seed"] = effective_seed

    # 4. Manda il prompt a ComfyUI
    prompt_id, client_id = queue_prompt(workflow)

    # 5. Aspetta il risultato
    outputs = wait_for_result(prompt_id)

    # 6. Scarica l'immagine finale
    result_img = download_first_image(outputs)
    return result_img


def main():
    with gr.Blocks(title="Product Photography Demo") as demo:
        gr.Markdown("## Product Photography demo (Qwen + ComfyUI)\n"
                    "Carica un'immagine di prodotto, scrivi il prompt della scena e scegli il formato.")

        with gr.Row():
            input_image = gr.Image(label="Immagine di prodotto", type="pil")
            with gr.Column():
                user_prompt = gr.Textbox(
                    label="Prompt scena",
                    placeholder="es. metti il prodotto su un tavolo di marmo in una cucina moderna…",
                    lines=3,
                )
                output_format = gr.Dropdown(
                    ["Quadrato 1024x1024", "16:9 1280x720"],
                    value="Quadrato 1024x1024",
                    label="Formato output",
                )
                user_seed = gr.Number(
                    value=42,
                    precision=0,
                    label="Seed (usato se 'Seed random' è disattivato)",
                )
                random_seed = gr.Checkbox(
                    value=True,
                    label="Seed random ad ogni generazione",
                )
                run_btn = gr.Button("Genera")

        output_image = gr.Image(label="Risultato", type="pil")

        run_btn.click(
            fn=run_frontend,
            inputs=[input_image, user_prompt, output_format, user_seed, random_seed],
            outputs=output_image,
        )

    demo.launch(server_name="0.0.0.0", server_port=7860)


if __name__ == "__main__":
    main()
