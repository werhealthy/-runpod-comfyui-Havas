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
import base64
import gradio as gr

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

import subprocess

def run_threaded_with_progress(progress, target_fn, estimated_seconds: int, desc: str):
    """
    Esegue target_fn in un thread e aggiorna progress fino a ~95% in estimated_seconds.
    Poi completa a 100%.
    """
    out = {"done": False, "result": None, "error": None}

    def _wrap():
        try:
            out["result"] = target_fn()
        except Exception as e:
            out["error"] = e
        finally:
            out["done"] = True

    t = threading.Thread(target=_wrap)
    t.start()

    start = time.time()
    while not out["done"]:
        elapsed = time.time() - start
        p = min(0.95, elapsed / max(1, estimated_seconds))
        progress(p, desc=f"{desc}... {int(p*100)}%")
        time.sleep(0.5)

    t.join()

    if out["error"]:
        raise out["error"]

    progress(1.0, desc="Fatto!")
    return out["result"]


def mp4_faststart(in_path: str, out_path: str) -> str:
    """
    Rende l'MP4 'streamabile' (moov atom in testa) → preview fluida in browser.
    Se fallisce, lascia il file originale.
    """
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", in_path, "-c", "copy", "-movflags", "+faststart", out_path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return out_path
    except Exception:
        return in_path

# ========================================
# CARICAMENTO FONT BaikalExp (BASE64)
# ========================================
FONT_PATH = "/tmp/comfyui/frontends/aliexpress/BaikalExp-Medium.otf"

with open(FONT_PATH, "rb") as f:
    BAIKAL_B64 = base64.b64encode(f.read()).decode("utf-8")

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
    
    # Barra di caricamento sincronizzata (25s circa)
    start_time = time.time()
    estimated_duration = 25
    
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
    
        # --- mapping dropdown -> flag tecnico per n8n + durata finta ---
        if "Kling" in (model_choice or ""):
            model_type = "kling"
            estimated_duration = 220   # 3m40s
        else:
            model_type = "svd"
            estimated_duration = 120   # 2m
    
        def call_n8n_video():
            # questa funzione viene eseguita in thread dal helper
            with open(selected_file, "rb") as f:
                files = {"data": (os.path.basename(selected_file), f, "image/png")}
                data = {
                    "prompt": video_prompt,
                    "session_id": current_id,
                    "model_type": model_type,
                }
                session = create_session()
                return session.post(N8N_VIDEO_URL, files=files, data=data, timeout=1200)
    
        # ✅ QUI avviene la “capsula” + progress finta sui secondi
        response = run_threaded_with_progress(
            progress=progress,
            target_fn=call_n8n_video,
            estimated_seconds=estimated_duration,
            desc=f"Generazione video ({model_type})"
        )
    
        # gestione errore
        if not response or response.status_code != 200:
            return None, None, f"❌ Err n8n ({response.status_code if response else '0'}): {response.text if response else ''}"
    
        progress(0.97, desc="Finalizzazione...")

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
        print(f"📡 Chiamata n8n: {N8N_FINAL_URL}")

        def call_n8n_final():
            session = create_session()
            return session.post(N8N_FINAL_URL, json=payload, timeout=900)
        
        response = run_threaded_with_progress(
            progress=progress,
            target_fn=call_n8n_final,
            estimated_seconds=55,
            desc="Render finale"
        )

        
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

:root{
  --brand-red: #E20800;
  --brand-black: #111111;

  --label-gray: #111827;
  --label-icon-gray: #6B7280;

  --page-gutter: 32px;
}

@font-face{
  font-family: "BaikalExp";
  src: url("data:font/otf;base64,REPLACE_ME") format("opentype");
  font-weight: 500;
  font-style: normal;
  font-display: swap;
}

#app-title{
  font-family: "BaikalExp", "DM Sans", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
  font-weight: 500 !important;
}

/* =========================
   BASE
   ========================= */
.gradio-container{
  font-family: "DM Sans", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;

  /* prova a disinnescare token Soft (aiuta, ma non basta) */
  --block-label-background-fill: transparent;
  --block-label-border-color: transparent;
  --block-label-text-color: var(--label-gray);
}

/* Placeholder più chiaro */
.gradio-container ::placeholder{
  color:#BCBCBC !important;
  opacity:1 !important;
}

/* =========================
   TABS: stesso gutter del titolo
   ========================= */
.gradio-container .tabs,
.gradio-container .tab-nav{
  padding-left: var(--page-gutter) !important;
  padding-right: var(--page-gutter) !important;
}

/* =========================
   HEADER / TITOLO (allineamento stabile)
   (questo era il metodo che ti funzionava)
   ========================= */
#app-title{
  display:block !important;
  width:100% !important;
  text-align:left !important;

  padding-left: var(--page-gutter) !important;
  padding-right: var(--page-gutter) !important;

  margin: 0 !important;
  font-size: 28px !important;
  letter-spacing: 0.04em !important;
  text-transform: uppercase !important;
  color: #1F2933 !important;
}

/* se qualche wrapper prova a centrare */
.gradio-container .prose h1,
.gradio-container .markdown h1,
.gradio-container .md h1{
  text-align:left !important;
  padding-left: var(--page-gutter) !important;
  padding-right: var(--page-gutter) !important;
}

/* =========================
   LOGO TOP-RIGHT FIXED
   ========================= */
#brand-logo-fixed{
  position: fixed;
  top: 14px;
  right: 18px;
  z-index: 9999;
  pointer-events: none;
}
#brand-logo-fixed img{
  height: 18px;
  width: auto;
  display: block;
  object-fit: contain;
}

/* =========================
   FIX CROP (Image/Gallery)
   ========================= */
.gradio-container .grid-wrap.fixed-height{
  height: auto !important;
  max-height: none !important;
  align-items: stretch !important;
}
.gradio-container .image-container img,
.gradio-container .gallery img,
.gradio-container .gallery-item img{
  object-fit: contain !important;
}
.gradio-container .image-container,
.gradio-container .gallery-item{
  overflow: hidden !important;
}

/* =========================
   LABELS (NO pill, NO rosso)
   SOLO titoli di Gradio (safe)
   ========================= */
.gradio-container :is(
  [data-testid="block-label"],
  [data-testid="block-title"],
  .gr-input-label,
  .gr-label,
  .block-title,
  .block-label
){
  background: transparent !important;
  border: 0 !important;
  box-shadow: none !important;
  border-radius: 0 !important;

  color: var(--label-gray) !important;
  font-weight: 500 !important;
  font-size: 14px !important;

  padding: 0 !important;
  margin: 0 0 6px 0 !important;

  display: inline-flex !important;
  align-items: center !important;
  gap: 10px !important; /* distanza icona-testo */
}

/* IL COLPEVOLE: lo span interno che diventa “pill” */
.gradio-container :is(
  [data-testid="block-label"],
  .gr-input-label,
  .gr-label,
  .block-label,
  .block-title
) > span{
  background: transparent !important;
  background-color: transparent !important;
  box-shadow: none !important;
  border: 0 !important;
  border-radius: 0 !important;

  color: var(--label-gray) !important;
  font-weight: 500 !important;

  padding: 0 !important;
  margin: 0 !important;
}

/* Icone (quando già presenti) */
.gradio-container :is(
  [data-testid="block-label"],
  .gr-input-label,
  .gr-label,
  .block-title,
  .block-label
) svg{
  width: 16px !important;
  height: 16px !important;
  color: var(--label-icon-gray) !important;
  margin-right: 6px !important; /* extra oltre gap */
}

/* =========================
   FIX MIRATO: DROPDOWN “Seleziona modello video”
   (qui la pill spesso sta in label-wrap e non su data-testid)
   ========================= */
.gradio-container .gr-dropdown .label-wrap,
.gradio-container .gr-dropdown .label-wrap *{
  background: transparent !important;
  background-color: transparent !important;
  box-shadow: none !important;
  border: 0 !important;
  border-radius: 0 !important;
}

/* in particolare: span interno del label del dropdown */
.gradio-container .gr-dropdown label > span,
.gradio-container .gr-dropdown .label-wrap label > span{
  background: transparent !important;
  background-color: transparent !important;
  box-shadow: none !important;
  border: 0 !important;
  border-radius: 0 !important;

  color: var(--label-gray) !important;
  font-weight: 500 !important;

  padding: 0 !important;
  margin: 0 !important;
}

/* =========================
   TABS selected
   ========================= */
.gradio-container .tab-nav button.selected,
.gradio-container .tabs button.selected{
  color: var(--brand-red) !important;
  border-color: var(--brand-red) !important;
}

/* =========================
   BOTTONI
   ========================= */
button.gr-button.primary,
.gr-button-primary{
  background-color: var(--brand-red) !important;
  border-color: var(--brand-red) !important;
  color: #ffffff !important;
  font-weight: 600 !important;
}
button.gr-button.primary:hover,
.gr-button-primary:hover{
  filter: brightness(0.92);
}
button.gr-button:not(.primary):not(.keep-red){
  background-color: #ffffff !important;
  color: var(--brand-black) !important;
  border: 1px solid #DDDDDD !important;
}

/* Aggiungi frase (perfetto + aggiungo “+”) */
.add-line-btn{
  background: #F9FAFB !important;
  color: #374151 !important;
  border: 1px solid #E5E7EB !important;
  border-radius: 10px !important;
  font-weight: 600 !important;
  padding: 10px 14px !important;
  box-shadow: none !important;
}
.add-line-btn::before{
  content:"+";
  margin-right: 10px;
  font-weight: 800;
}
.add-line-btn:hover{
  background: #F3F4F6 !important;
  border-color: #D1D5DB !important;
}
/* =========================
   RIGHE TESTO – SPACING
   ========================= */
.sentence-row{
  gap: 12px !important;
  margin-bottom: 12px !important;
  align-items: center !important;
}
/* Textbox frase: deve dominare la riga */
.sentence-row .gr-textbox,
.sentence-row input[type="text"],
.sentence-row textarea{
  flex: 1 1 auto !important;
  min-width: 0 !important;
}
/* Dropdown peso font: compatto e allineato */
.sentence-row .gr-dropdown{
  flex: 0 0 120px !important;
  min-width: 120px !important;
}
/* ===== Delete button: quadratino piccolo centrato ===== */
.delete-line-btn{
  flex: 0 0 32px !important;
  width: 32px !important;
  min-width: 32px !important;
  height: 32px !important;

  padding: 0 !important;
  margin: 0 10px !important;

  border-radius: 8px !important;
  background: #F3F4F6 !important;
  border: 1px solid #E5E7EB !important;

  color: #6B7280 !important;
  font-size: 18px !important;   /* X più leggibile */
  font-weight: 800 !important;

  display: flex !important;
  align-items: center !important;
  justify-content: center !important;

  line-height: 1 !important;
  box-shadow: none !important;
}

/* evita che Gradio la “allunghi” internamente */
.delete-line-btn > *{
  width: auto !important;
}
/* =========================
   SLIDER (thumb rosso; track nero/grigio lo fa il tuo JS)
   ========================= */
.gradio-container input[type="range"]{
  -webkit-appearance: none;
  appearance: none;
  background: #E5E5E5; /* fallback se JS non parte */
  border-radius: 999px;
  height: 6px;
}
.gradio-container input[type="range"]::-webkit-slider-thumb{
  -webkit-appearance: none;
  appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 999px;
  background: var(--brand-red);
  border: 3px solid #ffffff;
  box-shadow: 0 1px 2px rgba(0,0,0,.12);
  margin-top: -6px;
}
.gradio-container input[type="range"]::-moz-range-thumb{
  width: 18px;
  height: 18px;
  border-radius: 999px;
  background: var(--brand-red);
  border: 3px solid #ffffff;
  box-shadow: 0 1px 2px rgba(0,0,0,.12);
}
.gradio-container input[type="range"]::-moz-range-track{
  background: #E5E5E5;
  height: 6px;
  border-radius: 999px;
}
.gradio-container input[type="range"]::-moz-range-progress{
  background: #111111;
  height: 6px;
  border-radius: 999px;
}
/* =========================
   WHITE CARD WRAPPER
   ========================= */
.overlay-card{
  background: #FFFFFF !important;
  border-radius: 16px !important;
  padding: 16px !important;
  border: 1px solid #EEF0F3 !important;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04) !important;
}
/* =========================
   SECTION CHIP (like Nome prodotto)
   ========================= */
.section-chip{
  display: inline-block !important;
  background: #FDE2E1 !important;
  color: var(--brand-red) !important;
  padding: 6px 12px !important;
  border-radius: 10px !important;
  font-size: 14px !important;
  font-weight: 600 !important;
  margin: 0 0 12px 0 !important;
}
/* ===== Overlay testi: rimuovi “box grigio” dietro ogni riga ===== */
.overlay-card .sentence-row{
  background: transparent !important;
  box-shadow: none !important;
  border: 0 !important;
  padding: 0 !important;
}
.overlay-card .sentence-row > .gr-box{
  background: transparent !important;
  box-shadow: none !important;
  border: 0 !important;
}
/* =========================
   GENERA "rosso" anche se non-primary
   ========================= */
.btn-gen-red button{
  background-color: var(--brand-red) !important;
  border-color: var(--brand-red) !important;
  color: #ffffff !important;
  font-weight: 700 !important;
}

/* quando disabled, lo vogliamo chiaramente disabilitato */
.btn-gen-red button:disabled{
  opacity: 0.55 !important;
  cursor: not-allowed !important;
  filter: grayscale(0.2);
}
/* =========================
   BUTTON MODES (same component, different looks)
   ========================= */

/* PRIMARY LOOK (rosso) */
.btn-mode-primary button{
  background-color: var(--brand-red) !important;
  border-color: var(--brand-red) !important;
  color:#fff !important;
  font-weight:700 !important;
}

/* SECONDARY LOOK (bianco) */
.btn-mode-secondary button{
  background-color:#ffffff !important;
  border: 1px solid #DDDDDD !important;
  color: var(--brand-black) !important;
  font-weight:600 !important;
}

/* Disabled (vale per entrambi) */
.btn-mode-primary button:disabled,
.btn-mode-secondary button:disabled{
  opacity: 0.55 !important;
  cursor: not-allowed !important;
  filter: grayscale(0.1);
}
/* =========================
   FORCE BUTTON LOOK VIA elem_classes (Gradio 4–6)
   ========================= */

/* PRIMARY LOOK (rosso) */
.btn-mode-primary :is(button, .gr-button){
  background-color: var(--brand-red) !important;
  border-color: var(--brand-red) !important;
  color: #ffffff !important;
  font-weight: 700 !important;
}

/* SECONDARY LOOK (bianco) */
.btn-mode-secondary :is(button, .gr-button){
  background-color: #ffffff !important;
  border: 1px solid #DDDDDD !important;
  color: var(--brand-black) !important;
  font-weight: 600 !important;
}

/* Disabled */
.btn-mode-primary :is(button, .gr-button):disabled,
.btn-mode-secondary :is(button, .gr-button):disabled{
  opacity: 0.55 !important;
  cursor: not-allowed !important;
}

"""
custom_css = custom_css.replace("REPLACE_ME", BAIKAL_B64)

def img_to_data_uri(path: str) -> str:
    import base64
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


# =========================================================
# ✅ DEMO ROOT (MANCAVA) + STATES
# =========================================================
with gr.Blocks(theme=theme, css=custom_css) as demo:

    # ---- STATES (devono esistere prima dei componenti che li usano) ----
    state_session_id = gr.State()
    state_video_url = gr.State()
    state_filenames = gr.State()
    state_selected_file = gr.State()
    state_row_count = gr.State(value=1)

        
    # ---------- TOP BAR (TITLE + LOGO) ----------
    logo_src = img_to_data_uri("/tmp/comfyui/frontends/aliexpress/logo.png")

    gr.HTML(f"""
      <div id="brand-logo-fixed">
        <img src="{logo_src}" alt="Havas" />
      </div>
      <div id="app-title" style="margin-top:18px; margin-bottom:10px;">
        EXECUTIVE TOOL 001: ALIEXPRESS VIDEO
      </div>
    """)

    with gr.Tabs() as main_tabs:

        # =========================================================
        # TAB 1: IMMAGINE (NO SELECT, 1 OUTPUT, CTA SOTTO GENERA)
        # =========================================================
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

                    # ✅ DUE BOTTONI (ROBUSTO): primary -> hidden, secondary -> shown
                    with gr.Row():
                        btn_gen_img_primary = gr.Button(
                            "Genera",
                            variant="primary",
                            elem_classes=["keep-red"],  # bypass al tuo css not(.primary)
                            visible=True
                        )
                        btn_gen_img_secondary = gr.Button(
                            "Rigenera",
                            variant="secondary",
                            visible=False
                        )

                    # ✅ CTA successiva (nascosta finché non ho generato)
                    with gr.Row(visible=False) as next_cta_row_img:
                        btn_next_img = gr.Button(
                            "Conferma e vai al video",
                            variant="primary",
                            interactive=False
                        )

                    help_next_img = gr.Markdown("", visible=False)

                with gr.Column(scale=2):
                    out_gallery = gr.Gallery(
                        columns=1,
                        height="auto",
                        interactive=False,
                        label="Risultato generato"
                    )
                    status_msg = gr.Markdown("")


        # =========================================================
        # TAB 2: VIDEO (CTA SOTTO GENERA)
        # =========================================================
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
                            "Kling 1.5 Pro (High Quality - €0.50)",
                            "Fast SVD (Preview - €0.05)"
                        ],
                        value="Kling 1.5 Pro (High Quality - €0.50)",  # ✅ DEFAULT
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

                    # ✅ DUE BOTTONI (ROBUSTO): primary -> hidden, secondary -> shown
                    with gr.Row():
                        btn_gen_vid_primary = gr.Button(
                            "Genera",
                            variant="primary",
                            elem_classes=["keep-red"],
                            visible=True
                        )
                        btn_gen_vid_secondary = gr.Button(
                            "Rigenera",
                            variant="secondary",
                            visible=False
                        )

                    with gr.Row(visible=False) as next_cta_row_vid:
                        btn_next_vid = gr.Button(
                            "Conferma e vai ai testi",
                            variant="primary",
                            interactive=False
                        )

                    help_next_vid = gr.Markdown("", visible=False)

                with gr.Column(scale=2):
                    out_video = gr.Video(
                        height=450,
                        label="Anteprima video",
                        interactive=False
                    )
                    video_status = gr.Markdown("")


        # =========================================================
        # TAB 3: TESTI (RENDER + DOWNLOAD)
        # =========================================================
        with gr.Tab("Testi", id=2):
            with gr.Row():
                # -------- COLONNA SINISTRA — INPUT --------
                with gr.Column(scale=1):
                    inp_video_step3 = gr.Video(
                        label="Video base",
                        interactive=False,
                        height=200
                    )

                    with gr.Column(elem_classes=["overlay-card"]):

                        # ✅ niente Row intorno a HTML+Textbox (evita layout strani)
                        gr.HTML("<div class='section-chip'>Nome prodotto</div>")
                        txt_foot = gr.Textbox(
                            show_label=False,
                            placeholder="Nome prodotto"
                        )

                        gr.HTML("<div class='section-chip'>Overlay testi</div>")

                        # --- LOGICA RIGHE DINAMICHE ---
                        def hide_row_logic(current_count):
                            new_count = max(1, current_count - 1)
                            return gr.update(visible=False), "", "Normal", new_count

                        # RIGA 1 (no X, ma spacer)
                        with gr.Row(visible=True, variant="compact", elem_classes=["sentence-row"]) as r1:
                            l1_txt = gr.Textbox(placeholder="Frase 1", show_label=False, scale=7)
                            spacer_1 = gr.HTML("<div class='delete-line-spacer'></div>", show_label=False, scale=1)
                            l1_font = gr.Dropdown(["Bold", "Normal"], value="Bold", show_label=False, scale=2)

                        # RIGA 2
                        with gr.Row(visible=False, variant="compact", elem_classes=["sentence-row"]) as r2:
                            l2_txt = gr.Textbox(placeholder="Frase 2", show_label=False, scale=7)
                            btn_del_2 = gr.Button("×", size="sm", elem_classes=["delete-line-btn"], scale=1)
                            l2_font = gr.Dropdown(["Bold", "Normal"], value="Normal", show_label=False, scale=2)
                            btn_del_2.click(
                                fn=hide_row_logic,
                                inputs=[state_row_count],
                                outputs=[r2, l2_txt, l2_font, state_row_count]
                            )

                        # RIGA 3
                        with gr.Row(visible=False, variant="compact", elem_classes=["sentence-row"]) as r3:
                            l3_txt = gr.Textbox(placeholder="Frase 3", show_label=False, scale=7)
                            btn_del_3 = gr.Button("×", size="sm", elem_classes=["delete-line-btn"], scale=1)
                            l3_font = gr.Dropdown(["Bold", "Normal"], value="Normal", show_label=False, scale=2)
                            btn_del_3.click(
                                fn=hide_row_logic,
                                inputs=[state_row_count],
                                outputs=[r3, l3_txt, l3_font, state_row_count]
                            )

                        # RIGA 4
                        with gr.Row(visible=False, variant="compact", elem_classes=["sentence-row"]) as r4:
                            l4_txt = gr.Textbox(placeholder="Frase 4", show_label=False, scale=7)
                            btn_del_4 = gr.Button("×", size="sm", elem_classes=["delete-line-btn"], scale=1)
                            l4_font = gr.Dropdown(["Bold", "Normal"], value="Normal", show_label=False, scale=2)
                            btn_del_4.click(
                                fn=hide_row_logic,
                                inputs=[state_row_count],
                                outputs=[r4, l4_txt, l4_font, state_row_count]
                            )

                        # RIGA 5
                        with gr.Row(visible=False, variant="compact", elem_classes=["sentence-row"]) as r5:
                            l5_txt = gr.Textbox(placeholder="Frase 5", show_label=False, scale=7)
                            btn_del_5 = gr.Button("×", size="sm", elem_classes=["delete-line-btn"], scale=1)
                            l5_font = gr.Dropdown(["Bold", "Normal"], value="Normal", show_label=False, scale=2)
                            btn_del_5.click(
                                fn=hide_row_logic,
                                inputs=[state_row_count],
                                outputs=[r5, l5_txt, l5_font, state_row_count]
                            )

                        btn_add_row = gr.Button(
                            "Aggiungi frase",
                            size="sm",
                            elem_classes=["add-line-btn"]
                        )

                        def add_next_row(count):
                            if count >= 5:
                                return (gr.update(), gr.update(), gr.update(), gr.update(), count)
                            if count == 1:
                                return (gr.update(visible=True), gr.update(), gr.update(), gr.update(), 2)
                            if count == 2:
                                return (gr.update(), gr.update(visible=True), gr.update(), gr.update(), 3)
                            if count == 3:
                                return (gr.update(), gr.update(), gr.update(visible=True), gr.update(), 4)
                            if count == 4:
                                return (gr.update(), gr.update(), gr.update(), gr.update(visible=True), 5)
                            return (gr.update(), gr.update(), gr.update(), gr.update(), count)

                        btn_add_row.click(
                            fn=add_next_row,
                            inputs=[state_row_count],
                            outputs=[r2, r3, r4, r5, state_row_count]
                        )

                        sl_x = gr.Slider(0, 100, value=50, label="X testi")
                        sl_y = gr.Slider(0, 100, value=15, label="Y testi")

                        # ✅ DUE BOTTONI render (robusto)
                        with gr.Row():
                            btn_render_primary = gr.Button(
                                "Renderizza",
                                variant="primary",
                                elem_classes=["keep-red"],
                                visible=True
                            )
                            btn_render_secondary = gr.Button(
                                "Rigenera",
                                variant="secondary",
                                visible=False
                            )

                # -------- COLONNA DESTRA — OUTPUT --------
                with gr.Column(scale=1):
                    gr.Markdown("### Video finale")
                    out_final = gr.Video(
                        label="Output finale",
                        height=320,
                        interactive=False
                    )
                    final_status = gr.Markdown("")

                    with gr.Row(visible=False) as download_row:
                        btn_download = gr.DownloadButton(
                            "Scarica video",
                            variant="primary"
                        )


    # =========================================================
    # WIRING (TAB1 -> TAB2 -> TAB3)
    # =========================================================

    # -------------------------
    # STEP 1 — IMMAGINE
    # -------------------------
    def lock_img_ui():
        return (
            None,
            gr.update(interactive=False, value="Generazione..."),
            gr.update(interactive=False, value="Generazione..."),
            gr.update(visible=False),
            gr.update(visible=False, value=""),
            gr.update(value="")
        )

    def unlock_img_ui_after_success():
        return (
            gr.update(visible=False),  # hide primary
            gr.update(visible=True, interactive=True, value="Rigenera")  # show secondary
        )

    def after_generate_autopick(filenames, gallery):
        has_results = bool(gallery) and len(gallery) > 0 and bool(filenames) and len(filenames) > 0
        if not has_results:
            return (
                None,
                gr.update(visible=False),
                gr.update(interactive=False),
                gr.update(visible=False, value="")
            )
        selected = filenames[0]
        return (
            selected,
            gr.update(visible=True),
            gr.update(interactive=True),
            gr.update(visible=True, value="<span style='color:#111827'><b>Immagine pronta.</b> Puoi proseguire.</span>")
        )

    def to_tab2_guard(file):
        if not file:
            raise gr.Error("Nessuna immagine disponibile. Genera prima un'immagine.")
        return file, gr.Tabs(selected=1)

    # PRIMARY
    btn_gen_img_primary.click(
        fn=lock_img_ui,
        inputs=[],
        outputs=[
            state_selected_file,
            btn_gen_img_primary,
            btn_gen_img_secondary,
            next_cta_row_img,
            help_next_img,
            status_msg
        ]
    ).then(
        fn=generate_images,
        inputs=[inp_img, inp_prompt],
        outputs=[out_gallery, state_session_id, state_filenames, status_msg]
    ).then(
        fn=unlock_img_ui_after_success,
        inputs=[],
        outputs=[btn_gen_img_primary, btn_gen_img_secondary]
    ).then(
        fn=after_generate_autopick,
        inputs=[state_filenames, out_gallery],
        outputs=[state_selected_file, next_cta_row_img, btn_next_img, help_next_img]
    )

    # SECONDARY (rigenera)
    btn_gen_img_secondary.click(
        fn=lock_img_ui,
        inputs=[],
        outputs=[
            state_selected_file,
            btn_gen_img_primary,
            btn_gen_img_secondary,
            next_cta_row_img,
            help_next_img,
            status_msg
        ]
    ).then(
        fn=generate_images,
        inputs=[inp_img, inp_prompt],
        outputs=[out_gallery, state_session_id, state_filenames, status_msg]
    ).then(
        fn=unlock_img_ui_after_success,
        inputs=[],
        outputs=[btn_gen_img_primary, btn_gen_img_secondary]
    ).then(
        fn=after_generate_autopick,
        inputs=[state_filenames, out_gallery],
        outputs=[state_selected_file, next_cta_row_img, btn_next_img, help_next_img]
    )

    btn_next_img.click(
        fn=to_tab2_guard,
        inputs=[state_selected_file],
        outputs=[final_preview, main_tabs]
    )


    # -------------------------
    # STEP 2 — VIDEO
    # -------------------------
    def lock_vid_ui():
        return (
            gr.update(interactive=False, value="Generazione..."),
            gr.update(interactive=False, value="Generazione..."),
            gr.update(visible=False),
            gr.update(visible=False, value=""),
            gr.update(value="")
        )

    def unlock_vid_ui_after_success():
        return (
            gr.update(visible=False),
            gr.update(visible=True, interactive=True, value="Rigenera"),
        )

    def after_video_ready(video_path, video_url):
        ok = bool(video_url) and bool(video_path)
        if not ok:
            return (
                gr.update(visible=False),
                gr.update(interactive=False),
                gr.update(visible=False, value="")
            )
        return (
            gr.update(visible=True),
            gr.update(interactive=True),
            gr.update(visible=True, value="<span style='color:#111827'><b>Video pronto.</b> Puoi proseguire.</span>")
        )

    def to_tab3_guard(vid):
        if not vid:
            raise gr.Error("Genera prima un video.")
        return vid, gr.Tabs(selected=2)

    btn_gen_vid_primary.click(
        fn=lock_vid_ui,
        inputs=[],
        outputs=[btn_gen_vid_primary, btn_gen_vid_secondary, next_cta_row_vid, help_next_vid, video_status]
    ).then(
        fn=generate_video_base,
        inputs=[state_selected_file, state_session_id, video_prompt_input, video_model_selector],
        outputs=[out_video, state_video_url, video_status]
    ).then(
        fn=unlock_vid_ui_after_success,
        inputs=[],
        outputs=[btn_gen_vid_primary, btn_gen_vid_secondary]
    ).then(
        fn=after_video_ready,
        inputs=[out_video, state_video_url],
        outputs=[next_cta_row_vid, btn_next_vid, help_next_vid]
    )

    btn_gen_vid_secondary.click(
        fn=lock_vid_ui,
        inputs=[],
        outputs=[btn_gen_vid_primary, btn_gen_vid_secondary, next_cta_row_vid, help_next_vid, video_status]
    ).then(
        fn=generate_video_base,
        inputs=[state_selected_file, state_session_id, video_prompt_input, video_model_selector],
        outputs=[out_video, state_video_url, video_status]
    ).then(
        fn=unlock_vid_ui_after_success,
        inputs=[],
        outputs=[btn_gen_vid_primary, btn_gen_vid_secondary]
    ).then(
        fn=after_video_ready,
        inputs=[out_video, state_video_url],
        outputs=[next_cta_row_vid, btn_next_vid, help_next_vid]
    )

    btn_next_vid.click(
        fn=to_tab3_guard,
        inputs=[out_video],
        outputs=[inp_video_step3, main_tabs]
    )


    # -------------------------
    # STEP 3 — RENDER + DOWNLOAD
    # -------------------------
    def lock_render_ui():
        return (
            gr.update(interactive=False, value="Rendering..."),
            gr.update(interactive=False, value="Rendering..."),
            gr.update(visible=False),
            gr.update(value="")
        )

    def unlock_render_ui_after_success():
        return (
            gr.update(visible=False),
            gr.update(visible=True, interactive=True, value="Rigenera"),
        )

    def show_download(final_path):
        if not final_path:
            return gr.update(visible=False), None
        return gr.update(visible=True), final_path

    btn_render_primary.click(
        fn=lock_render_ui,
        inputs=[],
        outputs=[btn_render_primary, btn_render_secondary, download_row, final_status]
    ).then(
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
    ).then(
        fn=unlock_render_ui_after_success,
        inputs=[],
        outputs=[btn_render_primary, btn_render_secondary]
    ).then(
        fn=show_download,
        inputs=[out_final],
        outputs=[download_row, btn_download]
    )

    btn_render_secondary.click(
        fn=lock_render_ui,
        inputs=[],
        outputs=[btn_render_primary, btn_render_secondary, download_row, final_status]
    ).then(
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
    ).then(
        fn=unlock_render_ui_after_success,
        inputs=[],
        outputs=[btn_render_primary, btn_render_secondary]
    ).then(
        fn=show_download,
        inputs=[out_final],
        outputs=[download_row, btn_download]
    )


# ========================================
# AVVIO APP
# ========================================
if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True,
        allowed_paths=[
            "/tmp/comfyui/frontends/aliexpress",   # logo ecc
            "/tmp/comfyui/fonts",                  # <-- directory del font
            "/tmp/comfyui/progetti",               # ✅ per DownloadButton
        ],
    )
