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

# === SCARICA I TUOI MODELLI QUI ===

# Esempio: Stable Diffusion 1.5
download_model \
    "https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors" \
    "$CHECKPOINT_DIR/sd15.safetensors"

# Esempio: VAE
download_model \
    "https://huggingface.co/stabilityai/sd-vae-ft-mse-original/resolve/main/vae-ft-mse-840000-ema-pruned.safetensors" \
    "$VAE_DIR/vae-ft-mse.safetensors"

# === FINE DOWNLOAD MODELLI ===

echo "✅ Tutti i modelli scaricati"

# Avvia ComfyUI
cd /tmp/comfyui
echo "🌐 ComfyUI in avvio su porta 8188..."
python main.py --listen 0.0.0.0 --port 8188
