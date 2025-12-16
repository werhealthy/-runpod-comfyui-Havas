Scopo del progetto

Costruire un ecosistema di strumenti interni per automatizzare workflow creativi e produttivi in modo utile, sostenibile, economico e veloce, utilizzabile anche da persone non tecniche. La tecnologia è un mezzo: priorità a ROI, costi GPU, time-efficiency e modularità. 

📄 Istruzioni di Progetto

In particolare, il workflow “AliExpress” punta a:

generare immagini prodotto con ComfyUI (controllo/coerenza/costi)

orchestrare step con n8n

offrire una UI pulita in Gradio per inserire testi/nome prodotto e lanciare il render finale

lavorare in RunPod in modo “ephemeral” (pod creato → usato → distrutto)

Architettura (alto livello)

RunPod (Linux) ospita:

ComfyUI (UI web e runtime modelli)

JupyterLab (gestione file, editing, debug)

n8n (orchestratore, webhook locali)

Gradio (frontend utente finale)

Il frontend Gradio parla con n8n tramite webhook locali su 127.0.0.1:5678. 
GitHub

Flusso di avvio (come lo usi tu)
0) Avvio Pod RunPod

Avvii RunPod usando un template.

Il template lancia startup.sh all’avvio. 
GitHub

1) Cosa fa startup.sh

startup.sh prepara la base “sistema”:

Cartelle principali

Base: /tmp/comfyui

Modelli: /tmp/comfyui/models/*

Custom nodes: /tmp/comfyui/custom_nodes 
GitHub

Clona e prepara ComfyUI

Se main.py non esiste, fa clone di ComfyUI in /tmp/comfyui da:

https://github.com/comfyanonymous/ComfyUI.git 
GitHub

Installa i requirements di ComfyUI se trova requirements.txt. 
GitHub

Installa ComfyUI-Manager

Clona in /tmp/comfyui/custom_nodes/ComfyUI-Manager da:

https://github.com/ltdrdata/ComfyUI-Manager.git 
GitHub

Comando rapido

Installa uno script di restart e crea alias:

restartcomfy → /usr/local/bin/restart-comfyui.sh (scaricato da repo esterna) 
GitHub

JupyterLab

Installa JupyterLab + terminals

Configura Jupyter senza token/password (accesso libero) e lo avvia su porta 8888

Notebook dir: /tmp/comfyui

Log: /tmp/jupyter.log 
GitHub

Workflow Manager
Installa comando workflows in /usr/local/bin/workflows:

mostra un menu

scegli workflow (es. 2) AliExpress)

scarica ed esegue un install.sh specifico del workflow da una base URL:

https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/refs/heads/main/workflows/<name>/install.sh 
GitHub

Output finale di startup

ComfyUI: http://0.0.0.0:8188

Jupyter: http://0.0.0.0:8888

Comandi: restartcomfy, workflows 
GitHub

Installazione workflow: AliExpress (workflows → opzione 2)

Quando scegli “AliExpress”, viene eseguito install.sh del workflow. 
GitHub
+1

2) Cosa fa install.sh (AliExpress)

Variabili e cartelle

COMFY_DIR=/tmp/comfyui

MODEL_DIR=/tmp/comfyui/models

CUSTOM_NODES_DIR=/tmp/comfyui/custom_nodes

WORKFLOWS_DIR=/tmp/comfyui/user/default/workflows 
GitHub

Crea (tra le altre) cartelle:

models/diffusion_models

models/text_encoders

models/vae

models/loras

models/checkpoints 
GitHub

Dipendenze di sistema
Installa via apt:

fonts-dejavu-core, ffmpeg, libgl1-mesa-glx, jq 
GitHub

Tool Python / HuggingFace transfer

Installa hf_transfer, huggingface_hub

set HF_HUB_ENABLE_HF_TRANSFER=1 
GitHub

Copia workflow JSON
Scarica aliexpress.json dentro la cartella workflow di ComfyUI:

base: https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/refs/heads/main/workflows/aliexpress

destinazione: /tmp/comfyui/user/default/workflows/aliexpress.json 
GitHub

Download modelli (HuggingFace)
Scarica (esempi principali):

Qwen Image Edit (diffusion model)

Qwen 2.5 VL text encoder

Qwen image VAE

LoRA “Qwen-Image-Lightning”

LoRA “white_to_scene” 
GitHub

Font e asset video
Scarica font e asset dalla stessa base URL dei workflow:

AliExpress sans.otf

AliExpress sans regluar.otf

output.mov salvato come /tmp/comfyui/outro.mp4 
GitHub

Fix dipendenze Python (numpy/opencv)
Per compatibilità:

disinstalla numpy/opencv vari

reinstalla numpy<2.0.0, OpenCV <4.10

installa cupy-cuda12x 
GitHub

Custom nodes installati (clone “da zero”)
Clona in /tmp/comfyui/custom_nodes/<NAME> una lista di repo, tra cui:

ComfyUI-KJNodes

ComfyUI-RMBG

rgthree-comfy

ComfyUI_essentials

ComfyUI_Comfyroll_CustomNodes

Comfyui-QwenEditUtils

was-node-suite-comfyui

ComfyUI_UltimateSDUpscale

ComfyUI-VideoHelperSuite

ComfyUI-Frame-Interpolation

RES4LYF

comfy-image-saver
(+ ComfyUI-Manager) 
GitHub

Poi:

installa requirements di ciascun nodo se presenti

esegue eventuale install.py

applica fix specifico per rgthree copiando asset web in web/extensions/rgthree

“ripara” dipendenze Manager con cm-cli.py restore-dependencies

pulisce cache (user/default/node_cache) 
GitHub

Nota: dopo install, spesso serve restartcomfy per far riconoscere i nuovi nodi/estensioni. 
GitHub

Frontend Gradio (AliExpress): cosa fa app.py

File: workflows/aliexpress/app.py nella tua repo (raw link fornito). 
GitHub

Concetto base

Frontend Gradio “AI Campaign Manager” con flusso a 3 step:

Generazione immagini (crea sessione, salva output ordinati)

Generazione video base (chiama n8n, salva preview nella sessione)

Render finale (manda testi/nome prodotto, salva render finale)

Endpoints n8n (locali)

Nel codice:

N8N_IMAGES_URL = http://127.0.0.1:5678/webhook/generate-images-2

N8N_VIDEO_URL = http://127.0.0.1:5678/webhook/generate-video

N8N_FINAL_URL = http://127.0.0.1:5678/webhook/generate-final-video 
GitHub

Organizzazione output per sessione

Base output:

BASE_OUTPUT_DIR = /tmp/comfyui/progetti 
GitHub

Ogni esecuzione crea una sessione con id tipo:

YYYYMMDD_HHMMSS
e salva in:

/tmp/comfyui/progetti/<session_id>/ 
GitHub

File salvati tipici:

input_original.jpg (input)

gen_1.png, gen_2.png, … (immagini generate)

base_video.mp4 (preview video step 2)

final_render.mp4 (output finale step 3) 
GitHub

Asset e font

Carica font BaikalExp da:

FONT_PATH = /tmp/comfyui/frontends/aliexpress/BaikalExp-Medium.otf 
GitHub

Usa anche un logo in:

/tmp/comfyui/frontends/aliexpress/logo.png 
GitHub

UI: struttura tab

Gradio costruisce tre tab principali:

Tab 1 “Immagine”: input immagine prodotto + prompt + gallery output (1 colonna)

Tab 2 “Video”: selezione modello (es. “Kling…” o “Fast SVD…”) + prompt video + player preview

Tab 3 “Testi”: input nome prodotto + overlay testi dinamici + render finale + download 
GitHub

Repos / sorgenti “chiave” coinvolte (quelle che finiscono nel Pod)

Queste sono le principali origini che, direttamente o indirettamente, vengono clonate/scaricate quando avvii tutto:

ComfyUI base

comfyanonymous/ComfyUI → clonato in /tmp/comfyui se non presente 
GitHub

ComfyUI Manager

ltdrdata/ComfyUI-Manager → clonato in /tmp/comfyui/custom_nodes/ComfyUI-Manager 
GitHub

Workflow install script + asset (base URL)

Workflow Manager scarica install script da:

werhealthy/-runpod-comfyui-Havas/.../workflows/<workflow>/install.sh 
GitHub

Il workflow AliExpress scarica JSON e asset da:

werhealthy/-runpod-comfyui-Havas/.../workflows/aliexpress/* 
GitHub

Custom nodes (più repo GitHub)

Clonati in /tmp/comfyui/custom_nodes/* (lista dentro install.sh). 
GitHub

Vincoli guida (da rispettare sempre)

Dal PDF “Istruzioni di Progetto”:

niente soluzioni “wow” inutili: preferire funzionale, snello, sostenibile

considerare sempre costi GPU + tempo (manuale vs ComfyUI vs automazione)

attenzione a vincoli legali: se output deve essere pubblicabile, meglio passaggi finali su piattaforme autorizzate quando necessario (Firefly, Artlist/Lightricks, ecc.) 

📄 Istruzioni di Progetto

Checklist rapida: “se apro un Pod nuovo”

Avvio Pod con template → parte startup.sh 
GitHub

Controllo:

Jupyter su :8888 (log /tmp/jupyter.log) 
GitHub

ComfyUI su :8188 
GitHub

Da terminale: workflows → scelgo 2) AliExpress 
GitHub

Attendo install (modelli + nodi + workflow json + font/asset) 
GitHub

Eseguo restartcomfy se necessario 
GitHub

Apro Gradio (avvio gestito dal workflow AliExpress; frontend app.py) e uso i 3 tab
