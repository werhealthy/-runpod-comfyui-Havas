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
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ========================================
# ⚙️ CONFIGURAZIONE
# ========================================

N8N_IMAGES_URL = "http://0.0.0.0:5678/webhook/generate-images-2"
N8N_VIDEO_URL = "http://localhost:5678/webhook/generate-video"

BASE_OUTPUT_DIR = "/tmp/comfyui"  # Senza /output finale

# ========================================
# 🔧 SESSIONE REQUESTS CON RETRY
# ========================================

def create_session():
    """Crea sessione requests con retry automatico"""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

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
    
    print(f"\n{'='*50}")
    print(f"🎬 INIZIO GENERAZIONE IMMAGINI")
    print(f"{'='*50}")
    print(f"📁 Image path: {image_path}")
    print(f"💬 Prompt: {prompt}")
    print(f"🕐 Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    progress(0, desc="📤 Preparazione immagine...")
    
    # Converti immagine in base64
    try:
        img = Image.open(image_path)
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=95)
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        print(f"✅ Immagine codificata: {len(img_base64)} caratteri")
    except Exception as e:
        print(f"❌ ERRORE caricamento immagine: {str(e)}")
        return [], None, [], f"❌ Errore caricamento immagine: {str(e)}"
    
    # Prepara payload
    payload = {
        "prompt": prompt,
        "image": img_base64
    }
    
    progress(0.1, desc="📡 Invio a n8n...")
    print(f"📡 Invio richiesta a: {N8N_IMAGES_URL}")
    
    try:
        # Crea sessione con retry
        session = create_session()
        
        # Timer di inizio
        start_time = time.time()
        
        # Invia richiesta a n8n con TIMEOUT AUMENTATO
        print(f"⏳ Timeout impostato: 240 secondi (4 minuti)")
        response = session.post(
            N8N_IMAGES_URL,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            timeout=240  # 4 MINUTI invece di 3
        )
        
        elapsed_time = time.time() - start_time
        
        progress(0.3, desc="⏳ ComfyUI sta generando...")
        
        print(f"\n{'='*50}")
        print(f"📥 RISPOSTA DA n8n")
        print(f"{'='*50}")
        print(f"⏱️  Tempo di risposta: {elapsed_time:.2f} secondi")
        print(f"📊 Status Code: {response.status_code}")
        print(f"📋 Headers: {dict(response.headers)}")
        print(f"📝 Response Text (primi 500 char): {response.text[:500]}")
        
        if response.status_code != 200:
            error_msg = f"❌ Errore n8n (status {response.status_code}): {response.text}"
            print(error_msg)
            return [], None, [], error_msg
        
        # Parsea JSON
        try:
            result = response.json()
            print(f"✅ JSON parsato correttamente")
            print(f"🔑 Chiavi JSON ricevute: {list(result.keys())}")
            print(f"📦 Full result: {result}")
        except Exception as json_error:
            print(f"❌ ERRORE parsing JSON: {json_error}")
            print(f"📝 Raw text: {response.text}")
            return [], None, [], f"❌ Errore parsing JSON: {json_error}"
        
        progress(0.6, desc="📦 Ricezione risultati...")
        
        # VERIFICA RISPOSTA PREMATURA
        if "message" in result and result.get("message") == "Workflow executed successfully":
            error_msg = """
            ⚠️ n8n ha risposto troppo presto!
            
            Il webhook è configurato per rispondere immediatamente invece di aspettare il completamento.
            
            SOLUZIONE:
            1. Apri n8n
            2. Clicca sul nodo "Webhook" (primo nodo)
            3. Nella sezione "Webhook Response" → Respond
            4. Cambia in: "Using 'Respond to Webhook' Node"
            5. Salva il workflow
            """
            print(f"❌ {error_msg}")
            return [], None, [], error_msg
        
        # Verifica successo
        if not result.get("success"):
            error_msg = result.get("error", "Generazione fallita (motivo sconosciuto)")
            print(f"❌ n8n ha restituito success=false: {error_msg}")
            return [], None, [], f"❌ {error_msg}"
        
        images_metadata = result.get("images", [])
        session_id = result.get("session_id", "unknown")
        
        print(f"🆔 Session ID: {session_id}")
        print(f"🖼️  Numero immagini ricevute: {len(images_metadata)}")
        
        if not images_metadata:
            error_msg = "❌ n8n non ha restituito immagini. Verifica il nodo 'Respond to Webhook'"
            print(error_msg)
            return [], None, [], error_msg
        
        progress(0.7, desc=f"🖼️ Caricamento {len(images_metadata)} immagini...")
        
        # LEGGI I FILE DAL FILESYSTEM
        output_images = []
        filenames_list = []
        
        BASE_DIR = BASE_OUTPUT_DIR
        
        print(f"\n{'='*50}")
        print(f"📂 CARICAMENTO IMMAGINI DAL FILESYSTEM")
        print(f"{'='*50}")
        print(f"📁 Base directory: {BASE_DIR}")
        
        for idx, img_meta in enumerate(images_metadata):
            filename = img_meta.get("filename")
            subfolder = img_meta.get("subfolder", "")
            img_type = img_meta.get("type", "output")
            node_id = img_meta.get("node_id")
            
            print(f"\n🔍 Immagine {idx+1}/{len(images_metadata)}:")
            print(f"   📄 Filename: {filename}")
            print(f"   📂 Subfolder: {subfolder}")
            print(f"   🏷️  Type: {img_type}")
            print(f"   🔢 Node ID: {node_id}")
            
            if not filename:
                print(f"   ⚠️  SKIP: filename mancante")
                continue
            
            # FILTRA IMMAGINI INTERMEDIE
            if node_id == "59" or img_type == "temp":
                print(f"   ⚠️  SKIP: immagine intermedia/temp")
                continue
            
            # Costruisci path
            if img_type == "output":
                file_path = os.path.join(BASE_DIR, "output", filename)
            else:
                if subfolder:
                    file_path = os.path.join(BASE_DIR, img_type, subfolder, filename)
                else:
                    file_path = os.path.join(BASE_DIR, img_type, filename)
            
            print(f"   📍 Path completo: {file_path}")
            
            if not os.path.exists(file_path):
                print(f"   ❌ FILE NON TROVATO!")
                continue
            
            # Carica e converti in numpy array
            try:
                pil_image = Image.open(file_path)
                numpy_image = np.array(pil_image)
                
                output_images.append(numpy_image)
                filenames_list.append(file_path)
                print(f"   ✅ CARICATA ({pil_image.size})")
            except Exception as e:
                print(f"   ❌ Errore caricamento: {e}")
        
        print(f"\n{'='*50}")
        print(f"📊 RISULTATO FINALE")
        print(f"{'='*50}")
        print(f"✅ Immagini caricate con successo: {len(output_images)}")
        print(f"⏱️  Tempo totale: {time.time() - start_time:.2f} secondi")
        
        if not output_images:
            error_msg = "❌ Nessuna immagine caricata dal filesystem"
            print(error_msg)
            return [], None, [], error_msg
        
        progress(1.0, desc="✅ Completato!")
        
        status_message = f"✅ Generate {len(output_images)} varianti! Clicca su un'immagine per selezionarla."
        
        return output_images, session_id, filenames_list, status_message
        
    except requests.exceptions.Timeout:
        error_msg = f"⏱️ TIMEOUT dopo 240 secondi. n8n non ha risposto in tempo.\n\nPossibili cause:\n1. ComfyUI impiega più di 4 minuti\n2. Il webhook n8n non è configurato correttamente\n3. Il nodo 'Wait' ha un valore troppo alto"
        print(f"\n❌ {error_msg}")
        return [], None, [], error_msg
    except requests.exceptions.RequestException as e:
        error_msg = f"❌ Errore connessione a n8n: {str(e)}"
        print(f"\n❌ {error_msg}")
        return [], None, [], error_msg
    except Exception as e:
        print(f"\n❌ ERRORE GENERALE: {e}")
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
    
    print(f"\n{'='*50}")
    print(f"🎬 INIZIO GENERAZIONE VIDEO")
    print(f"{'='*50}")
    print(f"📁 File: {selected_file}")
    print(f"🆔 Session: {session_id}")
    print(f"🕐 Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    progress(0, desc="📤 Invio immagine a n8n...")
    
    try:
        # Leggi l'immagine e converti in base64
        with open(selected_file, 'rb') as f:
            image_bytes = f.read()
        
        img_base64 = base64.b64encode(image_bytes).decode('utf-8')
        print(f"✅ Immagine codificata: {len(img_base64)} caratteri")
        
        # Prepara payload
        payload = {
            "image": img_base64,
            "session_id": session_id,
            "filename": os.path.basename(selected_file)
        }
        
        progress(0.2, desc="📡 Connessione a n8n...")
        
        # Crea sessione con retry
        session = create_session()
        
        start_time = time.time()
        
        # Chiamata a n8n con TIMEOUT AUMENTATO
        print(f"📡 Invio richiesta a: {N8N_VIDEO_URL}")
        print(f"⏳ Timeout impostato: 300 secondi (5 minuti)")
        
        response = session.post(
            N8N_VIDEO_URL,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            timeout=300  # 5 minuti per il video
        )
        
        elapsed_time = time.time() - start_time
        
        progress(0.5, desc="🎬 Generazione video in corso...")
        
        print(f"\n{'='*50}")
        print(f"📥 RISPOSTA DA n8n (VIDEO)")
        print(f"{'='*50}")
        print(f"⏱️  Tempo di risposta: {elapsed_time:.2f} secondi")
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code != 200:
            error_msg = f"❌ Errore n8n (status {response.status_code}): {response.text}"
            print(error_msg)
            return None, error_msg
        
        result = response.json()
        print(f"✅ JSON parsato: {result}")
        
        progress(0.8, desc="📥 Ricezione video...")
        
        if not result.get("success"):
            error_msg = f"❌ Generazione video fallita: {result.get('error', 'Unknown')}"
            print(error_msg)
            return None, error_msg
        
        # Ottieni il path del video
        video_path = result.get("video_path")
        
        print(f"📹 Video path ricevuto: {video_path}")
        
        if not video_path or not os.path.exists(video_path):
            error_msg = "❌ Video generato ma file non trovato"
            print(error_msg)
            return None, error_msg
        
        progress(1.0, desc="✅ Video pronto!")
        
        print(f"✅ Video generato con successo: {os.path.basename(video_path)}")
        print(f"⏱️  Tempo totale: {elapsed_time:.2f} secondi")
        
        return video_path, f"✅ Video generato con successo! ({os.path.basename(video_path)})"
        
    except requests.exceptions.Timeout:
        error_msg = "⏱️ Timeout: la generazione video richiede più di 5 minuti"
        print(f"\n❌ {error_msg}")
        return None, error_msg
    except Exception as e:
        print(f"\n❌ Errore video: {e}")
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
    state_has_generated = gr.State(value=False)

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
    # TAB 2: GENERAZIONE VIDEO
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
    print(f"\n{'='*60}")
    print(f"🚀 AVVIO AI CAMPAIGN MANAGER")
    print(f"{'='*60}")
    print(f"📡 n8n Images Endpoint: {N8N_IMAGES_URL}")
    print(f"📡 n8n Video Endpoint: {N8N_VIDEO_URL}")
    print(f"📁 Base Output Directory: {BASE_OUTPUT_DIR}")
    print(f"⏰ Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True,
        show_error=True
    )