#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🛍️ AI Campaign Manager - Gradio Frontend
Genera varianti di immagini prodotto e video animati
"""

import gradio as gr
import requests
import os
import base64

# ========================================
# ⚙️ CONFIGURAZIONE
# ========================================

N8N_IMAGES_URL = "http://localhost:5678/webhook/generate-images"
N8N_VIDEO_URL = "http://localhost:5678/webhook/generate-video"

BASE_OUTPUT_DIR = "/tmp/comfyui"  # Senza /output finale

# ========================================
# 📸 FUNZIONE: GENERA IMMAGINI
# ========================================

def generate_images(image_path, prompt, progress=gr.Progress()):
    import io
    from PIL import Image
    import numpy as np
    
    if not image_path:
        return [], None, [], "⚠️ Carica prima un'immagine!"
    
    if not prompt or prompt.strip() == "":
        return [], None, [], "⚠️ Inserisci una descrizione!"
    
    print(f"=== DEBUG GRADIO ===")
    print(f"Image path: {image_path}")
    print(f"Prompt: {prompt}")
    
    progress(0, desc="📤 Preparazione immagine...")
    
    # Converti immagine in base64
    try:
        img = Image.open(image_path)
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=95)
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    except Exception as e:
        return [], None, [], f"❌ Errore caricamento immagine: {str(e)}"
    
    # Prepara payload
    payload = {
        "prompt": prompt,
        "image": img_base64
    }
    
    progress(0.1, desc="📡 Invio a n8n...")
    
    try:
        # Invia richiesta a n8n
        response = requests.post(
            N8N_IMAGES_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=180
        )
        
        progress(0.3, desc="⏳ ComfyUI sta generando...")
        
        print(f"n8n Status Code: {response.status_code}")
        
        if response.status_code != 200:
            return [], None, [], f"❌ Errore n8n (status {response.status_code})"
        
        # Parsea JSON
        result = response.json()
        print(f"Full result: {result}")
        
        progress(0.6, desc="📦 Ricezione risultati...")
        
        # Verifica
        if not result.get("success"):
            return [], None, [], "❌ Generazione fallita"
        
        images_metadata = result.get("images", [])
        session_id = result.get("session_id", "unknown")
        
        if not images_metadata:
            return [], None, [], "❌ Nessuna immagine generata"
        
        progress(0.7, desc=f"🖼️ Caricamento {len(images_metadata)} immagini...")
        
        # LEGGI I FILE DAL FILESYSTEM
        output_images = []
        filenames_list = []
        
        # Costruisci path corretto
        if img_type == "output":
            file_path = os.path.join(BASE_DIR, "output", filename)
        else:
            file_path = os.path.join(BASE_DIR, img_type, subfolder, filename) if subfolder else os.path.join(BASE_DIR, img_type, filename)

        
        print(f"=== CARICAMENTO IMMAGINI ===")
        
        for idx, img_meta in enumerate(images_metadata):
            filename = img_meta.get("filename")
            subfolder = img_meta.get("subfolder", "")
            img_type = img_meta.get("type", "output")
            node_id = img_meta.get("node_id")
            
            if not filename:
                continue
            
            # FILTRA IMMAGINI INTERMEDIE
            if node_id == "59" or img_type == "temp":
                print(f"⚠️ Saltata immagine intermedia: {filename}")
                continue
            
            # Costruisci path
            if subfolder:
                file_path = os.path.join(BASE_DIR, img_type, subfolder, filename)
            else:
                file_path = os.path.join(BASE_DIR, img_type, filename)
            
            if not os.path.exists(file_path):
                print(f"⚠️ File non trovato: {file_path}")
                continue
            
            # Carica e converti in numpy array
            try:
                pil_image = Image.open(file_path)
                numpy_image = np.array(pil_image)
                
                output_images.append(numpy_image)
                filenames_list.append(file_path)
                print(f"✅ Caricata immagine {len(output_images)}: {filename}")
            except Exception as e:
                print(f"❌ Errore caricamento {filename}: {e}")
        
        if not output_images:
            return [], None, [], "❌ Nessuna immagine caricata"
        
        progress(1.0, desc="✅ Completato!")
        
        print(f"✅ Ritorno {len(output_images)} immagini")
        
        status_message = f"✅ Generate {len(output_images)} varianti! Clicca su un'immagine per selezionarla."
        
        return output_images, session_id, filenames_list, status_message
        
    except requests.exceptions.Timeout:
        return [], None, [], "⏱️ Timeout: n8n impiega troppo tempo (>3min)"
    except requests.exceptions.RequestException as e:
        return [], None, [], f"❌ Errore connessione: {str(e)}"
    except Exception as e:
        print(f"❌ ERRORE: {e}")
        import traceback
        traceback.print_exc()
        return [], None, [], f"❌ Errore: {str(e)}"


# ========================================
# 🎬 FUNZIONE: GENERA VIDEO
# ========================================

def generate_video(selected_file, session_id, progress=gr.Progress()):
    """
    Genera video animato dall'immagine selezionata
    """
    if not selected_file:
        return None, "❌ Nessuna immagine selezionata"
    
    print(f"=== GENERA VIDEO ===")
    print(f"File: {selected_file}")
    print(f"Session: {session_id}")
    
    progress(0, desc="📤 Invio immagine a n8n...")
    
    try:
        # Leggi l'immagine e converti in base64
        with open(selected_file, 'rb') as f:
            image_bytes = f.read()
        
        img_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Prepara payload
        payload = {
            "image": img_base64,
            "session_id": session_id,
            "filename": os.path.basename(selected_file)
        }
        
        progress(0.2, desc="📡 Connessione a n8n...")
        
        # Chiamata a n8n
        response = requests.post(
            N8N_VIDEO_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=300  # 5 minuti per il video
        )
        
        progress(0.5, desc="🎬 Generazione video in corso...")
        
        if response.status_code != 200:
            return None, f"❌ Errore n8n (status {response.status_code}): {response.text}"
        
        result = response.json()
        
        progress(0.8, desc="📥 Ricezione video...")
        
        if not result.get("success"):
            return None, f"❌ Generazione video fallita: {result.get('error', 'Unknown')}"
        
        # Ottieni il path del video
        video_path = result.get("video_path")
        
        if not video_path or not os.path.exists(video_path):
            return None, "❌ Video generato ma file non trovato"
        
        progress(1.0, desc="✅ Video pronto!")
        
        return video_path, f"✅ Video generato con successo! ({os.path.basename(video_path)})"
        
    except requests.exceptions.Timeout:
        return None, "⏱️ Timeout: la generazione video richiede troppo tempo"
    except Exception as e:
        print(f"❌ Errore video: {e}")
        import traceback
        traceback.print_exc()
        return None, f"❌ Errore: {str(e)}"


# ========================================
# 🎨 INTERFACCIA GRADIO
# ========================================

with gr.Blocks(title="AI Campaign Manager") as demo:
    
    # Stati
    state_session_id = gr.State()
    state_filenames = gr.State()
    state_selected_file = gr.State()
    state_has_generated = gr.State(value=False)  # Traccia se ha generato immagini

    gr.Markdown("# 🛍️ Generatore Campagne AI")
    gr.Markdown("Trasforma le foto dei tuoi prodotti in campagne marketing professionali")
    
    # ========================================
    # TAB 1: GENERAZIONE IMMAGINI
    # ========================================
    with gr.Tab("📸 Genera Varianti") as tab_images:
        with gr.Row():
            with gr.Column(scale=1):
                inp_img = gr.Image(
                    type="filepath", 
                    label="Carica Foto Prodotto", 
                    height=300
                )
                inp_prompt = gr.Textbox(
                    label="Descrivi lo Scenario", 
                    placeholder="Es: metti lo zaino in una scuola moderna",
                    lines=3
                )
                btn_gen_img = gr.Button(
                    "🚀 Genera Varianti", 
                    variant="primary", 
                    size="lg"
                )
            
            with gr.Column(scale=2):
                out_gallery = gr.Gallery(
                    label="Varianti Generate - Clicca per Selezionare", 
                    columns=3, 
                    height="auto", 
                    show_label=True,
                    object_fit="contain"
                )
                status_msg = gr.Markdown("Pronto.")
        
        # Sezione di conferma (nascosta)
        with gr.Row(visible=False) as confirm_section:
            with gr.Column(scale=1):
                gr.Markdown("### ✅ Hai Selezionato un'Immagine")
                selected_preview = gr.Image(
                    label="Anteprima", 
                    interactive=False,
                    height=300
                )
            with gr.Column(scale=1):
                gr.Markdown("### Conferma per Procedere al Video")
                btn_confirm = gr.Button(
                    "✅ Conferma e Vai al Video", 
                    variant="primary", 
                    size="lg"
                )
                btn_cancel = gr.Button(
                    "🔄 Cambia Selezione"
                )

    # ========================================
    # TAB 2: GENERAZIONE VIDEO (INIZIALMENTE DISABILITATO)
    # ========================================
    with gr.Tab("🎬 Genera Video", id=1) as tab_video:
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## 🎬 Creazione Video Animato")
                final_preview = gr.Image(
                    label="Immagine Selezionata", 
                    interactive=False,
                    height=400
                )
                btn_gen_vid = gr.Button(
                    "✨ Genera Video Zoom", 
                    variant="primary", 
                    size="lg"
                )
            
            with gr.Column(scale=2):
                out_video = gr.Video(
                    label="Video Generato"
                )
                video_status = gr.Markdown("Seleziona un'immagine nel tab precedente e conferma.")

    # ========================================
    # EVENTI
    # ========================================
    
    # 1. Genera immagini
    btn_gen_img.click(
        fn=generate_images,
        inputs=[inp_img, inp_prompt],
        outputs=[out_gallery, state_session_id, state_filenames, status_msg]
    )
    
    # 2. Selezione immagine
    def on_gallery_select(filenames, evt: gr.SelectData):
        if not filenames or evt.index >= len(filenames):
            return None, gr.update(visible=False), None, "⚠️ Errore selezione"
        
        selected_file = filenames[evt.index]
        print(f"✅ Selezionata: {selected_file}")
        
        return (
            selected_file,
            gr.update(visible=True),
            selected_file,
            "✅ Immagine selezionata! Clicca 'Conferma' per procedere."
        )
    
    out_gallery.select(
        fn=on_gallery_select,
        inputs=[state_filenames],
        outputs=[state_selected_file, confirm_section, selected_preview, status_msg]
    )
    
    # 3. Conferma selezione
    def confirm_selection(selected_file):
        if not selected_file:
            return None, "⚠️ Nessuna immagine"
        
        print(f"✅ Confermata: {selected_file}")
        
        return (
            selected_file,
            "✅ Immagine confermata! Vai al tab 'Genera Video' e clicca 'Genera Video Zoom'."
        )
    
    btn_confirm.click(
        fn=confirm_selection,
        inputs=[state_selected_file],
        outputs=[final_preview, video_status]
    )
    
    # 4. Annulla selezione
    def cancel_selection():
        return None, gr.update(visible=False), None, "Seleziona un'altra immagine"
    
    btn_cancel.click(
        fn=cancel_selection,
        outputs=[state_selected_file, confirm_section, selected_preview, status_msg]
    )
    
    # 5. Genera video
    btn_gen_vid.click(
        fn=generate_video,
        inputs=[state_selected_file, state_session_id],
        outputs=[out_video, video_status]
    )
    

# ========================================
# LAUNCH
# ========================================

if __name__ == "__main__":
    print("🚀 Avvio AI Campaign Manager...")
    print(f"📡 n8n Images: {N8N_IMAGES_URL}")
    print(f"📡 n8n Video: {N8N_VIDEO_URL}")
    
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True,
        show_error=True
    )
