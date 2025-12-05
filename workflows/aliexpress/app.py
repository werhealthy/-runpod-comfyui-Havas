"""
🛍️ AI Campaign Manager - Gradio Frontend
"""

import gradio as gr
import requests
import os
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ========================================
# ⚙️ CONFIGURAZIONE
# ========================================

N8N_IMAGES_URL = "http://127.0.0.1:5678/webhook/generate-images-2"
N8N_VIDEO_URL  = "http://127.0.0.1:5678/webhook/generate-video"
N8N_FINAL_URL  = "http://127.0.0.1:5678/webhook/generate-final-video"

BASE_OUTPUT_DIR = "/tmp/comfyui"

# ========================================
# 🔧 SESSIONE REQUESTS
# ========================================

def create_session():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# ========================================
# 📸 STEP 1: IMMAGINI
# ========================================

def generate_images(image_path, prompt, progress=gr.Progress()):
    import io, base64
    from PIL import Image
    import numpy as np
    
    if not image_path: return [], None, [], "⚠️ Carica immagine!"
    if not prompt: return [], None, [], "⚠️ Scrivi prompt!"
    
    try:
        img = Image.open(image_path)
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=95)
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    except Exception as e:
        return [], None, [], f"❌ Errore img: {str(e)}"
    
    try:
        session = create_session()
        response = session.post(N8N_IMAGES_URL, json={"prompt": prompt, "image": img_base64}, timeout=600)
        
        if response.status_code != 200: return [], None, [], f"❌ Errore n8n: {response.text}"
        
        result = response.json()
        if isinstance(result, list): result = result[0] if len(result) > 0 else {}
        if not result.get("success"): return [], None, [], f"❌ Errore workflow: {result.get('error')}"
        
        output_images = []
        filenames_list = []
        for img_meta in result.get("images", []):
            fname = img_meta.get("filename")
            sub = img_meta.get("subfolder", "")
            path = os.path.join(BASE_OUTPUT_DIR, "output" if img_meta.get("type")=="output" else img_meta.get("type"), sub, fname)
            if os.path.exists(path):
                try:
                    output_images.append(np.array(Image.open(path)))
                    filenames_list.append(path)
                except: pass
                
        return output_images, result.get("session_id"), filenames_list, f"✅ Generate {len(output_images)} immagini"
    except Exception as e:
        return [], None, [], f"❌ Errore: {str(e)}"

# ========================================
# 🎬 STEP 2: VIDEO BASE (AGGIORNATO PER PROMPT API)
# ========================================

def generate_video_base(selected_file, session_id, video_prompt, progress=gr.Progress()):
    """
    Funzione di generazione Video Base che invia il Prompt alla Webhook N8n (Fal.ai).
    """
    # 1. Pulizia e Controlli
    if not selected_file:
        return None, "⚠️ Errore: Nessuna immagine selezionata."
    
    # 2. Estrazione del percorso e del nome
    # 'selected_file' in questo punto contiene il percorso completo /tmp/.../nome.png
    image_path = selected_file
    clean_filename = os.path.basename(image_path)
    
    # 3. Gestione Sessione (per il salvataggio del video)
    # Se session_id è None (memoria persa), usiamo una stringa vuota per cercare nella root (vedi fix N8n)
    if not session_id:
        print("⚠️ Session ID mancante. Uso ID temporaneo per l'output.")
        session_id = "" 
    
    if not clean_filename:
        return None, "❌ Errore: Nome file non valido."
    
    # 4. Payload per N8n (invia Promt Video a Fal.ai)
    payload = {
        "session_id": session_id,
        # La funzione N8n si aspetta solo il nome pulito, il percorso completo non serve più
        "image_filename": clean_filename,
        "prompt": video_prompt  # <--- NUOVO PROMPT VIDEO
    }

    try:
        session = create_session()
        response = session.post(N8N_VIDEO_URL, json=payload, timeout=600)
        
        if response.status_code != 200:
            return None, f"❌ Errore n8n: {response.text}"
            
        # 5. Verifica e Salvataggio (Assumiamo che il video ritorni in formato binario/file)
        expected_output_name = f"video_{clean_filename}" # Nome con suffisso video_
        
        # Salvataggio del video scaricato nel percorso corretto
        base_dir = os.path.join(BASE_OUTPUT_DIR, "output")
        output_dir = os.path.join(base_dir, session_id) if session_id else base_dir
        os.makedirs(output_dir, exist_ok=True)
        
        final_video_path = os.path.join(output_dir, expected_output_name)
        
        if len(response.content) > 1000:
            with open(final_video_path, 'wb') as f:
                f.write(response.content)
            return final_video_path, f"✅ Video Scaricato ({len(response.content)//1024} KB)"
        
        return None, "❌ Video non ricevuto da N8n. Controlla i log."
        
    except Exception as e:
        return None, f"❌ Errore API: {str(e)}"

# ========================================
# ✍️ STEP 3: VIDEO FINALE (Con Calcolo Larghezza)
# ========================================

def generate_final_video(base_video_path, 
                         l1_text, l1_font, 
                         l2_text, l2_font, 
                         l3_text, l3_font, 
                         l4_text, l4_font, 
                         l5_text, l5_font, 
                         x_head, y_head, 
                         text_foot, x_foot, y_foot, 
                         progress=gr.Progress()):
    
    if not base_video_path:
        return None, "❌ Nessun video base caricato"

    print(f"\n{'='*50}")
    print(f"🎨 INIZIO POST-PRODUZIONE")
    
    # 1. Mappa Font
    font_map = {
        "Bold": "/tmp/comfyui/AliExpress sans.otf", 
        "Normal": "/tmp/comfyui/AliExpress sans regluar.otf"
    }
    
    # 2. Funzione Pulizia Testo
    def cln(t): return t.strip() if t and t.strip() else " "
    
    # 3. CALCOLO LARGHEZZA RETTANGOLO (Nuova Parte)
    # Pulisci il footer
    clean_foot = cln(text_foot)
    # Calcola i pixel: (Numero caratteri * 26px) + 80px di margine. Se vuoto = 0.
    box_width = (len(clean_foot) * 26) + 80 if clean_foot != " " else 0
    
    output_name = f"final_{int(time.time())}.mp4"
    
    # 4. Payload con il nuovo parametro 'box_width'
    payload = {
        "input_video": base_video_path, "output_name": output_name,
        "x_head": x_head, "y_head": y_head, 
        "text_foot": clean_foot, "x_foot": x_foot, "y_foot": y_foot,
        
        "box_width": box_width,  # <--- ECCOLO QUI!
        
        "l1_text": cln(l1_text), "l1_font": font_map.get(l1_font, font_map["Bold"]),
        "l2_text": cln(l2_text), "l2_font": font_map.get(l2_font, font_map["Normal"]),
        "l3_text": cln(l3_text), "l3_font": font_map.get(l3_font, font_map["Normal"]),
        "l4_text": cln(l4_text), "l4_font": font_map.get(l4_font, font_map["Normal"]),
        "l5_text": cln(l5_text), "l5_font": font_map.get(l5_font, font_map["Normal"]),
    }
    
    try:
        session = create_session()
        response = session.post(N8N_FINAL_URL, json=payload, timeout=300)
        expected = os.path.join(BASE_OUTPUT_DIR, "output", output_name)
        time.sleep(1)
        if os.path.exists(expected): return expected, "✅ Video Finale Completato!"
        return None, f"❌ Errore n8n: {response.text}"
    except Exception as e:
        return None, f"❌ Errore: {str(e)}"

# ========================================
# 🎨 INTERFACCIA
# ========================================

with gr.Blocks(title="AI Campaign Manager") as demo:
    
    # Stati
    state_session_id = gr.State()
    state_filenames = gr.State()
    state_selected_file = gr.State()
    state_row_count = gr.State(value=1)

    gr.Markdown("# 🛍️ Generatore Campagne AI")
    
    with gr.Tabs() as main_tabs:
        
        # TAB 1: Varianti
        with gr.Tab("1. Varianti", id=0):
            with gr.Row():
                with gr.Column(scale=1):
                    inp_img = gr.Image(type="filepath", height=300, label="Input Immagine")
                    inp_prompt = gr.Textbox(label="Prompt", lines=3)
                    btn_gen_img = gr.Button("🚀 Genera", variant="primary")
                with gr.Column(scale=2):
                    out_gallery = gr.Gallery(columns=3, height="auto", interactive=False)
                    status_msg = gr.Markdown("Pronto")
            
            with gr.Row(visible=False) as confirm_section:
                with gr.Column():
                    selected_preview = gr.Image(label="Selezionata", interactive=False, height=300)
                    btn_confirm = gr.Button("✅ Conferma e Vai a Video", variant="primary")

        # TAB 2: Video Base (CORRETTO)
        with gr.Tab("2. Video Base", id=1):
            with gr.Row():
                with gr.Column(scale=1):
                    # Preview interattiva per passare il file
                    final_preview = gr.Image(interactive=True, height=300, label="Anteprima", type="filepath")
                    
                    # Prompt Video
                    video_prompt_input = gr.Textbox(
                        label="Prompt per il Video",
                        placeholder="Es: Zoom lento, movimento laterale...",
                        value="Slow cinematic zoom in, high quality product video, 4k, advertising style",
                        lines=3
                    )
                    
                    btn_gen_vid = gr.Button("✨ Genera Video Base", variant="primary")
                
                with gr.Column(scale=2):
                    out_video = gr.Video(height=450, label="Video Base", interactive=False)
                    video_status = gr.Markdown("")
            
            with gr.Row(visible=False) as video_confirm_section:
                btn_confirm_video = gr.Button("✅ Video OK? Vai ai Testi", variant="primary")

        # TAB 3: Testi
        with gr.Tab("3. Testi", id=2):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### ✍️ Storytelling")
                    inp_video_step3 = gr.Video(label="Base", interactive=False, visible=True, height=200)

                    with gr.Group():
                        gr.Markdown("#### 📝 Frasi (Sequenza)")
                        with gr.Row(visible=True) as r1:
                            l1_txt = gr.Textbox(label="Frase 1 (0.5s)", placeholder="Testo...")
                            l1_font = gr.Dropdown(["Bold", "Normal"], value="Bold", label="Font")
                        with gr.Row(visible=False) as r2:
                            l2_txt = gr.Textbox(label="Frase 2 (1.5s)", placeholder="Testo...")
                            l2_font = gr.Dropdown(["Bold", "Normal"], value="Bold", label="Font")
                        with gr.Row(visible=False) as r3:
                            l3_txt = gr.Textbox(label="Frase 3 (2.5s)", placeholder="Testo...")
                            l3_font = gr.Dropdown(["Bold", "Normal"], value="Normal", label="Font")
                        with gr.Row(visible=False) as r4:
                            l4_txt = gr.Textbox(label="Frase 4 (3.5s)", placeholder="Testo...")
                            l4_font = gr.Dropdown(["Bold", "Normal"], value="Normal", label="Font")
                        with gr.Row(visible=False) as r5:
                            l5_txt = gr.Textbox(label="Frase 5 (4.5s)", placeholder="Testo...")
                            l5_font = gr.Dropdown(["Bold", "Normal"], value="Normal", label="Font")
                        
                        btn_add_row = gr.Button("+ Aggiungi Frase", size="sm")
                        
                        def add_row_logic(count):
                            c = min(count + 1, 5)
                            return (c, 
                                    gr.update(visible=True) if c>=2 else gr.update(), 
                                    gr.update(visible=True) if c>=3 else gr.update(), 
                                    gr.update(visible=True) if c>=4 else gr.update(), 
                                    gr.update(visible=True) if c>=5 else gr.update())

                        btn_add_row.click(fn=add_row_logic, inputs=[state_row_count], outputs=[state_row_count, r2, r3, r4, r5])

                    with gr.Group():
                        gr.Markdown("#### 📍 Posizione e Footer")
                        sl_x_head = gr.Slider(0, 100, value=50, label="Pos X Testi")
                        sl_y_head = gr.Slider(0, 100, value=15, label="Pos Y Testi")
                        txt_foot = gr.Textbox(label="Nome Prodotto")
                        sl_x_foot = gr.Slider(0, 100, value=50, label="Pos X Footer")
                        sl_y_foot = gr.Slider(0, 100, value=85, label="Pos Y Footer")

                    btn_render_final = gr.Button("🎬 Renderizza", variant="primary", size="lg")

                with gr.Column(scale=2):
                    out_final_video = gr.Video(label="Finale", height=450)
                    final_status = gr.Markdown("")

    # ========================================
    # EVENTI
    # ========================================
    
    # 1. Genera Immagini
    btn_gen_img.click(
        fn=generate_images, 
        inputs=[inp_img, inp_prompt], 
        outputs=[out_gallery, state_session_id, state_filenames, status_msg]
    )
    
    # 2. Selezione Immagine
    def on_select(filenames, evt: gr.SelectData):
        if not filenames: return None, gr.update(visible=False), None
        s = filenames[evt.index]
        return s, gr.update(visible=True), s

    out_gallery.select(
        fn=on_select, 
        inputs=[state_filenames], 
        outputs=[state_selected_file, confirm_section, selected_preview]
    )
    
    # 3. Conferma Immagine (Passa al Tab 2)
    def confirm_step1(selected_file):
        if not selected_file: return None, "Seleziona immagine!", gr.Tabs()
        return selected_file, "Clicca 'Genera Video Base' per iniziare.", gr.Tabs(selected=1)

    btn_confirm.click(
        fn=confirm_step1, 
        inputs=[state_selected_file], 
        outputs=[final_preview, video_status, main_tabs]
    )

    # --- Sincronizzazione Anteprima Tab 1 -> Tab 2 ---
    selected_preview.change(
        fn=lambda x: x,
        inputs=[selected_preview],
        outputs=[final_preview]
    )
    
    # 4. Genera Video Base (LOGICA CORRETTA)
    def on_video_generated(video_path, status):
        return gr.update(visible=bool(video_path))

    gen_vid_event = btn_gen_vid.click(
        fn=generate_video_base,  # Assicurati che la funzione in alto si chiami così!
        inputs=[state_selected_file, state_session_id, video_prompt_input], 
        outputs=[out_video, video_status]
    )
    
    gen_vid_event.then(
        fn=on_video_generated, 
        inputs=[out_video, video_status], 
        outputs=[video_confirm_section]
    )
    
    # 5. Conferma Video (Passa al Tab 3)
    def confirm_step2(video_path):
        if not video_path: return None, gr.Tabs()
        return video_path, gr.Tabs(selected=2)

    btn_confirm_video.click(
        fn=confirm_step2, 
        inputs=[out_video], 
        outputs=[inp_video_step3, main_tabs]
    )
    
    # 6. Render Finale
    btn_render_final.click(
        fn=generate_final_video, 
        inputs=[
            inp_video_step3, 
            l1_txt, l1_font, 
            l2_txt, l2_font, 
            l3_txt, l3_font, 
            l4_txt, l4_font, 
            l5_txt, l5_font, 
            sl_x_head, sl_y_head, 
            txt_foot, sl_x_foot, sl_y_foot
        ],
        outputs=[out_final_video, final_status]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=True)

    # ========================================
    # EVENTI (COLLEGAMENTI CORRETTI)
    # ========================================
    
    # 1. Genera Immagini
    btn_gen_img.click(
        fn=generate_images, 
        inputs=[inp_img, inp_prompt], 
        outputs=[out_gallery, state_session_id, state_filenames, status_msg]
    )
    
    # 2. Selezione Immagine
    def on_select(filenames, evt: gr.SelectData):
        if not filenames: return None, gr.update(visible=False), None
        s = filenames[evt.index]
        return s, gr.update(visible=True), s

    out_gallery.select(
        fn=on_select, 
        inputs=[state_filenames], 
        outputs=[state_selected_file, confirm_section, selected_preview]
    )
    
    # 3. Conferma Immagine
    def confirm_step1(selected_file):
        if not selected_file: return None, "Seleziona immagine!", gr.Tabs()
        return selected_file, "Clicca 'Genera Video Base' per iniziare.", gr.Tabs(selected=1)

    btn_confirm.click(
        fn=confirm_step1, 
        inputs=[state_selected_file], 
        outputs=[final_preview, video_status, main_tabs]
    )
    
    # 4. Genera Video Base
    def on_video_generated(video_path, status):
        return gr.update(visible=bool(video_path))

    gen_vid_event = btn_gen_vid.click(
        fn=generate_video, 
        inputs=[state_selected_file, state_session_id], 
        outputs=[out_video, video_status]
    )
    
    gen_vid_event.then(
        fn=on_video_generated, 
        inputs=[out_video, video_status], 
        outputs=[video_confirm_section]
    )
    
    # 5. Conferma Video
    def confirm_step2(video_path):
        if not video_path: return None, gr.Tabs()
        return video_path, gr.Tabs(selected=2)

    btn_confirm_video.click(
        fn=confirm_step2, 
        inputs=[out_video], 
        outputs=[inp_video_step3, main_tabs]
    )
    
    # 6. Render Finale
    btn_render_final.click(
        fn=generate_final_video, 
        inputs=[
            inp_video_step3, 
            l1_txt, l1_font,   # <--- CORRETTO
            l2_txt, l2_font,   # <--- CORRETTO
            l3_txt, l3_font, 
            l4_txt, l4_font, 
            l5_txt, l5_font, 
            sl_x_head, sl_y_head, 
            txt_foot, sl_x_foot, sl_y_foot
        ],
        outputs=[out_final_video, final_status]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=True)
