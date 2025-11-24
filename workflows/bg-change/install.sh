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
# 3. INSTALLAZIONE CUSTOM NODES (aggiornata)
###############################################

echo "🧩 Installazione Custom Nodes..."

CUSTOM_NODES=(
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
  [ -d "$DEST" ] && rm -rf "$DEST"
  echo "📥 Clono da zero $NAME"
  git clone --depth=1 "$REPO" "$DEST"
done

echo "📦 Installo requirements dei custom nodes..."
for folder in $CUSTOM_NODES_DIR/*; do
  [ -f "$folder/requirements.txt" ] && pip install -q --no-cache-dir -r "$folder/requirements.txt"
  [ -f "$folder/install.py" ] && python "$folder/install.py"
done


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

