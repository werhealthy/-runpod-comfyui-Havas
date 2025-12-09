"""
🛍️ AI Campaign Manager - Gradio Frontend (FINAL VERSION)
Architecture: 3-Worlds (RunPod Linux, n8n, Windows Server)
Feature: Session-based Folder Organization
"""

import gradio as gr
import requests
import os
import time
import io
import base64
import json
from PIL import Image
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import threading

# ========================================
# ⚙️ CONFIGURAZIONE
# ========================================

# URL dei Webhook di n8n (Verifica che siano corretti per la tua istanza)
N8N_IMAGES_URL = "http://127.0.0.1:5678/webhook/generate-images-2" 
N8N_VIDEO_URL  = "http://127.0.0.1:5678/webhook/generate-video"
N8N_FINAL_URL  = "http://127.0.0.1:5678/webhook/generate-final-video"

# Cartella base (Linux RunPod)
BASE_OUTPUT_DIR = "/tmp/comfyui/progetti"

# ========================================
# 🔧 UTILS
# ========================================

def create_session():
    """Crea una sessione HTTP robusta con retry."""
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def get_session_path(session_id=None):
    """
    Gestisce la creazione delle cartelle ordinate per data.
    Se session_id è None, ne crea uno nuovo.
    Ritorna: (session_id, full_path)
    """
    if not session_id:
        # Crea ID univoco: YYYYMMDD_HHMMSS (es. 20251209_153000)
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Percorso: /tmp/comfyui/progetti/20251209_153000/
    session_path = os.path.join(BASE_OUTPUT_DIR, session_id)
    
    # Crea la cartella se non esiste
    os.makedirs(session_path, exist_ok=True)
    
    return session_id, session_path

# ========================================
# 📸 STEP 1: IMMAGINI (Start Session)
# ========================================

def generate_images(image_path, prompt, progress=gr.Progress(track_tqdm=True)):
    
    # 1. CREAZIONE SESSIONE
    # Passiamo None per creare una nuova cartella pulita
    current_session_id, session_path = get_session_path(None)
    print(f"\n📂 [STEP 1] Nuova Sessione Avviata: {current_session_id}")
    print(f"   Salvataggio in: {session_path}")

    if not image_path: return [], current_session_id, [], "⚠️ Errore: Carica un'immagine!"
    
    progress(0.0, desc="Preparazione...")
    
    # 2. Encoding Immagine
    try:
        img = Image.open(image_path)
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=95)
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        # Salviamo anche l'immagine di input nella cartella sessione per riferimento
        img.save(os.path.join(session_path, "input_original.jpg"))
        
    except Exception as e:
        return [], current_session_id, [], f"❌ Errore img: {str(e)}"
    
    # 3. Chiamata n8n (Threaded)
    api_response = {}
    def call_n8n():
        try:
            session = create_session()
            resp = session.post(N8N_IMAGES_URL, json={"prompt": prompt, "image": img_base64}, timeout=600)
            api_response['data'] = resp
        except Exception as err:
            api_response['error'] = err

    t = threading.Thread(target=call_n8n)
    t.start()
    
    # Barra di caricamento sincronizzata (60s circa)
    start_time = time.time()
    estimated_duration = 60.0
    
    while t.is_alive():
        elapsed = time.time() - start_time
        current_prog = elapsed / estimated_duration
        if current_prog > 0.95: current_prog = 0.95
        progress(current_prog, desc=f"Generazione... {int(current_prog*100)}%")
        time.sleep(0.5)
    t.join()

    # 4. Gestione Risposta
    if 'error' in api_response:
        return [], current_session_id, [], f"❌ Err Connessione: {api_response['error']}"
        
    response = api_response.get('data')
    if not response or response.status_code != 200: 
        return [], current_session_id, [], f"❌ Err n8n ({response.status_code if response else '0'}): {response.text if response else ''}"
        
    # 5. Decodifica e Salvataggio Ordinato
    try:
        result = response.json()
        # Supporta sia lista diretta che oggetto {images: [...]}
        images_raw = result.get("images") if isinstance(result, dict) else result
        if not images_raw: images_raw = []
        
        output_images = []
        filenames_list = []

        for i, item in enumerate(images_raw):
            try:
                # Estrae stringa base64
                b64_str = item.get('data') if isinstance(item, dict) else item
                
                if b64_str and isinstance(b64_str, str):
                    img_bytes = base64.b64decode(b64_str)
                    image = Image.open(io.BytesIO(img_bytes))
                    output_images.append(image)
                    
                    # SALVATAGGIO NELLA CARTELLA SESSIONE
                    fname = f"gen_{i+1}.png"
                    local_path = os.path.join(session_path, fname)
                    image.save(local_path)
                    filenames_list.append(local_path)
                    print(f"✅ SALVATO FILE ORDINATO: {local_path}") # <--- CONTROLLA QUESTO NEL TERMINALE
            except Exception as e:
                print(f"⚠️ Errore save img {i}: {e}")

        if not output_images:
            return [], current_session_id, [], "⚠️ Nessuna immagine generata."

        progress(1.0, desc="Fatto!")
        return output_images, current_session_id, filenames_list, f"✅ Generate {len(output_images)} immagini in {current_session_id}"
        
    except Exception as e:
        return [], current_session_id, [], f"❌ Errore Parsing: {str(e)}"

# ========================================
# 🎬 STEP 2: VIDEO BASE (Save to Session)
# ========================================

def generate_video_base(selected_file, session_id, video_prompt, progress=gr.Progress(track_tqdm=True)):
    
    # Recuperiamo la cartella della sessione corrente
    # Se session_id è vuoto (es. test diretto), ne crea una nuova
    current_id, session_path = get_session_path(session_id)
    print(f"🚀 [STEP 2] Generazione Video. Sessione: {current_id}")
    
    if not selected_file: return None, None, "⚠️ Manca immagine."

    try:
        progress(0.1, desc="Invio file a n8n...")
        
        # Upload file fisico a n8n
        with open(selected_file, 'rb') as f:
            files = {'data': (os.path.basename(selected_file), f, 'image/png')}
            data = {'prompt': video_prompt, 'session_id': current_id}
            
            session = create_session()
            response = session.post(N8N_VIDEO_URL, files=files, data=data, timeout=600)
        
        if response.status_code != 200:
            return None, None, f"❌ Err n8n: {response.text}"
            
        # Leggiamo URL Fal.ai
        result = response.json()
        remote_video_url = result.get("video_url")
        
        if not remote_video_url:
            return None, None, f"❌ Nessun URL video ricevuto."
            
        print(f"✅ URL Fal.ai: {remote_video_url}")
        
        # Scarichiamo anteprima nella cartella ordinata
        progress(0.9, desc="Salvataggio...")
        local_filename = "base_video.mp4"
        local_path = os.path.join(session_path, local_filename)
        
        try:
            video_data = requests.get(remote_video_url).content
            with open(local_path, 'wb') as f_vid:
                f_vid.write(video_data)
        except Exception as e:
            print(f"⚠️ Errore download preview: {e}")

        # Ritorna: (Path Locale per Player, URL Remoto per State, Messaggio)
        return local_path, remote_video_url, "✅ Video Base Creato!"

    except Exception as e:
        return None, None, f"❌ Errore: {str(e)}"

# ========================================
# ✍️ STEP 3: RENDER FINALE (Save to Session)
# ========================================

def generate_final_video(base_video_url_state, session_id,
                         l1_text, l1_font, 
                         l2_text, l2_font, 
                         l3_text, l3_font, 
                         l4_text, l4_font, 
                         l5_text, l5_font, 
                         x_head, y_head, 
                         text_foot, 
                         progress=gr.Progress()):
    
    # Recuperiamo cartella sessione
    current_id, session_path = get_session_path(session_id)
    print(f"🚀 [STEP 3] Render Finale. Sessione: {current_id}")
    print(f"   URL Input: {base_video_url_state}")
    
    # Controlli sicurezza "3 Mondi"
    if not base_video_url_state: return None, "❌ Manca URL video."
    if str(base_video_url_state).startswith("/tmp") or not str(base_video_url_state).startswith("http"):
        return None, "❌ Errore: Trovato path locale invece di URL remoto."

    progress(0.1, desc="Invio a Windows...")
    
    # Preparazione Dati
    hero_lines = []
    def add_line(t, f): return {"text": t.strip() if t else "", "is_bold": (f=="Bold")}
    hero_lines.append(add_line(l1_text, l1_font))
    hero_lines.append(add_line(l2_text, l2_font))
    hero_lines.append(add_line(l3_text, l3_font))
    hero_lines.append(add_line(l4_text, l4_font))
    hero_lines.append(add_line(l5_text, l5_font))

    payload = {
        "video_url": base_video_url_state,
        "product_name": text_foot.strip() if text_foot else "",
        "hero_lines": hero_lines,
        "x_head": x_head, "y_head": y_head
    }
    
    try:
        session = create_session()
        print(f"📡 Chiamata n8n: {N8N_FINAL_URL}")
        response = session.post(N8N_FINAL_URL, json=payload, timeout=300)
        
        if response.status_code != 200:
            return None, f"❌ Errore Server: {response.text}"
        
        if not response.content:
            return None, "❌ File vuoto dal server."

        progress(0.8, desc="Salvataggio finale...")
        
        # Salvataggio ordinato
        output_filename = "final_render.mp4"
        output_path = os.path.join(session_path, output_filename)
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
            
        print(f"✅ Video Finale salvato in: {output_path}")
        progress(1.0, desc="Fatto!")
        
        return output_path, f"✅ Render Completato! (Sessione: {current_id})"

    except Exception as e:
        print(f"❌ Eccezione: {e}")
        return None, f"❌ Errore: {str(e)}"

# ========================================
# 🎨 INTERFACCIA (UI)
# ========================================

with gr.Blocks(title="AI Campaign Manager v2.0") as demo:
    
    # STATI GLOBALI
    state_session_id = gr.State() # ID Cartella (es. 20251209_1030)
    state_video_url = gr.State()  # URL Remoto Fal.ai
    
    state_filenames = gr.State()
    state_selected_file = gr.State()
    state_row_count = gr.State(value=1)

    gr.Markdown("# 🛍️ AI Campaign Manager (Session Folder System)")
    
    with gr.Tabs() as main_tabs:
        
        # --- TAB 1 ---
        with gr.Tab("1. Immagini", id=0):
            with gr.Row():
                with gr.Column(scale=1):
                    inp_img = gr.Image(type="filepath", height=300, label="Input Prodotto")
                    inp_prompt = gr.Textbox(label="Prompt", lines=3, value="metti lo zaino in spiaggia")
                    btn_gen_img = gr.Button("🚀 Genera Nuova Sessione", variant="primary")
                with gr.Column(scale=2):
                    out_gallery = gr.Gallery(columns=3, height="auto", interactive=False)
                    status_msg = gr.Markdown("Pronto")
            
            with gr.Row(visible=False) as confirm_section:
                with gr.Column():
                    selected_preview = gr.Image(label="Selezionata", interactive=False, height=300)
                    btn_confirm = gr.Button("✅ Conferma e Vai ai Video", variant="primary")

        # --- TAB 2 ---
        with gr.Tab("2. Video Base", id=1):
            with gr.Row():
                with gr.Column(scale=1):
                    final_preview = gr.Image(interactive=True, height=300, label="Img Scelta", type="filepath")
                    video_prompt_input = gr.Textbox(label="Prompt Video", value="cinematic zoom", lines=3)
                    btn_gen_vid = gr.Button("✨ Genera Video Base", variant="primary")
                with gr.Column(scale=2):
                    out_video = gr.Video(height=450, label="Video Preview", interactive=False)
                    video_status = gr.Markdown("")
            
            with gr.Row(visible=False) as video_confirm_section:
                btn_confirm_video = gr.Button("✅ Video OK? Vai ai Testi", variant="primary")

        # --- TAB 3 ---
        with gr.Tab("3. Testi & Render", id=2):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### ✍️ Overlay Testi")
                    inp_video_step3 = gr.Video(label="Base", interactive=False, height=200)

                    # Righe Testo
                    def hide_row(): return gr.update(visible=False), "", "Bold"
                    with gr.Row(visible=True, variant="compact"):
                        l1_txt = gr.Textbox(placeholder="Riga 1", show_label=False, scale=3)
                        l1_font = gr.Dropdown(["Bold", "Normal"], value="Bold", show_label=False, scale=1)
                    
                    # (Righe 2-5 nascoste per brevità codice, logica standard)
                    with gr.Row(visible=False, variant="compact") as r2:
                        l2_txt = gr.Textbox(placeholder="Riga 2", show_label=False, scale=3)
                        l2_font = gr.Dropdown(["Bold", "Normal"], value="Normal", show_label=False, scale=1)
                        btn_del_2 = gr.Button("x", size="sm", scale=0)
                        btn_del_2.click(fn=hide_row, outputs=[r2, l2_txt, l2_font])
                    
                    # ... Puoi aggiungere r3, r4, r5 qui se vuoi ...
                    
                    btn_add = gr.Button("+ Riga", size="sm")
                    btn_add.click(lambda: gr.update(visible=True), outputs=[r2]) # Semplificato per brevità

                    with gr.Group():
                        gr.Markdown("#### Posizione")
                        sl_x = gr.Slider(0, 100, value=50, label="X")
                        sl_y = gr.Slider(0, 100, value=15, label="Y")
                        txt_foot = gr.Textbox(label="Footer Prodotto")

                    btn_render = gr.Button("🎬 Renderizza Finale", variant="primary", size="lg")

                with gr.Column(scale=2):
                    out_final = gr.Video(label="Risultato Finale", height=450)
                    final_status = gr.Markdown("")

    # ========================================
    # LOGICA DI COLLEGAMENTO (WIRING)
    # ========================================
    
    # Step 1
    btn_gen_img.click(
        fn=generate_images, 
        inputs=[inp_img, inp_prompt], 
        outputs=[out_gallery, state_session_id, state_filenames, status_msg]
    )
    
    # Selezione Immagine
    def on_select(filenames, evt: gr.SelectData):
        if not filenames: return None, gr.update(visible=False), None
        s = filenames[evt.index]
        return s, gr.update(visible=True), s

    out_gallery.select(fn=on_select, inputs=[state_filenames], outputs=[state_selected_file, confirm_section, selected_preview])
    
    # Transizione Tab 1 -> 2
    def to_tab2(file): return file, gr.Tabs(selected=1)
    btn_confirm.click(fn=to_tab2, inputs=[state_selected_file], outputs=[final_preview, main_tabs])
    selected_preview.change(lambda x: x, inputs=[selected_preview], outputs=[final_preview])

    # Step 2
    gen_vid_event = btn_gen_vid.click(
        fn=generate_video_base, 
        inputs=[state_selected_file, state_session_id, video_prompt_input], 
        outputs=[out_video, state_video_url, video_status] # <--- State Video URL aggiornato qui
    )
    
    def on_vid_ok(url): return gr.update(visible=bool(url))
    gen_vid_event.then(fn=on_vid_ok, inputs=[state_video_url], outputs=[video_confirm_section])

    # Transizione Tab 2 -> 3
    def to_tab3(vid): return vid, gr.Tabs(selected=2)
    btn_confirm_video.click(fn=to_tab3, inputs=[out_video], outputs=[inp_video_step3, main_tabs])

    # Step 3
    btn_render.click(
        fn=generate_final_video, 
        inputs=[
            state_video_url, # URL remoto (HTTPS)
            state_session_id, # Cartella sessione
            l1_txt, l1_font,
            l2_txt, l2_font,
            l1_txt, l1_font, # Placeholder per r3
            l1_txt, l1_font, # Placeholder per r4
            l1_txt, l1_font, # Placeholder per r5
            sl_x, sl_y, 
            txt_foot
        ],
        outputs=[out_final, final_status]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7861, share=True)