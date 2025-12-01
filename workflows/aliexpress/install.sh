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
  "$MODEL_DIR/checkpoints" \
  "$CUSTOM_NODES_DIR" \
  "$WORKFLOWS_DIR"
  
###############################################
# 0. SISTEMA E DIPENDENZE BASE
###############################################
echo "🚀 Installazione dipendenze di sistema..."

apt-get update && apt-get install -y fonts-dejavu-core ffmpeg libgl1-mesa-glx jq
echo "🚀 Installazione tool Python..."
pip install hf_transfer huggingface_hub

export HF_HUB_ENABLE_HF_TRANSFER=1

###############################################
# 1. COPIA DEL FILE JSON DEL WORKFLOW
###############################################

WORKFLOW_URL="https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/refs/heads/main/workflows/aliexpress/aliexpress.json"

echo "📄 Copio workflow JSON..."
curl -fSL "$WORKFLOW_URL" -o "$WORKFLOWS_DIR/aliexpress.json"

echo "✔️ Workflow copiato in $WORKFLOWS_DIR/aliexpress.json"


###############################################
# 2. INSTALLAZIONE MODELLI
###############################################

echo "📥 Installazione modelli..."

wget -c --show-progress "https://huggingface.co/aidiffuser/Qwen-Image-Edit-2509/resolve/main/Qwen-Image-Edit-2509_fp8_e4m3fn.safetensors" \
  -O "$MODEL_DIR/diffusion_models/Qwen-Image-Edit-2509_fp8_e4m3fn.safetensors"

wget -c --show-progress "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors" \
  -O "$MODEL_DIR/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors"

wget -c --show-progress "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors" \
  -O "$MODEL_DIR/vae/qwen_image_vae.safetensors"

wget -c --show-progress "https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-8steps-V1.1.safetensors" \
  -O "$MODEL_DIR/loras/Qwen-Image-Lightning-8steps-V1.1.safetensors"

wget -c --show-progress "https://huggingface.co/dx8152/Qwen-Image-Edit-2509-White_to_Scene/resolve/main/%E7%99%BD%E5%BA%95%E5%9B%BE%E8%BD%AC%E5%9C%BA%E6%99%AF.safetensors" \
  -O "$MODEL_DIR/loras/white_to_scene.safetensors"

# --- FONTS ---
echo "🔤 Installazione Fonts..."

# URL base che punta alla cartella workflows/aliexpress dove hai caricato i file
FONT_BASE_URL="https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/refs/heads/main/workflows/aliexpress"

# Scarica Bold
wget -c "$FONT_BASE_URL/TTNormsPro-Bold.ttf" -O "$COMFY_DIR/TTNormsPro-Bold.ttf"

# Scarica Regular ma lo salva come 'Normal' per compatibilità con lo script Python
wget -c "$FONT_BASE_URL/TTNormsPro-Regular.ttf" -O "$COMFY_DIR/TTNormsPro-Normal.ttf"

###############################################
# 3. INSTALLAZIONE CUSTOM NODES
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
)

for entry in "${CUSTOM_NODES[@]}"; do
  NAME=$(echo "$entry" | cut -d'|' -f1)
  REPO=$(echo "$entry" | cut -d'|' -f2)
  DEST="$CUSTOM_NODES_DIR/$NAME"
  rm -rf "$DEST"
  echo "📥 Clono da zero $NAME"
  git clone --depth=1 "$REPO" "$DEST"
done

echo "📦 Configurazione finale dei Nodi..."

for folder in "$CUSTOM_NODES_DIR"/*; do
  if [ -f "$folder/requirements.txt" ]; then
     pip install -q --no-cache-dir -r "$folder/requirements.txt" || true
  fi
  
  if [ -f "$folder/install.py" ]; then
     echo "⚙️ Configuro nodo: $(basename "$folder")"
     cd "$folder"
     python install.py || true
     cd ..
  fi
done

if [ -d "$CUSTOM_NODES_DIR/rgthree-comfy/web" ]; then
    echo "⚡ FIX: Copio manualmente interfaccia rgthree..."
    mkdir -p "$COMFY_DIR/web/extensions/rgthree"
    cp -rf "$CUSTOM_NODES_DIR/rgthree-comfy/web"/* "$COMFY_DIR/web/extensions/rgthree/"
fi

if [ -d "$CUSTOM_NODES_DIR/ComfyUI-Manager" ]; then
    echo "🔧 Eseguo riparazione dipendenze Manager..."
    cd "$CUSTOM_NODES_DIR/ComfyUI-Manager"
    pip install -q -r requirements.txt || true
    python cm-cli.py restore-dependencies || true
fi

echo "🧹 Pulizia cache finale..."
rm -rf "$COMFY_DIR/user/default/node_cache"
rm -rf "$COMFY_DIR/__pycache__"

cd /tmp

###############################################
# 4. FRONTEND ALIEXPRESS (Gradio)
###############################################

echo "🔧 Setup frontend AliExpress..."

FRONTEND_DIR="$COMFY_DIR/frontends/aliexpress"
mkdir -p "$FRONTEND_DIR"

APP_URL="https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/refs/heads/main/workflows/aliexpress/app.py"
echo "📥 Scarico app.py AliExpress..."
curl -fSL "$APP_URL" -o "$FRONTEND_DIR/app.py" || echo "⚠️ Errore download app.py"

echo "📦 Installo requirements frontend AliExpress..."
pip install -q --no-cache-dir gradio requests || true

echo "⚙️ Creo comando 'run-aliexpress-frontend'..."
cat <<'EOF' >/usr/local/bin/run-aliexpress-frontend
#!/usr/bin/env bash
FRONTEND_DIR="/tmp/comfyui/frontends/aliexpress"
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
  echo "📍 Log: $LOG_FILE"
else
  echo "❌ Frontend AliExpress non è rimasto in esecuzione."
  echo "📋 Ultime righe log:"
  tail -20 "$LOG_FILE" || echo "❌ Nessun log trovato."
fi
EOF

chmod +x /usr/local/bin/run-aliexpress-frontend

echo "🚀 Avvio frontend AliExpress..."
/usr/local/bin/run-aliexpress-frontend

###############################################
# 5. RIAVVIO AUTOMATICO COMFYUI
###############################################
echo "🔄 Riavvio forzato di ComfyUI..."

pkill -f "python main.py" || true
pkill -f "python3 main.py" || true

echo "⏳ Attendo chiusura processi..."
sleep 3

echo "🚀 Avvio ComfyUI Pulito..."
cd "$COMFY_DIR"

nohup python main.py \
    --listen 0.0.0.0 \
    --port 8188 \
    --enable-cors-header \
    --force-fp16 \
    --preview-method auto \
    > "$COMFY_DIR/comfyui.log" 2>&1 &

###############################################
# 6. INSTALLAZIONE N8N
###############################################

echo "📦 Installazione n8n..."

if ! command -v node &> /dev/null || ! node -e 'process.exit(process.versions.node.split(".")[0] >= 18 ? 0 : 1)'; then
  echo "⚠️ Node.js assente o troppo vecchio. Installo Node 18..."
  curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
  apt-get install -y nodejs
fi

echo "✔️ Versione Node in uso: $(node -v)"

if ! command -v n8n &> /dev/null; then
  echo "➡️ Installo n8n..."
  npm install -g n8n@1.39.1 || true
else
  echo "✔️ n8n già installato."
fi

echo "⚙️ Creo comando 'run-aliexpress-n8n'..."
cat <<'EOF' >/usr/local/bin/run-aliexpress-n8n
#!/usr/bin/env bash

export N8N_PORT=5678
export N8N_HOST=0.0.0.0
export N8N_BASIC_AUTH_ACTIVE=true
export N8N_BASIC_AUTH_USER=admin
export N8N_BASIC_AUTH_PASSWORD=havas123
export N8N_DIAGNOSTICS_ENABLED=false

n8n start
EOF

chmod +x /usr/local/bin/run-aliexpress-n8n
echo "✔️ Script creato: run-aliexpress-n8n"

###############################################
# 7. WORKFLOW N8N - DOWNLOAD E CONFIG
###############################################

echo "📥 Scarico workflow n8n AliExpress..."

N8N_WF_DIR="$COMFY_DIR/n8n_workflows/aliexpress"
mkdir -p "$N8N_WF_DIR"

# 🔍 RILEVA URL COMFYUI
if [ -n "$RUNPOD_POD_ID" ]; then
  COMFYUI_URL="https://${RUNPOD_POD_ID}-8188.proxy.runpod.net"
  echo "✅ URL ComfyUI rilevato: $COMFYUI_URL"
else
  COMFYUI_URL="http://127.0.0.1:8188"
  echo "⚠️ URL ComfyUI: localhost (non RunPod)"
fi

# Scarica workflow 1
curl -fSL "https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/refs/heads/main/workflows/aliexpress/_ALIEXPRESS__01___Image_Generator.json" \
  -o "$N8N_WF_DIR/_ALIEXPRESS__01___Image_Generator.json" || true

# Scarica workflow 2
curl -fSL "https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/refs/heads/main/workflows/aliexpress/_ALIEXPRESS__02___Video_Generator.json" \
  -o "$N8N_WF_DIR/_ALIEXPRESS__02___Video_Generator.json" || true

# Scarica workflow 3
curl -fSL "https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/refs/heads/main/workflows/aliexpress/_ALIEXPRESS__03___Final_Composer.json" \
  -o "$N8N_WF_DIR/_ALIEXPRESS__03___Final_Composer.json" || true

# 🔧 SOSTITUISCI URL NEI WORKFLOW
for file in "$N8N_WF_DIR"/*.json; do
  if [ -f "$file" ]; then
    echo "🔧 Aggiorno URL in: $(basename "$file")"
    sed -i "s|http://127.0.0.1:8188|${COMFYUI_URL}|g" "$file"
    sed -i "s|{{ \$env.COMFYUI_URL }}|${COMFYUI_URL}|g" "$file"
  fi
done

echo "✔️ Workflow n8n salvati in $N8N_WF_DIR"
echo "📥 Import automatico dei workflow in n8n..."

export N8N_ENCRYPTION_KEY="dev-aliexpress-key-super-segreta"
export N8N_BASIC_AUTH_ACTIVE=true
export N8N_BASIC_AUTH_USER=admin
export N8N_BASIC_AUTH_PASSWORD=havas123

# Funzione per correggere e importare
import_safe() {
  local FILE="$1"
  local FIXED_FILE="${FILE}_fixed.json"
  
  if [ -f "$FILE" ]; then
    echo "🔧 Correggo formato JSON per: $(basename "$FILE")"
    # Usa jq per mettere il contenuto dentro una lista [ ... ]
    jq -s '.' "$FILE" > "$FIXED_FILE"
    
    echo "➡️ Importo in n8n..."
    n8n import:workflow --input="$FIXED_FILE" || echo "⚠️ Errore importazione $(basename "$FILE")"
    
    # Pulizia
    rm "$FIXED_FILE"
  else
    echo "❌ File non trovato: $FILE"
  fi
}

# Esegui importazione sicura per i 3 file
import_safe "$N8N_WF_DIR/_ALIEXPRESS__01___Image_Generator.json"
import_safe "$N8N_WF_DIR/_ALIEXPRESS__02___Video_Generator.json"
import_safe "$N8N_WF_DIR/_ALIEXPRESS__03___Final_Composer.json"

echo "🔌 Attivazione automatica di tutti i workflow..."
# Questo comando attiva tutti i workflow importati nel database
n8n update:workflow --all --active=true

echo "✔️ Workflow importati e ATTIVI nel DB di n8n"
###############################################
# 8. COPIA WORKFLOW NELLA CARTELLA n8n
###############################################

echo "📂 Copio workflow nella cartella n8n..."

# Crea la cartella workflows di n8n
N8N_USER_FOLDER="/root/.n8n"
mkdir -p "$N8N_USER_FOLDER/workflows"

# Copia i workflow direttamente nella cartella di n8n
if [ -f "$N8N_WF_DIR/_ALIEXPRESS__01___Image_Generator.json" ]; then
  cp "$N8N_WF_DIR/_ALIEXPRESS__01___Image_Generator.json" "$N8N_USER_FOLDER/workflows/"
  echo "✅ Copiato: _ALIEXPRESS__01___Image_Generator.json"
fi

if [ -f "$N8N_WF_DIR/_ALIEXPRESS__02___Video_Generator.json" ]; then
  cp "$N8N_WF_DIR/_ALIEXPRESS__02___Video_Generator.json" "$N8N_USER_FOLDER/workflows/"
  echo "✅ Copiato: _ALIEXPRESS__02___Video_Generator.json"
fi

if [ -f "$N8N_WF_DIR/_ALIEXPRESS__03___Final_Composer.json" ]; then
  cp "$N8N_WF_DIR/_ALIEXPRESS__03___Final_Composer.json" "$N8N_USER_FOLDER/workflows/"
  echo "✅ Copiato: _ALIEXPRESS__03___Final_Composer.json"
fi

###############################################
# 9. AVVIO AUTOMATICO N8N
###############################################

echo "🚀 Avvio automatico di n8n (AliExpress)..."
nohup /usr/local/bin/run-aliexpress-n8n > /tmp/n8n.log 2>&1 &
echo "✔️ n8n avviato in background sulla porta 5678 (log: /tmp/n8n.log)"

###############################################
# 10. MESSAGGIO FINALE
###############################################

echo "==============================================="
echo "  🎉 INSTALLAZIONE COMPLETATA & RIAVVIATO!"
echo "  ComfyUI è attivo. Attendi 10-20 secondi."
echo ""
echo "  👉 Workflow AliExpress installato!"
echo "     • Workflow JSON:  $WORKFLOWS_DIR/aliexpress.json"
echo "     • Frontend:       http://0.0.0.0:7860"
echo ""
echo "  👉 Orchestratore (n8n)"
echo "     • Avvia n8n: run-aliexpress-n8n"
echo "     • Porta:     5678"
echo "     • Login:     admin / havas123"
echo ""
echo "  👉 Debug"
echo "     • Log ComfyUI: tail -f $COMFY_DIR/comfyui.log"
echo "     • Log Frontend: tail -f /tmp/aliexpress-frontend.log"
echo "     • Log n8n: tail -f /tmp/n8n.log"
echo ""
echo "==============================================="
