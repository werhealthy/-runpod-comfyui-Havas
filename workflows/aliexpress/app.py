import gradio as gr
import requests
import json
import os

# ==========================================
# ⚙️ CONFIGURAZIONE URL
# Assicurati che i workflow su n8n siano su "ACTIVE" (Verde)!
# ==========================================
N8N_IMAGES_URL = "http://localhost:5678/webhook/generate-images" 
N8N_VIDEO_URL = "http://localhost:5678/webhook/generate-video"
BASE_OUTPUT_DIR = "/tmp/comfyui/output"
# ==========================================

def generate_images(image_path, prompt, progress=gr.Progress()):
    if not image_path:
        raise gr.Error("⚠️ Carica prima un'immagine!")

    progress(0, desc="🚀 Contatto n8n...")
    print(f"🚀 Invio richiesta Immagini a n8n... [VERSIONE 2]")
    
    files = {'image': (os.path.basename(image_path), open(image_path, 'rb'))}
    data = {'prompt': prompt}

    try:
        response = requests.post(N8N_IMAGES_URL, files=files, data=data)
        
        # DEBUG: Stampiamo cosa risponde n8n nel terminale
        print(f"Stato n8n: {response.status_code}")
        print(f"Risposta n8n: {response.text[:200]}...") # Primi 200 caratteri

        if response.status_code == 200:
            try:
                json_resp = response.json()
            except:
                raise gr.Error(f"n8n non ha risposto con un JSON valido! Risposta grezza: {response.text}")

            images_data = json_resp.get('images', [])
            
            if not images_data:
                raise gr.Error(f"n8n ha risposto OK, ma la lista 'images' è vuota! Controlla il nodo Code.")

            # Recupero Session ID
            session_id = json_resp.get('session_id')
            if not session_id and images_data:
                session_id = images_data[0].get('subfolder', '')

            gallery_items = []
            filenames_only = []
            
            for img in images_data:
                fname = img.get('filename')
                subfolder = img.get('subfolder', '')
                full_path = os.path.join(BASE_OUTPUT_DIR, subfolder, fname)
                
                # Verifica se il file esiste davvero sul disco
                if not os.path.exists(full_path):
                    print(f"⚠️ ATTENZIONE: File non trovato sul disco: {full_path}")
                
                gallery_items.append((full_path, fname))
                filenames_only.append(fname)
            
            return gallery_items, session_id, filenames_only, f"✅ {len(images_data)} Varianti generate!"
        else:
            # Mostra l'errore esatto nel box rosso
            raise gr.Error(f"Errore Server n8n ({response.status_code}): {response.text}")

    except Exception as e:
        raise gr.Error(f"Errore Tecnico: {str(e)}")


def on_select_image(evt: gr.SelectData, filenames):
    index = evt.index
    selected_filename = filenames[index]
    return (
        selected_filename, 
        gr.update(visible=True), # Mostra sezione video
        f"📸 Selezionata: {selected_filename}"
    )


def generate_video(filename, session_id, progress=gr.Progress()):
    if not filename or not session_id:
        raise gr.Error("⚠️ Selezione persa. Riclicca l'immagine.")
        
    progress(0, desc="🎬 Rendering Video...")
    payload = { "session_id": session_id, "image_filename": filename }
    
    try:
        response = requests.post(N8N_VIDEO_URL, json=payload)
        
        if response.status_code == 200:
            output_path = "video_output.mp4"
            with open(output_path, "wb") as f:
                f.write(response.content)
            return output_path, "✨ Video Completato!"
        else:
            raise gr.Error(f"Errore n8n Video: {response.text}")
            
    except Exception as e:
        raise gr.Error(f"Errore Connessione: {str(e)}")


# --- INTERFACCIA ---
with gr.Blocks(title="AI Campaign Manager") as demo:
    
    state_session_id = gr.State()
    state_filenames = gr.State()
    state_selected_file = gr.State()

    gr.Markdown("# 🛍️ Generatore Campagne AI")
    
    with gr.Row():
        with gr.Column(scale=1):
            inp_img = gr.Image(type="filepath", label="Carica Foto", height=300)
            inp_prompt = gr.Textbox(label="Prompt", placeholder="Descrivi lo scenario...")
            btn_gen_img = gr.Button("🚀 Genera Varianti", variant="primary")
        
        with gr.Column(scale=2):
            # HO TOLTO IL NUMERO "2." DAL TITOLO
            out_gallery = gr.Gallery(
                label="Scegli la variante migliore", 
                columns=3, 
                height="auto", 
                interactive=False, 
                allow_preview=False
            )
            status_msg = gr.Markdown("Pronto.")

    # Sezione Video (Nascosta)
    with gr.Column(visible=False) as video_section:
        gr.Markdown("### 🎬 Animazione")
        with gr.Row():
            with gr.Column():
                btn_gen_vid = gr.Button("✨ Genera Video Zoom", variant="primary")
            with gr.Column():
                out_video = gr.Video(label="Video Finale", autoplay=True)

    # Eventi
    btn_gen_img.click(fn=generate_images, inputs=[inp_img, inp_prompt], outputs=[out_gallery, state_session_id, state_filenames, status_msg])
    out_gallery.select(fn=on_select_image, inputs=[state_filenames], outputs=[state_selected_file, video_section, status_msg])
    btn_gen_vid.click(fn=generate_video, inputs=[state_selected_file, state_session_id], outputs=[out_video, status_msg])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=True)