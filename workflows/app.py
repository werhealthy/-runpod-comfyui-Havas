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
    
    # Barra di caricamento sincronizzata (50s circa)
    start_time = time.time()
    estimated_duration = 49.0
    
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

def generate_video_base(selected_file, session_id, video_prompt, model_choice, progress=gr.Progress(track_tqdm=True)):
    
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
    
    # ... (Codice sessione e controlli URL invariati) ...
    current_id, session_path = get_session_path(session_id)
    
    progress(0.1, desc="Preparazione Dati...")
    
    # --- LOGICA DINAMICA RIGHE ---
    hero_lines = []
    
    # Helper per aggiungere solo se c'è testo
    def process_line(text, font):
        clean_text = text.strip() if text else ""
        if clean_text: # Aggiunge solo se la riga non è vuota
            hero_lines.append({
                "text": clean_text,
                "is_bold": (font == "Bold")
            })

    # Processiamo tutte le 5 potenziali righe
    process_line(l1_text, l1_font)
    process_line(l2_text, l2_font)
    process_line(l3_text, l3_font)
    process_line(l4_text, l4_font)
    process_line(l5_text, l5_font)

    # Se non c'è nessuna riga, mandiamo un array vuoto o un placeholder
    if not hero_lines:
        print("⚠️ Nessuna riga di testo inserita.")

    payload = {
        "video_url": base_video_url_state,
        "product_name": text_foot.strip() if text_foot else "",
        "hero_lines": hero_lines, # Ora contiene solo le righe compilate
        "x_head": x_head, 
        "y_head": y_head
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

# Tema Soft con accento rosso, bordo standard Gradio
theme = gr.themes.Soft(
    primary_hue="red",
    neutral_hue="gray",
    radius_size=gr.themes.sizes.radius_sm,
)

custom_css = """
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap');

.gradio-container {
  font-family: "DM Sans", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

:root {
  --brand-red: #E20800;
  --brand-black: #111111;

  /* Disattiva pill colorate delle label del tema Soft */
  --block-label-background-fill: transparent;
  --block-label-border-color: transparent;
  --block-label-text-color: #111111;
}

/* ---------- HEADER: logo sopra, titolo sotto, allineati con le tab ---------- */

#header-row {
  display: flex;
  justify-content: flex-start;
  padding-left: 24px;
  margin-bottom: 16px;
}

#logo-img {
  margin: 0 !important;
  padding: -40 !important;
  max-width: 200px;
}

/* togli bordo / card dal blocco immagine del logo */
#logo-img .wrap,
#logo-img .container {
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
}

/* allinea l'immagine a sinistra dentro l'image-container */
#logo-img .image-container {
  justify-content: flex-start !important;
}

/* nascondi i pulsantini fullscreen/download/share */
#logo-img .icon-button-wrapper {
  display: none !important;
}

/* Placeholder più chiaro ovunque */
.gradio-container ::placeholder {
  color: #BCBCBC !important;
  opacity: 1 !important;
}

/* dimensione precisa del logo */
#logo-img img {
  height: 17px !important;
  width: auto !important;
  object-fit: contain !important;
  margin: 0 !important;
}

/* Titolo */
#app-title-wrapper {
  margin: 4px 0 0 0 !important;
  padding: 0 !important;
}

#app-title {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  margin: 0;
  color: #1F2933;
}

/* ---------- LABEL: niente rettangolo rosso, solo testo ---------- */

label[data-testid="block-label"],
.gradio-container .block-label,
.gradio-container .gr-input-label,
.gradio-container .gr-label {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
  margin-bottom: 4px !important;
  color: #111111 !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  text-transform: none !important;
  letter-spacing: 0 !important;
}

/* ---------- TABS: solo accento rosso sulla tab attiva ---------- */

.gradio-container .tab-nav button.selected,
.gradio-container .tabs button.selected {
  color: var(--brand-red) !important;
  border-color: var(--brand-red) !important;
}

/* ---------- BOTTONI ---------- */

button.gr-button.primary,
.gr-button-primary {
  background-color: var(--brand-red) !important;
  border-color: var(--brand-red) !important;
  color: #ffffff !important;
  font-weight: 600 !important;
}
button.gr-button.primary:hover,
.gr-button-primary:hover {
  filter: brightness(0.92);
}

/* pulsanti non primari, neutri */
button.gr-button:not(.primary) {
  background-color: #ffffff !important;
  color: var(--brand-black) !important;
  border: 1px solid #DDDDDD !important;
}

/* Bottone "Aggiungi frase" */
.add-line-btn {
  border-radius: 999px !important;
  font-weight: 500 !important;
  padding-inline: 14px !important;
  background-color: #ffffff !important;
  color: var(--brand-red) !important;
  border: 1px solid var(--brand-red) !important;
}
.add-line-btn:hover {
  background-color: rgba(226, 8, 0, 0.05) !important;
}

/* ---------- RIGHE TESTO (Frase + X + Font) ---------- */

.sentence-row {
  gap: 8px;
  align-items: center;
}
.sentence-row > * {
  margin: 0 !important;
}

/* Spacer invisibile della riga 1 (uguale alla X) */
.delete-line-spacer {
  width: 40px;
  min-width: 40px;
  height: 1px;
}

/* X: bottone pieno, alto come il campo, proporzionato */
.delete-line-btn {
  border-radius: 8px !important;
  background-color: #F3F4F6 !important;
  color: #111827 !important;
  border: 1px solid #E5E7EB !important;
  font-weight: 600 !important;
  font-size: 16px !important;
  width: 40px !important;
  min-width: 40px !important;
  height: 44px !important;
  padding: 0 !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
}

/* ---------- SLIDER track ---------- */

input[type="range"]::-webkit-slider-runnable-track {
  background: #E5E5E5;
}
input[type="range"]::-moz-range-track {
  background: #E5E5E5;
}
"""


with gr.Blocks(
    title="Executive Tool 001: Aliexpress Video",
    theme=theme,
    css=custom_css,
) as demo:
    
    # STATI GLOBALI
    state_session_id = gr.State()   # ID Cartella (es. 20251209_1030)
    state_video_url = gr.State()    # URL Remoto Fal.ai
    
    state_filenames = gr.State()
    state_selected_file = gr.State()
    state_row_count = gr.State(value=1)  # quante frasi sono visibili

    # ---------- HEADER ----------
    with gr.Row(elem_id="header-row"):
        with gr.Column(scale=1, min_width=260):
            gr.Image(
                value="logo.png",
                show_label=False,
                interactive=False,
                height=24,
                elem_id="logo-img",
                type="filepath",
            )
            gr.HTML(
                '<div id="app-title-wrapper"><div id="app-title">EXECUTIVE TOOL 001: ALIEXPRESS VIDEO</div></div>'
            )

    with gr.Tabs() as main_tabs:
        
        # ========== TAB 1: IMMAGINE ==========
        with gr.Tab("Immagine", id=0):
            with gr.Row():
                with gr.Column(scale=1):
                    inp_img = gr.Image(
                        type="filepath",
                        height=300,
                        label="Immagine prodotto"
                    )
                    inp_prompt = gr.Textbox(
                        label="Prompt immagine",
                        lines=3,
                        placeholder=(
                            "Fotografia prodotto e-commerce di [nome prodotto] appoggiato "
                            "su un tavolo di legno chiaro, stanza minimal, luce morbida laterale, "
                            "sfondo sfocato, stile studio professionale"
                        ),
                        value=""
                    )
                    btn_gen_img = gr.Button(
                        "Genera",
                        variant="primary",
                    )
                with gr.Column(scale=2):
                    out_gallery = gr.Gallery(
                        columns=3,
                        height="auto",
                        interactive=False,
                        label="Risultati generati"
                    )
                    status_msg = gr.Markdown("")

            with gr.Row(visible=False) as confirm_section:
                with gr.Column():
                    selected_preview = gr.Image(
                        label="Immagine selezionata",
                        interactive=False,
                        height=300
                    )
                    btn_confirm = gr.Button(
                        "Conferma e vai al video",
                        variant="primary",
                    )

        # ========== TAB 2: VIDEO ==========
        with gr.Tab("Video", id=1):
            with gr.Row():
                with gr.Column(scale=1):
                    final_preview = gr.Image(
                        interactive=True,
                        height=300,
                        label="Frame di partenza",
                        type="filepath"
                    )
                    
                    video_model_selector = gr.Dropdown(
                        choices=[
                            "Video Prova (SVD - €0.05)",
                            "Kling 1.5 Pro (High Quality - €0.50)"
                        ],
                        value="Video Prova (SVD - €0.05)",
                        label="Seleziona modello video"
                    )
                    
                    video_prompt_input = gr.Textbox(
                        label="Prompt video",
                        lines=3,
                        placeholder=(
                            "Slow cinematic zoom sul prodotto appoggiato su un tavolo di legno chiaro, "
                            "luce morbida di studio, sfondo sfocato, movimento di camera fluido "
                            "verso il prodotto, inquadratura orizzontale 16:9"
                        ),
                        value=""
                    )
                    btn_gen_vid = gr.Button(
                        "Genera",
                        variant="primary",
                    )

                with gr.Column(scale=2):
                    out_video = gr.Video(
                        height=450,
                        label="Anteprima video",
                        interactive=False
                    )
                    video_status = gr.Markdown("")
            
            with gr.Row(visible=False) as video_confirm_section:
                btn_confirm_video = gr.Button(
                    "Video ok? Vai ai testi",
                    variant="primary",
                )

        # ========== TAB 3: TESTI ==========
        with gr.Tab("Testi", id=2):
            with gr.Row():
                # COLONNA 1 — INPUT TESTI
                with gr.Column(scale=1):
                    # Video base in alto
                    inp_video_step3 = gr.Video(
                        label="Video base",
                        interactive=False,
                        height=200
                    )

                    # Titolo sezione
                    gr.Markdown("### Overlay testi")

                    # --- LOGICA RIGHE DINAMICHE ---
                    def hide_row_logic(current_count):
                        new_count = max(1, current_count - 1)
                        return gr.update(visible=False), "", "Normal", new_count

                    # RIGA 1 (no X, ma spacer della stessa larghezza)
                    with gr.Row(visible=True, variant="compact", elem_classes=["sentence-row"]) as r1:
                        l1_txt = gr.Textbox(
                            placeholder="Frase 1",
                            show_label=False,
                            scale=6
                        )
                        spacer_1 = gr.HTML(
                            "<div class='delete-line-spacer'></div>",
                            show_label=False,
                            scale=1
                        )
                        l1_font = gr.Dropdown(
                            ["Bold", "Normal"],
                            value="Bold",
                            show_label=False,
                            scale=2
                        )

                    # RIGA 2
                    with gr.Row(visible=False, variant="compact", elem_classes=["sentence-row"]) as r2:
                        l2_txt = gr.Textbox(
                            placeholder="Frase 2",
                            show_label=False,
                            scale=6
                        )
                        btn_del_2 = gr.Button(
                            "×",
                            size="sm",
                            elem_classes=["delete-line-btn"],
                            scale=1,
                        )
                        l2_font = gr.Dropdown(
                            ["Bold", "Normal"],
                            value="Normal",
                            show_label=False,
                            scale=2
                        )
                        btn_del_2.click(
                            fn=hide_row_logic,
                            inputs=[state_row_count],
                            outputs=[r2, l2_txt, l2_font, state_row_count]
                        )

                    # RIGA 3
                    with gr.Row(visible=False, variant="compact", elem_classes=["sentence-row"]) as r3:
                        l3_txt = gr.Textbox(
                            placeholder="Frase 3",
                            show_label=False,
                            scale=6
                        )
                        btn_del_3 = gr.Button(
                            "×",
                            size="sm",
                            elem_classes=["delete-line-btn"],
                            scale=1,
                        )
                        l3_font = gr.Dropdown(
                            ["Bold", "Normal"],
                            value="Normal",
                            show_label=False,
                            scale=2
                        )
                        btn_del_3.click(
                            fn=hide_row_logic,
                            inputs=[state_row_count],
                            outputs=[r3, l3_txt, l3_font, state_row_count]
                        )

                    # RIGA 4
                    with gr.Row(visible=False, variant="compact", elem_classes=["sentence-row"]) as r4:
                        l4_txt = gr.Textbox(
                            placeholder="Frase 4",
                            show_label=False,
                            scale=6
                        )
                        btn_del_4 = gr.Button(
                            "×",
                            size="sm",
                            elem_classes=["delete-line-btn"],
                            scale=1,
                        )
                        l4_font = gr.Dropdown(
                            ["Bold", "Normal"],
                            value="Normal",
                            show_label=False,
                            scale=2
                        )
                        btn_del_4.click(
                            fn=hide_row_logic,
                            inputs=[state_row_count],
                            outputs=[r4, l4_txt, l4_font, state_row_count]
                        )

                    # RIGA 5
                    with gr.Row(visible=False, variant="compact", elem_classes=["sentence-row"]) as r5:
                        l5_txt = gr.Textbox(
                            placeholder="Frase 5",
                            show_label=False,
                            scale=6
                        )
                        btn_del_5 = gr.Button(
                            "×",
                            size="sm",
                            elem_classes=["delete-line-btn"],
                            scale=1,
                        )
                        l5_font = gr.Dropdown(
                            ["Bold", "Normal"],
                            value="Normal",
                            show_label=False,
                            scale=2
                        )
                        btn_del_5.click(
                            fn=hide_row_logic,
                            inputs=[state_row_count],
                            outputs=[r5, l5_txt, l5_font, state_row_count]
                        )

                    # BOTTONE AGGIUNGI FRASE
                    btn_add_row = gr.Button(
                        "Aggiungi frase",
                        size="sm",
                        elem_classes=["add-line-btn"]
                    )

                    def add_next_row(count):
                        if count >= 5:
                            return (
                                gr.update(),
                                gr.update(),
                                gr.update(),
                                gr.update(),
                                count
                            )
                        if count == 1:
                            return (
                                gr.update(visible=True),  # r2
                                gr.update(),
                                gr.update(),
                                gr.update(),
                                2
                            )
                        if count == 2:
                            return (
                                gr.update(),
                                gr.update(visible=True),  # r3
                                gr.update(),
                                gr.update(),
                                3
                            )
                        if count == 3:
                            return (
                                gr.update(),
                                gr.update(),
                                gr.update(visible=True),  # r4
                                gr.update(),
                                4
                            )
                        if count == 4:
                            return (
                                gr.update(),
                                gr.update(),
                                gr.update(),
                                gr.update(visible=True),  # r5
                                5
                            )
                        return (
                            gr.update(),
                            gr.update(),
                            gr.update(),
                            gr.update(),
                            count
                        )

                    btn_add_row.click(
                        fn=add_next_row,
                        inputs=[state_row_count],
                        outputs=[r2, r3, r4, r5, state_row_count]
                    )

                    # CONTROLLI POSIZIONE TESTI + NOME PRODOTTO
                    sl_x = gr.Slider(
                        0, 100,
                        value=50,
                        label="X testi"
                    )
                    sl_y = gr.Slider(
                        0, 100,
                        value=15,
                        label="Y testi"
                    )
                    txt_foot = gr.Textbox(
                        label="Nome prodotto"
                    )

                    btn_render = gr.Button(
                        "Renderizza",
                        variant="primary",
                    )

                # COLONNA 2 — OUTPUT VIDEO FINALE
                with gr.Column(scale=1):
                    gr.Markdown("### Video finale")
                    out_final = gr.Video(
                        label="Output finale",
                        height=320,
                        interactive=False
                    )
                    final_status = gr.Markdown("")

    # ========================================
    # LOGICA DI COLLEGAMENTO (WIRING)
    # ========================================
    
    # Step 1 - immagini
    btn_gen_img.click(
        fn=generate_images,
        inputs=[inp_img, inp_prompt],
        outputs=[out_gallery, state_session_id, state_filenames, status_msg]
    )
    
    # Selezione Immagine
    def on_select(filenames, evt: gr.SelectData):
        if not filenames:
            return None, gr.update(visible=False), None
        s = filenames[evt.index]
        return s, gr.update(visible=True), s

    out_gallery.select(
        fn=on_select,
        inputs=[state_filenames],
        outputs=[state_selected_file, confirm_section, selected_preview]
    )
    
    # Transizione Tab 1 -> 2
    def to_tab2(file):
        return file, gr.Tabs(selected=1)

    btn_confirm.click(
        fn=to_tab2,
        inputs=[state_selected_file],
        outputs=[final_preview, main_tabs]
    )
    selected_preview.change(
        lambda x: x,
        inputs=[selected_preview],
        outputs=[final_preview]
    )

    # Step 2 - video base
    gen_vid_event = btn_gen_vid.click(
        fn=generate_video_base,
        inputs=[state_selected_file, state_session_id, video_prompt_input, video_model_selector],
        outputs=[out_video, state_video_url, video_status]
    )
    
    def on_vid_ok(url):
        return gr.update(visible=bool(url))

    gen_vid_event.then(
        fn=on_vid_ok,
        inputs=[state_video_url],
        outputs=[video_confirm_section]
    )

    # Transizione Tab 2 -> 3
    def to_tab3(vid):
        return vid, gr.Tabs(selected=2)

    btn_confirm_video.click(
        fn=to_tab3,
        inputs=[out_video],
        outputs=[inp_video_step3, main_tabs]
    )

    # Step 3 - render finale
    btn_render.click(
        fn=generate_final_video,
        inputs=[
            state_video_url,
            state_session_id,
            l1_txt, l1_font,
            l2_txt, l2_font,
            l3_txt, l3_font,
            l4_txt, l4_font,
            l5_txt, l5_font,
            sl_x, sl_y,
            txt_foot
        ],
        outputs=[out_final, final_status]
    )

# ========================================
# AVVIO APP
# ========================================
if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True,
    )
