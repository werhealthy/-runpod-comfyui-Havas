import gradio as gr
import requests
import json
import random
import time
import os
import io
import sys
import logging
from PIL import Image

# Configurazione Logger
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - %(message)s')

COMFY_URL = "http://127.0.0.1:8188"
WORKFLOW_FILE = "bg-change.json"

# --- HELPERS ---
def check_server():
    try: return requests.get(COMFY_URL).status_code == 200
    except: return False

def get_queue_status():
    try:
        res = requests.get(f"{COMFY_URL}/queue")
        if res.status_code == 200:
            data = res.json()
            return len(data.get('queue_pending', [])) + len(data.get('queue_running', []))
    except: pass
    return 0

def load_workflow():
    if not os.path.exists(WORKFLOW_FILE): return None
    with open(WORKFLOW_FILE, "r") as f: return json.load(f)

def upload_image_to_comfy(pil_image):
    try:
        buffer = io.BytesIO()
        pil_image.save(buffer, format="PNG")
        buffer.seek(0)
        files = {"image": ("input_gradio.png", buffer, "image/png")}
        res = requests.post(f"{COMFY_URL}/upload/image", files=files, data={"overwrite": "true"})
        if res.status_code == 200:
            return res.json().get("name")
    except:
        pass
    return None

# --- MOTORE PRINCIPALE ---
def run_process(img, prompt, seed, rnd, progress=gr.Progress(track_tqdm=True)):
    
    log_txt = "🔵 Inizializzazione..."
    yield None, log_txt

    # 1. UPLOAD
    progress(0.1, desc="Upload")
    fname = upload_image_to_comfy(img)
    if not fname: 
        yield None, "❌ Errore Upload"
        return
    log_txt += f"\n✅ Upload OK: {fname}"
    yield None, log_txt

    # 2. SETUP WORKFLOW
    wf = load_workflow()
    s = random.randint(1, 9**15) if rnd else int(seed)
    
    # --- PATCHING ---
    try:
        # Immagine -> Nodo 49
        if "49" in wf: wf["49"]["inputs"]["image"] = fname
        # Prompt -> Nodo 57
        if "57" in wf: wf["57"]["inputs"]["text"] = prompt
        # Seed -> Nodo 6
        if "6" in wf: wf["6"]["inputs"]["seed"] = s
    except Exception as e:
        yield None, f"❌ Errore ID Nodi: {e}"
        return

    # 3. INVIO
    progress(0.3, desc="Invio richiesta")
    clean_wf = {k: v for k, v in wf.items() if isinstance(v, dict) and 'class_type' in v}
    
    try:
        req = requests.post(f"{COMFY_URL}/prompt", data=json.dumps({"prompt": clean_wf}).encode('utf-8'))
        if req.status_code != 200:
            yield None, f"❌ Errore Server: {req.text}"
            return
        pid = req.json().get("prompt_id")
    except Exception as e:
        yield None, f"❌ Errore Connessione: {e}"
        return

    log_txt += f"\n✅ In lavorazione (ID: {pid})"
    yield None, log_txt

    # 4. MONITORAGGIO E RECUPERO IMMAGINE
    start_time = time.time()
    
    while True:
        try:
            hist = requests.get(f"{COMFY_URL}/history/{pid}").json()
            if pid in hist:
                # Abbiamo finito! Cerchiamo l'immagine GIUSTA (Type: output)
                outputs = hist[pid]["outputs"]
                target_img = None
                
                # Cerca in tutti i nodi di output
                for nid in outputs:
                    if "images" in outputs[nid]:
                        for candidate in outputs[nid]["images"]:
                            
                            # --- FILTRO IMPORTANTE: SALTA I FILE TEMP ---
                            if candidate.get("type") == "temp":
                                continue 
                            
                            # PRENDI SOLO FILE OUTPUT
                            if candidate.get("type") == "output":
                                target_img = candidate
                                break
                    
                    if target_img: break 
                
                if target_img:
                    fn = target_img.get("filename")
                    tp = target_img.get("type")
                    sf = target_img.get("subfolder", "")
                    
                    log_txt += f"\n📥 Scarico Immagine Finale: {fn}"
                    yield None, log_txt
                    progress(0.9, desc="Download")
                    
                    res = requests.get(f"{COMFY_URL}/view", params={"filename": fn, "subfolder": sf, "type": tp})
                    final_img = Image.open(io.BytesIO(res.content))
                    
                    log_txt += "\n🎉 COMPLETATO!"
                    yield final_img, log_txt
                    return
                else:
                    yield None, "❌ Errore: Nessuna immagine finale trovata (Solo preview temporanee)."
                    return

            # Feedback Coda
            q = get_queue_status()
            elapsed = int(time.time() - start_time)
            msg = f"⏳ In coda: {q} lavori davanti a te..." if q > 1 else f"🎨 Generazione in corso... ({elapsed}s)"
            progress(0.4 + (min(elapsed, 60)/100), desc=msg)
            
            time.sleep(1)
            if elapsed > 600: 
                yield None, "❌ Timeout (Server troppo lento)"
                return
                
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)

# --- UI (SENZA CSS CUSTOM) ---
with gr.Blocks(title="Havas AI Tool") as demo:
    gr.Markdown("## 🚀 Background Changer")
    
    with gr.Row():
        with gr.Column():
            im = gr.Image(label="Input", type="pil", height=300)
            p = gr.Textbox(label="Prompt", lines=3)
            with gr.Row():
                s = gr.Number(value=42, label="Seed")
                r = gr.Checkbox(value=True, label="Random")
            btn = gr.Button("GENERA", variant="primary")
            logs = gr.Textbox(label="Log", interactive=False, lines=6)
            
        with gr.Column():
            out = gr.Image(label="Output Finale", interactive=False)
    
    btn.click(run_process, inputs=[im, p, s, r], outputs=[out, logs], show_progress="hidden")

print("🚀 AVVIO SU PORTA 7860...")
demo.queue().launch(server_name="0.0.0.0", server_port=7860, share=True, allowed_paths=["/tmp"])

if __name__ == "__main__":
    pass
EOF
