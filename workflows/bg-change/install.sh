#!/usr/bin/env bash
set -e

echo "==============================================="
echo "   ✅ Installazione workflow: BG Change"
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

WORKFLOW_URL="https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/main/workflows/bg-change/bg-change.json"

echo "📄 Copio workflow JSON..."
curl -fSL "$WORKFLOW_URL" -o "$WORKFLOWS_DIR/bg-change.json"

echo "✔️ Workflow copiato in $WORKFLOWS_DIR/bg-change.json"


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
# 4. FRONTEND (nuovo, integrato correttamente)
###############################################

echo "🌐 Setup Frontend BG Change..."

FRONTEND_ROOT="/tmp/havas_frontends"
FRONTEND_DIR="$FRONTEND_ROOT/bg-change"
REPO_GIT="https://github.com/werhealthy/-runpod-comfyui-Havas.git"

mkdir -p "$FRONTEND_ROOT"

# Clono il repo SOLO per prendere frontend_product_demo
if [ ! -d "$FRONTEND_DIR" ]; then
  echo "📥 Clono repo per recuperare il frontend..."
  git clone --depth 1 "$REPO_GIT" "$FRONTEND_DIR-tmp"

  if [ -d "$FRONTEND_DIR-tmp/frontend_product_demo" ]; then
    mv "$FRONTEND_DIR-tmp/frontend_product_demo" "$FRONTEND_DIR"
    rm -rf "$FRONTEND_DIR-tmp"
  else
    echo "❌ ERRORE: frontend_product_demo non trovato"
  fi
fi

if [ -d "$FRONTEND_DIR" ]; then

  echo "📦 Installo requirements frontend..."
  pip install -r "$FRONTEND_DIR/requirements.txt"

  echo "⚙️ Creo comando 'run-bg-change-frontend'..."
cat <<'EOF' >/usr/local/bin/run-bg-change-frontend
#!/usr/bin/env bash
FRONTEND_DIR="/tmp/havas_frontends/bg-change"
LOG_FILE="/tmp/bg-change-frontend.log"

cd "$FRONTEND_DIR" || {
  echo "❌ FRONTEND: cartella $FRONTEND_DIR non trovata"
  exit 1
}

echo "[FRONTEND] Avvio app.py su 0.0.0.0:7860..."
nohup python3 app.py > "$LOG_FILE" 2>&1 &

PID=$!
sleep 5

if ps -p "$PID" > /dev/null 2>&1; then
  echo "✨ Frontend BG Change avviato (PID $PID) su http://0.0.0.0:7860"
  echo "   Log: $LOG_FILE"
else
  echo "❌ Frontend BG Change non è rimasto in esecuzione."
  echo "   Ultime righe log:"
  tail -20 "$LOG_FILE" || echo "   Nessun log trovato."
fi
EOF

chmod +x /usr/local/bin/run-bg-change-frontend

  echo "🚀 Avvio frontend BG Change..."
  run-bg-change-frontend
fi


###############################################
# 5. FINE
###############################################

echo "==============================================="
echo "  🎉 BG Change installato!"
echo "  Usa 'run-bg-change-frontend' per riavviare la UI"
echo "  Esegui 'restartcomfy' per ricaricare ComfyUI"
echo "==============================================="

