"""
🛍️ AI Campaign Manager - Gradio Frontend (REWRITTEN FOR 3-WORLD ARCHITECTURE)
"""

import gradio as gr
import requests
import os
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ========================================
# ⚙️ CONFIGURAZIONE E COSTANTI
# ========================================

# URL dei Webhook di n8n
# NOTA: Assicurati che questi URL siano accessibili pubblicamente da RunPod
N8N_IMAGES_URL = "http://127.0.0.1:5678/webhook/generate-images-2" 
N8N_FINAL_URL  = "http://127.0.0.1:5678/webhook/generate-final-video"

# Cartella temporanea locale (Solo per Gradio su Linux)
BASE_OUTPUT_DIR = "/tmp/gradio_output"
os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)

# URL VIDEO DI TEST (Il nostro "Unicorno" per il debug)
DEBUG_VIDEO_URL = "https://storage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"

# ========================================
# 🔧 UTILS & SESSIONI
# ========================================

def create_session():
    """Crea una sessione HTTP robusta con retry automatici."""
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# ========================================
# 📸 STEP 1: IMMAGINI (Con Barra Sincronizzata 60s)
# ========================================

def generate_images(image_path, prompt, progress=gr.Progress(track_tqdm=True)):
    import io, base64, json
    from PIL import Image
    import threading
    import os
    import time
    
    # 1. Setup Iniziale
    if not os.path.exists(BASE_OUTPUT_DIR):
        os.makedirs(BASE_OUTPUT_DIR)

    if not image_path: return [], None, [], "⚠️ Errore: Carica un'immagine!"
    
    # Partiamo da 0% esatto
    progress(0.0, desc="Preparazione dati...")
    
    # 2. Preparazione Immagine
    try:
        img = Image.open(image_path)
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=95)
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    except Exception as e:
        return [], None, [], f"❌ Errore preparazione file: {str(e)}"
    
    # 3. Chiamata API (Thread separato)
    api_response = {}
    
    def call_n8n():
        try:
            session = create_session()
            # Timeout aumentato a 600s per sicurezza lato server
            resp = session.post(N8N_IMAGES_URL, json={"prompt": prompt, "image": img_base64}, timeout=600)
            api_response['data'] = resp
        except Exception as err:
            api_response['error'] = err

    t = threading.Thread(target=call_n8n)
    t.start()
    
    # --- BARRA DI CARICAMENTO CALIBRATA (60 SECONDI) ---
    start_time = time.time()
    estimated_duration = 60.0  # Durata stimata in secondi
    
    while t.is_alive():
        # Calcoliamo quanto tempo è passato
        elapsed = time.time() - start_time
        
        # Calcoliamo la percentuale (Tempo passato / 60 secondi)
        # Esempio: se sono passati 30s, siamo al 50% (0.5)
        current_prog = elapsed / estimated_duration
        
        # Blocchiamo la barra al 95% finché n8n non finisce davvero
        # (Così non arriva mai al 100% prima che il file sia pronto)
        if current_prog > 0.95:
            current_prog = 0.95
            
        progress(current_prog, desc=f"Generazione in corso... {int(current_prog*100)}%")
        time.sleep(0.5) # Aggiorniamo ogni mezzo secondo
        
    t.join() 
    # ---------------------------------------------------

    # 4. Controllo Risultato
    if 'error' in api_response:
        return [], None, [], f"❌ Errore Connessione: {str(api_response['error'])}"
        
    response = api_response.get('data')
    if not response:
        return [], None, [], "❌ Nessuna risposta dal server."
        
    if response.status_code != 200: 
        return [], None, [], f"❌ Errore n8n ({response.status_code}): {response.text[:100]}"
        
    # 5. Decodifica Immagini
    try:
        progress(0.97, desc="Scaricamento immagini...")
        result = response.json()
        images_raw = result.get("images", [])
        
        if not images_raw:
            return [], None, [], f"⚠️ n8n ha risposto OK, ma senza immagini."

        output_images = []
        filenames_list = []

        for i, item in enumerate(images_raw):
            try:
                b64_str = item if isinstance(item, str) else item.get('data')
                if b64_str:
                    img_bytes = base64.b64decode(b64_str)
                    image = Image.open(io.BytesIO(img_bytes))
                    output_images.append(image)
                    
                    fname = f"gen_{int(time.time())}_{i}.png"
                    local_path = os.path.join(BASE_OUTPUT_DIR, fname)
                    image.save(local_path)
                    filenames_list.append(local_path)
            except Exception:
                pass 

        if not output_images:
            return [], None, [], "❌ Errore visualizzazione immagini."

        # Solo alla fine andiamo al 100%
        progress(1.0, desc="Fatto!")
        return output_images, result.get("session_id", "sess"), filenames_list, f"✅ Successo! {len(output_images)} immagini."
        
    except Exception as e:
        return [], None, [], f"❌ Errore finale: {str(e)}"

# ========================================
# 🎬 STEP 2: VIDEO BASE (VERSIONE REALE CHE AGGIORNA LA MEMORIA)
# ========================================

def generate_video_base(selected_file, session_id, video_prompt, progress=gr.Progress(track_tqdm=True)):
    print(f"🚀 [STEP 2] Avvio Generazione Video FAL...")
    
    if not selected_file: return None, None, "⚠️ Errore: Nessuna immagine selezionata."
    
    # URL del Webhook di n8n (Assicurati che sia quello giusto!)
    N8N_VIDEO_URL = "http://127.0.0.1:5678/webhook/generate-video" 

    try:
        progress(0.1, desc="Invio file a n8n...")
        
        # 1. Upload e Richiesta a n8n
        # Inviamo l'immagine fisica + il prompt
        with open(selected_file, 'rb') as f:
            files = {'data': (os.path.basename(selected_file), f, 'image/png')}
            data = {'prompt': video_prompt, 'session_id': session_id}
            
            session = create_session()
            response = session.post(N8N_VIDEO_URL, files=files, data=data, timeout=600)
        
        if response.status_code != 200:
            return None, None, f"❌ Errore n8n ({response.status_code}): {response.text}"
            
        # 2. LEGGIAMO L'URL VERO DI FAL.AI
        result = response.json()
        remote_video_url = result.get("video_url")
        
        if not remote_video_url:
            return None, None, f"❌ Errore: n8n non ha restituito l'URL. Risposta: {result}"
            
        print(f"✅ URL VERO da passare allo Step 3: {remote_video_url}")
        
        # 3. Scarichiamo l'anteprima per te (solo visuale)
        progress(0.9, desc="Scaricamento anteprima...")
        local_filename = f"video_preview_{int(time.time())}.mp4"
        local_path = os.path.join(BASE_OUTPUT_DIR, local_filename)
        
        try:
            video_data = requests.get(remote_video_url).content
            with open(local_path, 'wb') as f_vid:
                f_vid.write(video_data)
        except Exception as e:
            print(f"⚠️ Anteprima fallita, ma URL valido: {e}")

        # --- IL PUNTO CRUCIALE ---
        # Restituiamo:
        # 1. local_path -> Per i tuoi occhi (Player)
        # 2. remote_video_url -> Per la Memoria (Step 3)
        return local_path, remote_video_url, "✅ Video Generato e Pronto per il Render!"

    except Exception as e:
        print(f"❌ Errore critico: {e}")
        return None, None, f"❌ Errore: {str(e)}"

# ========================================
# ✍️ STEP 3: VIDEO FINALE (RENDER VIA N8N -> WINDOWS)
# ========================================

def generate_final_video(base_video_url_state, # <--- PRENDE INPUT DALLO STATO!
                         l1_text, l1_font, 
                         l2_text, l2_font, 
                         l3_text, l3_font, 
                         l4_text, l4_font, 
                         l5_text, l5_font, 
                         x_head, y_head, 
                         text_foot, 
                         progress=gr.Progress()):
    
    print(f"\n🚀 [STEP 3] Richiesta Render Iniziata")
    print(f"   URL Input dallo State: {base_video_url_state}")
    
    # 1. CONTROLLI DI SICUREZZA "3 MONDI"
    if not base_video_url_state:
        return None, "❌ Errore: Nessun video selezionato. Esegui lo Step 2."
    
    # Se per errore arriva un path locale (/tmp/...), blocchiamo tutto.
    # Il server Windows non può leggere /tmp/ di RunPod.
    if str(base_video_url_state).startswith("/tmp") or not str(base_video_url_state).startswith("http"):
        print("❌ ERRORE CRITICO: Trovato path locale invece di URL remoto.")
        return None, "❌ Errore Tecnico: Il sistema ha perso l'URL remoto. Ricarica la pagina e riprova."

    progress(0.1, desc="Preparazione Dati...")
    
    # 2. PREPARAZIONE PAYLOAD (Struttura pulita per n8n)
    hero_lines = []
    def add_line(text, font):
        return { "text": text.strip() if text else "", "is_bold": (font == "Bold") }

    hero_lines.append(add_line(l1_text, l1_font))
    hero_lines.append(add_line(l2_text, l2_font))
    hero_lines.append(add_line(l3_text, l3_font))
    hero_lines.append(add_line(l4_text, l4_font))
    hero_lines.append(add_line(l5_text, l5_font))

    payload = {
        "video_url": base_video_url_state, # Passiamo l'URL puro
        "product_name": text_foot.strip() if text_foot else "",
        "hero_lines": hero_lines,
        "x_head": x_head, # Opzionali, se il server li gestisce
        "y_head": y_head
    }
    
    # 3. CHIAMATA N8N (Che fa da ponte verso Windows)
    try:
        progress(0.3, desc="Rendering remoto in corso (attendi)...")
        session = create_session()
        
        # Invio richiesta JSON
        print(f"📡 Invio a n8n: {N8N_FINAL_URL}")
        # Timeout alto (300s) perché After Effects è lento
        response = session.post(N8N_FINAL_URL, json=payload, timeout=300)
        
        if response.status_code != 200:
            return None, f"❌ Errore Server ({response.status_code}): {response.text}"
        
        # 4. GESTIONE RISPOSTA BINARIA
        # n8n deve restituire un file BINARIO (video), non JSON.
        if not response.content:
            return None, "❌ Errore: Il server ha risposto ma il contenuto è vuoto."

        progress(0.8, desc="Scaricamento video finale...")
        
        # Salviamo il risultato nel filesystem locale di Gradio (Linux) SOLO per la visualizzazione
        output_filename = f"final_render_{int(time.time())}.mp4"
        output_path = os.path.join(BASE_OUTPUT_DIR, output_filename)
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
            
        print(f"✅ Video salvato localmente per preview: {output_path}")
        progress(1.0, desc="Fatto!")
        
        return output_path, "✅ Video Renderizzato con Successo!"

    except Exception as e:
        print(f"❌ Eccezione durante render: {e}")
        return None, f"❌ Errore Connessione: {str(e)}"

# ========================================
# 🎨 INTERFACCIA UTENTE (UI)
# ========================================

with gr.Blocks(title="AI Campaign Manager (Debug Mode)") as demo:
    
    # --- VARIABILI DI STATO (MEMORIA) ---
    # state_video_url: La "Verità" per il flusso dati (contiene l'URL https://...)
    state_video_url = gr.State()
    
    # Altri stati
    state_session_id = gr.State()
    state_filenames = gr.State()
    state_selected_file = gr.State()
    state_row_count = gr.State(value=1)

    gr.Markdown("# 🛍️ Generatore Campagne AI (Modalità Debug 🦄)")
    
    with gr.Tabs() as main_tabs:
        
        # --- TAB 1: VARIANTI (Immagini) ---
        with gr.Tab("1. Varianti", id=0):
            with gr.Row():
                with gr.Column(scale=1):
                    inp_img = gr.Image(type="filepath", height=300, label="Input Immagine")
                    inp_prompt = gr.Textbox(label="Prompt", lines=3)
                    btn_gen_img = gr.Button("🚀 Genera Immagini", variant="primary")
                with gr.Column(scale=2):
                    out_gallery = gr.Gallery(columns=3, height="auto", interactive=False)
                    status_msg = gr.Markdown("Pronto")
            
            with gr.Row(visible=False) as confirm_section:
                with gr.Column():
                    selected_preview = gr.Image(label="Selezionata", interactive=False, height=300)
                    btn_confirm = gr.Button("✅ Conferma e Vai a Video", variant="primary")

        # --- TAB 2: VIDEO BASE (Debug URL) ---
        with gr.Tab("2. Video Base", id=1):
            with gr.Row():
                with gr.Column(scale=1):
                    final_preview = gr.Image(interactive=True, height=300, label="Anteprima Immagine", type="filepath")
                    video_prompt_input = gr.Textbox(label="Prompt Video", value="Test video prompt", lines=3)
                    
                    gr.Markdown("ℹ️ **Nota Debug:** In questa modalità, il sistema userà un video di test remoto (Google Storage) invece di generare con Fal.ai.")
                    btn_gen_vid = gr.Button("✨ Genera Video Base (TEST)", variant="primary")
                
                with gr.Column(scale=2):
                    # Questo player mostra il video, ma il suo valore NON deve essere passato al backend
                    out_video = gr.Video(height=450, label="Video Base (Preview)", interactive=False)
                    video_status = gr.Markdown("")
            
            with gr.Row(visible=False) as video_confirm_section:
                btn_confirm_video = gr.Button("✅ Video OK? Vai ai Testi", variant="primary")

        # --- TAB 3: TESTI & RENDER ---
        with gr.Tab("3. Testi", id=2):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### ✍️ Configurazione After Effects")
                    
                    # Video di riferimento visivo (Input disabilitato)
                    inp_video_step3 = gr.Video(label="Video Base Selezionato", interactive=False, height=200)

                    # Campi Testo Dinamici
                    def hide_row(): return gr.update(visible=False), "", "Bold"
                    
                    # Riga 1 (Sempre visibile)
                    with gr.Row(visible=True, variant="compact"):
                        l1_txt = gr.Textbox(placeholder="Frase 1...", show_label=False, container=False, scale=5)
                        l1_font = gr.Dropdown(["Bold", "Normal"], value="Bold", show_label=False, container=False, scale=2)

                    # Righe 2-5 (Nascoste inizialmente)
                    # (Codice ripetitivo per UI compatto, mantenuto per fedeltà al design originale)
                    with gr.Row(visible=False, variant="compact") as r2:
                        l2_txt = gr.Textbox(placeholder="Frase 2...", show_label=False, container=False, scale=5)
                        l2_font = gr.Dropdown(["Bold", "Normal"], value="Normal", show_label=False, container=False, scale=2)
                        btn_del_2 = gr.Button("✖", size="sm", scale=1, variant="secondary")
                        btn_del_2.click(fn=hide_row, outputs=[r2, l2_txt, l2_font])

                    with gr.Row(visible=False, variant="compact") as r3:
                        l3_txt = gr.Textbox(placeholder="Frase 3...", show_label=False, container=False, scale=5)
                        l3_font = gr.Dropdown(["Bold", "Normal"], value="Normal", show_label=False, container=False, scale=2)
                        btn_del_3 = gr.Button("✖", size="sm", scale=1, variant="secondary")
                        btn_del_3.click(fn=hide_row, outputs=[r3, l3_txt, l3_font])
                        
                    with gr.Row(visible=False, variant="compact") as r4:
                        l4_txt = gr.Textbox(placeholder="Frase 4...", show_label=False, container=False, scale=5)
                        l4_font = gr.Dropdown(["Bold", "Normal"], value="Normal", show_label=False, container=False, scale=2)
                        btn_del_4 = gr.Button("✖", size="sm", scale=1, variant="secondary")
                        btn_del_4.click(fn=hide_row, outputs=[r4, l4_txt, l4_font])

                    with gr.Row(visible=False, variant="compact") as r5:
                        l5_txt = gr.Textbox(placeholder="Frase 5...", show_label=False, container=False, scale=5)
                        l5_font = gr.Dropdown(["Bold", "Normal"], value="Normal", show_label=False, container=False, scale=2)
                        btn_del_5 = gr.Button("✖", size="sm", scale=1, variant="secondary")
                        btn_del_5.click(fn=hide_row, outputs=[r5, l5_txt, l5_font])
                    
                    gr.HTML("<div style='height: 10px'></div>")
                    btn_add_row = gr.Button("+ Aggiungi Frase", size="sm")
                    
                    def add_row_logic(count):
                        c = min(count + 1, 5)
                        return (c, gr.update(visible=True) if c>=2 else gr.update(), 
                                gr.update(visible=True) if c>=3 else gr.update(), 
                                gr.update(visible=True) if c>=4 else gr.update(), 
                                gr.update(visible=True) if c>=5 else gr.update())

                    btn_add_row.click(fn=add_row_logic, inputs=[state_row_count], outputs=[state_row_count, r2, r3, r4, r5])

                    with gr.Group():
                        gr.Markdown("#### 📍 Posizione e Footer")
                        with gr.Row():
                            sl_x_head = gr.Slider(0, 100, value=50, label="X Testi")
                            sl_y_head = gr.Slider(0, 100, value=15, label="Y Testi")
                        txt_foot = gr.Textbox(label="Nome Prodotto", show_label=True)

                    btn_render_final = gr.Button("🎬 Renderizza (Windows Server)", variant="primary", size="lg")

                with gr.Column(scale=2):
                    out_final_video = gr.Video(label="Risultato Finale", height=450)
                    final_status = gr.Markdown("")

    # ========================================
    # EVENTI & LOGICA FLUSSO
    # ========================================
    
    # 1. GENERAZIONE IMMAGINI
    btn_gen_img.click(
        fn=generate_images, 
        inputs=[inp_img, inp_prompt], 
        outputs=[out_gallery, state_session_id, state_filenames, status_msg]
    )
    
    # Selezione immagine
    def on_select(filenames, evt: gr.SelectData):
        if not filenames: return None, gr.update(visible=False), None
        s = filenames[evt.index]
        return s, gr.update(visible=True), s

    out_gallery.select(fn=on_select, inputs=[state_filenames], outputs=[state_selected_file, confirm_section, selected_preview])
    
    # Conferma Step 1
    def confirm_step1(selected_file):
        if not selected_file: return None, "Seleziona immagine!", gr.Tabs()
        return selected_file, "Clicca 'Genera Video Base' per iniziare.", gr.Tabs(selected=1)

    btn_confirm.click(fn=confirm_step1, inputs=[state_selected_file], outputs=[final_preview, video_status, main_tabs])
    selected_preview.change(fn=lambda x: x, inputs=[selected_preview], outputs=[final_preview])
    
    # 2. GENERAZIONE VIDEO BASE (SCOLLEGATO IL DEBUG, COLLEGATO IL REALE)
    gen_vid_event = btn_gen_vid.click(
        fn=generate_video_base,  # <--- Usa la nuova funzione senza "_debug"
        inputs=[state_selected_file, state_session_id, video_prompt_input], 
        outputs=[out_video, state_video_url, video_status]
    )
    
    def on_video_generated(video_url, status):
        # Mostra il pulsante di conferma solo se abbiamo un URL
        return gr.update(visible=bool(video_url))

    gen_vid_event.then(fn=on_video_generated, inputs=[state_video_url, video_status], outputs=[video_confirm_section])
    
    # Conferma Step 2
    def confirm_step2(video_url):
        # Passiamo l'URL anche al player visivo del tab successivo (solo per estetica)
        return video_url, gr.Tabs(selected=2)

    btn_confirm_video.click(fn=confirm_step2, inputs=[out_video], outputs=[inp_video_step3, main_tabs])
    
    # 3. RENDER FINALE (LOGICA CORRETTA)
    # NOTA BENE: Qui prendiamo state_video_url come input, NON out_video!
    # Questo assicura che al backend arrivi l'URL puro e non il path locale.
    btn_render_final.click(
        fn=generate_final_video, 
        inputs=[
            state_video_url, # <--- IMPORTANTE: Usiamo lo STATO!
            l1_txt, l1_font,
            l2_txt, l2_font,
            l3_txt, l3_font,
            l4_txt, l4_font,
            l5_txt, l5_font,
            sl_x_head, sl_y_head, 
            txt_foot
        ],
        outputs=[out_final_video, final_status]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7861, share=True)