#!/usr/bin/env bash
set -e

echo "==============================================="
echo "  ✅ Installazione workflow: AliExpress"
echo "==============================================="

COMFY_DIR="/tmp/comfyui"
MODEL_DIR="$COMFY_DIR/models"
CUSTOM_NODES_DIR="$COMFY_DIR/custom_nodes"
WORKFLOWS_DIR="$COMFY_DIR/user/default/workflows"

mkdir -p \
  "$MODEL_DIR/diffusion_models" \
  "$MODEL_DIR/text_encoders" \
  "$MODEL_DIR/vae" \
  "$MODEL_DIR/loras" \
  "$CUSTOM_NODES_DIR" \
  "$WORKFLOWS_DIR"
  
###############################################
# 0. SISTEMA E DIPENDENZE BASE (AGGIUNTO)
###############################################
echo "🚀 Installazione dipendenze di sistema..."

# Aggiorna apt e installa i font mancanti (FIX PER COMFYROLL) e ffmpeg
# Questo risolve l'errore "FileNotFoundError: /usr/share/fonts/truetype"
apt-get update && apt-get install -y fonts-dejavu-core ffmpeg libgl1-mesa-glx

echo "🚀 Installazione tool Python..."
# Installa il motore per download veloce (FIX PER RMBG)
# Questo risolve l'errore "hf_transfer package is not available"
pip install hf_transfer huggingface_hub

# Attiva il download veloce
export HF_HUB_ENABLE_HF_TRANSFER=1

###############################################
# 1. COPIA DEL FILE JSON DEL WORKFLOW
###############################################

WORKFLOW_URL="https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/refs/heads/main/workflows/aliexpress/aliexpress.json"

echo "📄 Copio workflow JSON..."
curl -fSL "$WORKFLOW_URL" -o "$WORKFLOWS_DIR/aliexpress.json"

echo "✔️ Workflow copiato in $WORKFLOWS_DIR/aliexpress.json"


###############################################
# 2. INSTALLAZIONE MODELLI (tuo codice originale)
###############################################

echo "📥 Installazione modelli..."

wget -c --show-progress "https://huggingface.co/aidiffuser/Qwen-Image-Edit-2509/resolve/main/Qwen-Image-Edit-2509_fp8_e4m3fn.safetensors" \
  -O $MODEL_DIR/diffusion_models/Qwen-Image-Edit-2509_fp8_e4m3fn.safetensors

wget -c --show-progress "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors" \
  -O $MODEL_DIR/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors

wget -c --show-progress "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors" \
  -O $MODEL_DIR/vae/qwen_image_vae.safetensors

wget -c --show-progress "https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-8steps-V1.1.safetensors" \
  -O $MODEL_DIR/loras/Qwen-Image-Lightning-8steps-V1.1.safetensors

wget -c --show-progress "https://huggingface.co/dx8152/Qwen-Image-Edit-2509-White_to_Scene/resolve/main/%E7%99%BD%E5%BA%95%E5%9B%BE%E8%BD%AC%E5%9C%BA%E6%99%AF.safetensors" \
  -O $MODEL_DIR/loras/white_to_scene.safetensors
  
# --- MODELLI PER SUPIR UPSCALER ---
# Nota: Questi vanno in 'checkpoints' standard
wget -c --show-progress "https://huggingface.co/Kijai/SUPIR_pruned/resolve/main/SUPIR-v0F_fp16.safetensors?download=true" \
  -O $MODEL_DIR/checkpoints/SUPIR-v0F_fp16.safetensors

wget -c --show-progress "https://civitai.com/api/download/models/357609" \
  -O $MODEL_DIR/checkpoints/juggernautXL_v9Rdphoto2Lightning.safetensors

###############################################
# 3. INSTALLAZIONE CUSTOM NODES (robusto e universale)
###############################################

echo "🧩 Installazione Custom Nodes..."

CUSTOM_NODES=(
  "ComfyUI-Manager|https://github.com/ltdrdata/ComfyUI-Manager.git"
  "ComfyUI-KJNodes|https://github.com/kijai/ComfyUI-KJNodes.git"
  "ComfyUI-RMBG|https://github.com/1038lab/ComfyUI-RMBG.git"
  "rgthree-comfy|https://github.com/rgthree/rgthree-comfy.git"
  "ComfyUI_essentials|https://github.com/cubiq/ComfyUI_essentials.git"
  "ComfyUI_Comfyroll_CustomNodes|https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes.git"
  "Comfyui-QwenEditUtils|https://github.com/lrzjason/Comfyui-QwenEditUtils.git"
  "was-node-suite-comfyui|https://github.com/ltdrdata/was-node-suite-comfyui.git"
  "ComfyUI-SUPIR|https://github.com/kijai/ComfyUI-SUPIR.git"
)

for entry in "${CUSTOM_NODES[@]}"; do
  NAME=$(echo "$entry" | cut -d'|' -f1)
  REPO=$(echo "$entry" | cut -d'|' -f2)
  DEST="$CUSTOM_NODES_DIR/$NAME"
  # Pulizia profonda e rimozione eventuale vecchia repo con nome diverso/simile
  rm -rf "$DEST"
  echo "📥 Clono da zero $NAME"
  git clone --depth=1 "$REPO" "$DEST"
done

echo "📦 Configurazione finale dei Nodi..."

# 1. Installa Requirements e Script di Setup (Solo se esistono)
for folder in /tmp/comfyui/custom_nodes/*; do
  if [ -f "$folder/requirements.txt" ]; then
     pip install -q --no-cache-dir -r "$folder/requirements.txt"
  fi
  
  # Questo controllo [ -f ] impedisce allo script di bloccarsi se install.py manca
  if [ -f "$folder/install.py" ]; then
     echo "⚙️ Configuro nodo: $(basename "$folder")"
     cd "$folder"
     python install.py
     cd ..
  fi
done

# 2. FIX SPECIFICO PER RGTHREE (Copia Manuale)
# Dato che install.py non esiste più, copiamo i file grafici a mano
if [ -d "/tmp/comfyui/custom_nodes/rgthree-comfy/web" ]; then
    echo "⚡ FIX: Copio manualmente interfaccia rgthree..."
    mkdir -p /tmp/comfyui/web/extensions/rgthree
    cp -rf /tmp/comfyui/custom_nodes/rgthree-comfy/web/* /tmp/comfyui/web/extensions/rgthree/
fi

# 3. RIPARAZIONE VIA MANAGER (Cruciale per KJNodes e RMBG)
if [ -d "/tmp/comfyui/custom_nodes/ComfyUI-Manager" ]; then
    echo "🔧 Eseguo riparazione dipendenze Manager..."
    cd /tmp/comfyui/custom_nodes/ComfyUI-Manager
    pip install -q -r requirements.txt
    python cm-cli.py restore-dependencies
fi

# 4. PULIZIA CACHE
echo "🧹 Pulizia cache finale..."
rm -rf /tmp/comfyui/user/default/node_cache
rm -rf /tmp/comfyui/__pycache__

# Torna alla cartella temporanea per proseguire con il frontend
cd /tmp

###############################################
# 4. FRONTEND ALIEXPRESS (Gradio)
###############################################

echo " Setup frontend AliExpress..."

FRONTEND_ROOT="/tmp/havas_frontends"
FRONTEND_DIR="$FRONTEND_ROOT/aliexpress"
mkdir -p "$FRONTEND_DIR"

# Scarica l'app Gradio specifica di AliExpress
APP_URL="https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/refs/heads/main/workflows/aliexpress/app.py"
echo " Scarico app.py AliExpress..."
curl -fSL "$APP_URL" -o "$FRONTEND_DIR/app.py"

# Requirements per il frontend (Gradio + richieste HTTP)
echo " Installo requirements frontend AliExpress..."
pip install -q --no-cache-dir gradio requests

echo "⚙️ Creo comando 'run-aliexpress-frontend'..."
cat <<'EOF' >/usr/local/bin/run-aliexpress-frontend
#!/usr/bin/env bash
FRONTEND_DIR="/tmp/havas_frontends/aliexpress"
LOG_FILE="/tmp/aliexpress-frontend.log"

cd "$FRONTEND_DIR" || {
  echo "❌ FRONTEND: cartella $FRONTEND_DIR non trovata"
  exit 1
}

echo "[FRONTEND] Avvio app.py AliExpress su 0.0.0.0:7860..."
nohup python3 app.py > "$LOG_FILE" 2>&1 &
PID=$!

sleep 5
if ps -p "$PID" > /dev/null 2>&1; then
  echo "✨ Frontend AliExpress avviato (PID $PID) su http://0.0.0.0:7860"
  echo " Log: $LOG_FILE"
else
  echo "❌ Frontend AliExpress non è rimasto in esecuzione."
  echo " Ultime righe log:"
  tail -20 "$LOG_FILE" || echo " Nessun log trovato."
fi
EOF

chmod +x /usr/local/bin/run-aliexpress-frontend

echo " Avvio frontend AliExpress..."
run-aliexpress-frontend
###############################################
# 5. RIAVVIO AUTOMATICO COMFYUI (Auto-Restart)
###############################################
echo "🔄 Riavvio forzato di ComfyUI per applicare le modifiche..."

# 1. Uccide il processo ComfyUI attuale (se esiste)
pkill -f "python main.py" || true
pkill -f "python3 main.py" || true

echo "⏳ Attendo chiusura processi..."
sleep 3

# 2. Rilancia ComfyUI in background con i tuoi parametri corretti
echo "🚀 Avvio ComfyUI Pulito..."
cd /tmp/comfyui

# Usa nohup per mantenerlo vivo anche se chiudi il terminale
nohup python main.py \
    --listen 0.0.0.0 \
    --port 8188 \
    --enable-cors-header \
    --force-fp16 \
    --preview-method auto \
    > /tmp/comfyui/comfyui.log 2>&1 &
###############################################
# 6. INSTALLAZIONE N8N (ORCHESTRATORE)
###############################################

echo "📦 Installazione n8n (orchestratore)..."

# 4.1 Installa Node 18 se assente o troppo vecchio
if ! command -v node &> /dev/null || ! node -e 'process.exit(process.versions.node.split(".")[0] >= 18 ? 0 : 1)'; then
  echo "⚠️  Node.js assente o troppo vecchio. Installo Node 18..."
  curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
  apt-get install -y nodejs
fi

echo "✔️  Versione Node in uso: $(node -v)"

# 4.2 Installa n8n versione compatibile con Node 18
if ! command -v n8n &> /dev/null; then
  echo "➡️  Installo n8n (versione compatibile con Node 18)..."
  npm install -g n8n@1.39.1
else
  echo "✔️  n8n già installato."
fi

# 4.3 Crea script di avvio per n8n
echo "⚙️  Creo comando 'run-aliexpress-n8n'..."
cat <<'EOF' >/usr/local/bin/run-aliexpress-n8n
#!/usr/bin/env bash

# Config base per n8n AliExpress
export N8N_PORT=5678
export N8N_HOST=0.0.0.0
export N8N_BASIC_AUTH_ACTIVE=true
export N8N_BASIC_AUTH_USER=admin
export N8N_BASIC_AUTH_PASSWORD=havas123
export N8N_DIAGNOSTICS_ENABLED=false

# Avvio n8n (senza argomenti invalidi)
n8n start
EOF


chmod +x /usr/local/bin/run-aliexpress-n8n
echo "✔️  Script creato: run-aliexpress-n8n"
echo ""
###############################################
# 7. WORKFLOW N8N (solo download file)
###############################################

echo " Scarico workflow n8n AliExpress..."

N8N_WF_DIR="/tmp/n8n_workflows/aliexpress"
mkdir -p "$N8N_WF_DIR"

curl -fSL "https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/refs/heads/main/workflows/aliexpress/_ALIEXPRESS__01___Image_Generator.json" \
  -o "$N8N_WF_DIR/_ALIEXPRESS__01___Image_Generator.json"

# ⚠️ CONTROLLA IL NOME ESATTO DEL SECONDO FILE NEL REPO
curl -fSL "https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/refs/heads/main/workflows/aliexpress/_ALIEXPRESS__02___Video_Generator.json" \
  -o "$N8N_WF_DIR/_ALIEXPRESS__02___Video_Generator.json" || echo "❌ Controlla il nome del file Video_Generator.json"

echo "✔️ Workflow n8n salvati in $N8N_WF_DIR"
echo "📥 Importo automaticamente i workflow in n8n..."

# n8n usa per default ~/.n8n come cartella utente
export N8N_USER_FOLDER="/root/.n8n"
export N8N_DIAGNOSTICS_ENABLED=false

# Importa tutti i JSON presenti nella cartella
n8n import:workflow --separate --input="$N8N_WF_DIR" || {
  echo "⚠️ Import automatico fallito. Puoi sempre importarli a mano da: n8n → Workflows → Import from File"
}


###############################################
# 8. AVVIO AUTOMATICO N8N DOPO INSTALLAZIONE
###############################################

echo "🚀 Avvio n8n per AliExpress..."

if [ -f /usr/local/bin/run-aliexpress-n8n ]; then
    # Avvia n8n in background
    nohup /usr/local/bin/run-aliexpress-n8n >/tmp/n8n.log 2>&1 &
    echo "✔️  n8n avviato in background sulla porta 5678"
    echo "📍 Log: /tmp/n8n.log"
else
    echo "❌ run-aliexpress-n8n non trovato! Possibile errore installazione."
fi

###############################################
# 9. MESSAGGIO FINALE
###############################################

echo "==============================================="
echo "  🎉 INSTALLAZIONE COMPLETATA & RIAVVIATO!"
echo "  ComfyUI è attivo. Attendi 10-20 secondi."
echo ""
echo "  👉 Workflow AliExpress installato!"
echo "     • Workflow JSON:  $WORKFLOWS_DIR/aliexpress.json"
echo "     • Script video:   /usr/local/bin/aliexpress-video.sh"
echo ""
echo "  👉 Orchestratore (n8n)"
echo "     • Avvia n8n: run-aliexpress-n8n"
echo "     • Porta:     5678"
echo "     • Login:     admin / havas123"
echo ""
echo "  👉 Debug"
echo "     • Log ComfyUI: tail -f /tmp/comfyui/comfyui.log"
echo ""
echo "==============================================="
