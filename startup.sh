#!/usr/bin/env bash
set -e

echo "==============================="
echo "  🚀 Avvio ComfyUI template Havas"
echo "==============================="

########################################
# 1. PATH E STRUTTURA CARTELLE
########################################

COMFY_DIR="/tmp/comfyui"
MODELS_DIR="$COMFY_DIR/models"
CUSTOM_NODES_DIR="$COMFY_DIR/custom_nodes"

mkdir -p \
  "$MODELS_DIR/checkpoints" \
  "$MODELS_DIR/loras" \
  "$MODELS_DIR/vae" \
  "$MODELS_DIR/controlnet" \
  "$MODELS_DIR/upscale_models" \
  "$MODELS_DIR/clip" \
  "$MODELS_DIR/unet" \
  "$CUSTOM_NODES_DIR"

########################################
# 2. INSTALLA / CLONA COMFYUI
########################################

if [ ! -d "$COMFY_DIR" ]; then
  echo "⚠️  ComfyUI non trovato, clonazione in corso..."
  git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git "$COMFY_DIR"
else
  echo "✓ ComfyUI già presente in $COMFY_DIR"
fi

cd "$COMFY_DIR"

# Se ci sono requirements, installali comunque
if [ -f "requirements.txt" ]; then
  pip install --no-cache-dir -r requirements.txt
fi


########################################
# 3. ALIAS restartcomfy
########################################

echo "🔧 Configurazione comando restartcomfy..."
wget -q https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/main/scripts/restart-comfyui.sh -O /usr/local/bin/restart-comfyui.sh || true
chmod +x /usr/local/bin/restart-comfyui.sh || true
echo "alias restartcomfy='/usr/local/bin/restart-comfyui.sh'" >> /root/.bashrc

########################################
# 4. INSTALLA COMFYUI-MANAGER
########################################

echo "🔧 Installazione ComfyUI-Manager..."
MANAGER_DIR="$CUSTOM_NODES_DIR/ComfyUI-Manager"
if [ ! -d "$MANAGER_DIR/.git" ]; then
  git clone --depth=1 https://github.com/ltdrdata/ComfyUI-Manager.git "$MANAGER_DIR"
  if [ -f "$MANAGER_DIR/requirements.txt" ]; then
    pip install -q --no-cache-dir -r "$MANAGER_DIR/requirements.txt"
  fi
else
  echo "✓ ComfyUI-Manager già presente"
fi

########################################
# 5. extra_model_paths.yaml (base vuota)
########################################

echo "⚙️  Configurazione percorsi modelli..."
cat > "$COMFY_DIR/extra_model_paths.yaml" <<EOF
runpod:
  base_path: $MODELS_DIR
  checkpoints: checkpoints
  unet: checkpoints
  diffusion_models: checkpoints
  vae: vae
  clip: clip
  loras: loras
  upscale_models: upscale_models
  controlnet: controlnet
EOF

########################################
# 6. AVVIO COMFYUI
########################################

echo "🌐 ComfyUI in avvio su porta 8188..."
cd "$COMFY_DIR"
python main.py \
  --listen 0.0.0.0 \
  --port 8188 \
  --enable-cors-header \
  > /tmp/comfyui.log 2>&1 &

sleep 5

########################################
# 7. INSTALLA JUPYTER LAB + TERMINALS
########################################

echo "🔧 Installazione Jupyter Lab con terminals..."
pip uninstall -y jupyter-server-terminals terminado >/dev/null 2>&1 || true
pip install -q --no-cache-dir terminado==0.18.0
pip install -q --no-cache-dir jupyter-server-terminals==0.5.0
pip install -q --no-cache-dir jupyterlab jupyter-server jupyterlab-server

echo "⚙️  Configurazione Jupyter..."
mkdir -p /root/.jupyter
cat > /root/.jupyter/jupyter_server_config.py << 'PYEOF'
c.ServerApp.allow_origin = '*'
c.ServerApp.disable_check_xsrf = True
c.ServerApp.token = ''
c.ServerApp.password = ''
c.IdentityProvider.token = ''
c.ServerApp.allow_remote_access = True
c.ServerApp.allow_credentials = True
PYEOF

echo "🌐 Avvio Jupyter Lab su porta 8888..."
jupyter lab \
  --ip=0.0.0.0 \
  --port=8888 \
  --no-browser \
  --allow-root \
  --notebook-dir=/tmp/comfyui \
  > /tmp/jupyter.log 2>&1 &

sleep 5

if ps aux | grep -q "[j]upyter lab"; then
  echo "✅ Jupyter Lab avviato correttamente su porta 8888"
else
  echo "❌ Errore avvio Jupyter, controlla /tmp/jupyter.log"
  tail -20 /tmp/jupyter.log || true
fi

########################################
# 8. WORKFLOW MANAGER (usa solo install.sh dei workflow)
########################################

echo "🔧 Installazione comando 'workflows'..."

cat > /usr/local/bin/workflows <<'WORKFLOWS_SCRIPT'
#!/usr/bin/env bash
set -e

REPO_BASE="https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/refs/heads/main/workflows"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

clear
echo -e "${BLUE}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║              ComfyUI Workflow Manager            ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Workflow disponibili:${NC}"
echo ""
echo " 1) BG Change"
echo "    └─ Workflow di esempio (background change con Qwen)"
echo ""
echo " Q) Esci"
echo ""
echo -e "${BLUE}──────────────────────────────────────────────────${NC}"
read -p "Seleziona workflow: " choice
echo ""

case "$choice" in
  1)
    NAME="bg-change"
    ;;
  [Qq])
    echo "Uscita..."
    exit 0
    ;;
  *)
    echo -e "${RED}Selezione non valida${NC}"
    exit 1
    ;;
esac

INSTALL_URL="$REPO_BASE/$NAME/install.sh"
TMP_SCRIPT="/tmp/workflow_install.sh"

echo -e "${BLUE}Scarico script di installazione per '${NAME}'...${NC}"
if curl -f -s "$INSTALL_URL" > "$TMP_SCRIPT"; then
  chmod +x "$TMP_SCRIPT"
  echo -e "${GREEN}Eseguo install.sh per '${NAME}'...${NC}"
  bash "$TMP_SCRIPT"
  rm "$TMP_SCRIPT"
else
  echo -e "${RED}❌ Errore nel download di $INSTALL_URL${NC}"
  exit 1
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║ ✅ Installazione workflow completata              ║${NC}"
echo -e "${GREEN}║ Esegui 'restartcomfy' per ricaricare ComfyUI     ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
WORKFLOWS_SCRIPT

chmod +x /usr/local/bin/workflows
echo "✅ Workflow manager installato! Usa: workflows"

########################################
# 9. RIASSUNTO
########################################

echo "✅ Setup completato!"
echo "   ComfyUI:  http://0.0.0.0:8188"
echo "   Jupyter:  http://0.0.0.0:8888"
echo "   Comandi:  restartcomfy, workflows"

# Mantieni il container attivo
wait
