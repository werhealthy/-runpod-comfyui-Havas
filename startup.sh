#!/bin/bash

echo "🚀 Avvio ComfyUI con download modelli..."

# Directory modelli temporanee
MODELS_DIR="/tmp/comfyui/models"
CHECKPOINT_DIR="$MODELS_DIR/checkpoints"
LORA_DIR="$MODELS_DIR/loras"
VAE_DIR="$MODELS_DIR/vae"
CONTROLNET_DIR="$MODELS_DIR/controlnet"

# Crea struttura directory
mkdir -p "$CHECKPOINT_DIR" "$LORA_DIR" "$VAE_DIR" "$CONTROLNET_DIR"
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
NODES_DIR="/tmp/comfyui/custom_nodes"
mkdir -p "$NODES_DIR"

# Rileggi il file modelli.txt per i custom nodes
wget -q "$MODELS_LIST_URL" -O /tmp/modelli_nodes.txt 2>/dev/null || {
    echo "⚠️  Riuso cache locale"
    cp /tmp/modelli.txt /tmp/modelli_nodes.txt
}

while IFS='|' read -r url category name; do
    # Salta tutto tranne i custom nodes
    [[ "$url" =~ ^#.*$ ]] || [[ -z "$url" ]] && continue
    [[ "$category" != "node" ]] && continue
    
    node_path="$NODES_DIR/$name"
    
    # Clone o skip se esiste
    if [ ! -d "$node_path/.git" ]; then
        echo "  📥 Clone: $name"
        git clone --depth=1 "$url" "$node_path" || {
            echo "  ⚠️  Clone fallito: $name"
            continue
        }
    else
        echo "  ✓ Già presente: $name"
    fi
    
    # Installa requirements.txt
    if [ -f "$node_path/requirements.txt" ]; then
        echo "    📦 Installo dipendenze..."
        pip install -q --no-cache-dir -r "$node_path/requirements.txt" 2>/dev/null || true
    fi
    
    # Esegui install.py se presente
    if [ -f "$node_path/install.py" ]; then
        echo "    🔧 Eseguo install.py..."
        (cd "$node_path" && python install.py 2>/dev/null) || true
    fi
    
done < /tmp/modelli_nodes.txt

echo "✓ Custom nodes installati"

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
cd /tmp/comfyui
echo "🌐 ComfyUI in avvio su porta 8188..."
python main.py \
    --listen 0.0.0.0 \
    --port 8188 \
    --enable-cors-header \
    --force-fp16 \
    --preview-method auto

