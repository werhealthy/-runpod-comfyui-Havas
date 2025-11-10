#!/bin/bash

echo "🚀 Avvio ComfyUI con download modelli..."

# === VERIFICA/INSTALLA COMFYUI ===
COMFY_DIR="/tmp/comfyui"
if [ ! -d "$COMFY_DIR" ]; then
    echo "⚠️  ComfyUI non trovato, clonazione in corso..."
    git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git "$COMFY_DIR"
    cd "$COMFY_DIR"
    pip install --no-cache-dir -r requirements.txt
else
    echo "✓ ComfyUI già presente"
    cd "$COMFY_DIR"
fi

# === INSTALLA COMFYUI MANAGER ===
echo "🔧 Installazione ComfyUI Manager..."
MANAGER_DIR="$COMFY_DIR/custom_nodes/ComfyUI-Manager"
if [ ! -d "$MANAGER_DIR/.git" ]; then
    echo "  📥 Clone ComfyUI-Manager..."
    git clone --depth=1 https://github.com/ltdrdata/ComfyUI-Manager.git "$MANAGER_DIR"
    if [ -f "$MANAGER_DIR/requirements.txt" ]; then
        pip install -q --no-cache-dir -r "$MANAGER_DIR/requirements.txt"
    fi
else
    echo "  ✓ ComfyUI-Manager già presente"
fi

# Directory modelli temporanee
MODELS_DIR="/tmp/comfyui/models"
CHECKPOINT_DIR="$MODELS_DIR/checkpoints"
LORA_DIR="$MODELS_DIR/loras"
VAE_DIR="$MODELS_DIR/vae"
CONTROLNET_DIR="$MODELS_DIR/controlnet"
WORKFLOWS_DIR="/tmp/comfyui/user/default/workflows"

# Crea struttura directory
mkdir -p "$CHECKPOINT_DIR" "$LORA_DIR" "$VAE_DIR" "$CONTROLNET_DIR" "$WORKFLOWS_DIR"
MODELS_LIST_URL="https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/main/modelli.txt"

# Funzione per download con retry
download_model() {
    local url=$1
    local output=$2
    local max_retries=3
    local retry=0
    
    while [ $retry -lt $max_retries ]; do
        echo "📥 Download: $(basename $output)..."
        if wget -c -q --show-progress "$url" -O "$output"; then
            echo "✅ Download completato: $(basename $output)"
            return 0
        fi
        retry=$((retry + 1))
        echo "⚠️  Tentativo $retry fallito, riprovo..."
        sleep 2
    done
    
    echo "❌ Download fallito dopo $max_retries tentativi: $url"
    return 1
}

# === SCARICA MODELLI DA FILE ===

echo "📋 Scarico lista modelli da GitHub..."
wget -q "$MODELS_LIST_URL" -O /tmp/modelli.txt || {
    echo "❌ Impossibile scaricare modelli.txt"
    exit 1
}

echo "📦 Download modelli da lista..."
while IFS='|' read -r url category filename; do
    # Salta commenti e righe vuote
    [[ "$url" =~ ^#.*$ ]] || [[ -z "$url" ]] && continue
    
    # Determina directory destinazione
    case "$category" in
        "diffusion_models/wan")
            dest_dir="$MODELS_DIR/checkpoints"
            mkdir -p "$dest_dir"
            ;;
        "loras")
            dest_dir="$LORA_DIR"
            ;;
        "vae")
            dest_dir="$VAE_DIR"
            ;;
        "text_encoders")
            dest_dir="$MODELS_DIR/clip"
            mkdir -p "$dest_dir"
            ;;
        "upscale_models")
            dest_dir="$MODELS_DIR/upscale_models"
            mkdir -p "$dest_dir"
            ;;
        *)
            dest_dir="$MODELS_DIR/$category"
            mkdir -p "$dest_dir"
            ;;
    esac
    
    download_model "$url" "$dest_dir/$filename"
    
done < /tmp/modelli.txt

# === FINE DOWNLOAD MODELLI ===
# === CUSTOM NODES ===
echo ""
echo "🔌 Installazione Custom Nodes..."
NODES_DIR="$COMFY_DIR/custom_nodes"
mkdir -p "$NODES_DIR"

# Array repository custom nodes con link corretti
declare -A REPOS=(
  ["rgthree-comfy"]="https://github.com/rgthree/rgthree-comfy.git"
  ["ComfyUI_UltimateSDUpscale"]="https://github.com/ssitu/ComfyUI_UltimateSDUpscale.git"
  ["ComfyUI-Inspire-Pack"]="https://github.com/ltdrdata/ComfyUI-Inspire-Pack.git"
  ["comfy-image-saver"]="https://github.com/giriss/comfy-image-saver.git"
  ["was-node-suite-comfyui"]="https://github.com/WASasquatch/was-node-suite-comfyui.git"
  ["ComfyUI-KJNodes"]="https://github.com/kijai/ComfyUI-KJNodes.git"
)

for name in "${!REPOS[@]}"; do
  repo="${REPOS[$name]}"
  node_path="$NODES_DIR/$name"
  
  if [ ! -d "$node_path/.git" ]; then
    echo "  📥 Clone: $name"
    git clone --depth=1 "$repo" "$node_path" || {
      echo "  ⚠️  Clone fallito: $name"
      continue
    }
  else
    echo "  ✓ Già presente: $name"
  fi
  
  # Installa requirements.txt
  if [ -f "$node_path/requirements.txt" ]; then
    echo "    📦 Installo dipendenze per $name..."
    pip install -q --no-cache-dir -r "$node_path/requirements.txt" 2>/dev/null || {
      echo "    ⚠️  Alcune dipendenze fallite per $name"
    }
  fi
  
  # Esegui install.py se presente
  if [ -f "$node_path/install.py" ]; then
    echo "    🔧 Eseguo install.py per $name..."
    (cd "$node_path" && python install.py 2>/dev/null) || {
      echo "    ⚠️  install.py fallito per $name"
    }
  fi
done

echo "✓ Custom nodes installati"

# === WORKFLOWS ===
echo ""
echo "📋 Caricamento Workflows da GitHub..."

# Lista diretta dei workflow (più affidabile dell'API)
WORKFLOW_URLS=(
  "https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/main/workflows/Gen-image.json"
  # Aggiungi qui altri workflow quando ne hai
)

workflow_count=0

for workflow_url in "${WORKFLOW_URLS[@]}"; do
    workflow_name=$(basename "$workflow_url")
    workflow_path="$WORKFLOWS_DIR/$workflow_name"
    
    if [ -f "$workflow_path" ]; then
        echo "  ✓ Già presente: $workflow_name"
        ((workflow_count++))
        continue
    fi
    
    echo "  📥 Scarico workflow: $workflow_name"
    if wget -q "$workflow_url" -O "$workflow_path"; then
        echo "  ✅ Workflow salvato: $workflow_name"
        ((workflow_count++))
    else
        echo "  ⚠️  Download fallito: $workflow_name"
    fi
done

echo "✓ Workflow caricati: $workflow_count"



echo "✅ Tutti i modelli scaricati"
# Crea extra_model_paths.yaml
echo "⚙️  Configurazione percorsi modelli..."
cat > /tmp/comfyui/extra_model_paths.yaml <<'EOF'
runpod:
    base_path: /tmp/comfyui/models/
    checkpoints: checkpoints
    unet: checkpoints
    vae: vae
    clip: clip
    loras: loras
    upscale_models: upscale_models
EOF

# Avvia ComfyUI
cd "$COMFY_DIR"
echo "🌐 ComfyUI in avvio su porta 8188..."
python main.py \
    --listen 0.0.0.0 \
    --port 8188 \
    --enable-cors-header \
    --force-fp16 \
    --preview-method auto

