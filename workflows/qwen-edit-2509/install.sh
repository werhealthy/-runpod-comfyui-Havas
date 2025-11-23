#!/bin/bash
# Qwen Edit 2509 - Complete Installation Script
# All-in-one: models + custom nodes + verification

echo "╔══════════════════════════════════════════════════╗"
echo "║  Qwen Edit 2509 - Installation Setup            ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# === 1. INSTALL CUSTOM NODES ===
echo "📦 Installing Custom Nodes..."

NODES_DIR="/tmp/comfyui/custom_nodes"
mkdir -p "$NODES_DIR"

# Custom nodes array: name|repository
declare -a CUSTOM_NODES=(
    "ComfyUI-Manager|https://github.com/ltdrdata/ComfyUI-Manager"
    "rgthree-comfy|https://github.com/rgthree/rgthree-comfy"
    "ComfyUI_essentials|https://github.com/cubiq/ComfyUI_essentials.git"
    "ComfyUI-KJNodes|https://github.com/kijai/ComfyUI-KJNodes.git"
    "ComfyUI_LayerStyle|https://github.com/chflame163/ComfyUI_LayerStyle.git"
    "ComfyUI-Inpaint-CropAndStitch|https://github.com/lquesada/ComfyUI-Inpaint-CropAndStitch.git"
    "Comfyui-QwenEditUtils|https://github.com/lrzjason/Comfyui-QwenEditUtils.git"
    "ComfyUI-QualityOfLifeSuit_Omar92|https://github.com/omar92/ComfyUI-QualityOfLifeSuit_Omar92.git"
)

for node_entry in "${CUSTOM_NODES[@]}"; do
    IFS='|' read -r name repo <<< "$node_entry"
    node_path="$NODES_DIR/$name"
    
    if [ -d "$node_path/.git" ]; then
        echo "  ✓ $name"
    else
        echo "  📥 Installing: $name"
        git clone --depth=1 "$repo" "$node_path" || continue
        
        [ -f "$node_path/requirements.txt" ] && \
            pip install -q --no-cache-dir -r "$node_path/requirements.txt" 2>/dev/null
        
        [ -f "$node_path/install.py" ] && \
            (cd "$node_path" && python install.py 2>/dev/null) || true
    fi
done

echo "✅ Custom nodes installed!"
echo ""

# === 2. INSTALL MODELS ===
echo "📥 Installing Models..."

# Create directories
mkdir -p /tmp/comfyui/models/diffusion_models
mkdir -p /tmp/comfyui/models/text_encoders
mkdir -p /tmp/comfyui/models/vae
mkdir -p /tmp/comfyui/models/loras

# Models array: filename|url|type
declare -a MODELS=(
    "qwen_image_edit_fp8_e4m3fn.safetensors|https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_fp8_e4m3fn.safetensors|diffusion_models"
    "qwen_2.5_vl_7b_fp8_scaled.safetensors|https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors|text_encoders"
    "qwen_image_vae.safetensors|https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors|vae"
    "Qwen-Image-Edit-2509-Lightning-8steps-V1.0-fp32.safetensors|https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Edit-2509/Qwen-Image-Edit-2509-Lightning-8steps-V1.0-fp32.safetensors|loras"
    "Qwen-Image-Lightning-8steps-V1.1.safetensors|https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-8steps-V1.1.safetensors|loras"
)

for model_entry in "${MODELS[@]}"; do
    IFS='|' read -r filename url type <<< "$model_entry"
    dest="/tmp/comfyui/models/$type/$filename"
    
    if [ -f "$dest" ]; then
        echo "  ✓ $filename"
    else
        echo "  📥 Downloading: $filename"
        wget -c --show-progress "$url" -O "$dest"
        echo "  ✅ Completed: $filename"
    fi
done

echo ""
echo "✅ All models installed!"
echo ""

# === 3. VERIFY INSTALLATION ===
echo "🔍 Verifying installation..."
echo ""
echo "Custom Nodes:"
ls -1 /tmp/comfyui/custom_nodes/ | grep -v "__pycache__"
echo ""
echo "Models:"
echo "  Diffusion: $(ls -1 /tmp/comfyui/models/diffusion_models/*.safetensors 2>/dev/null | wc -l) file(s)"
echo "  CLIP: $(ls -1 /tmp/comfyui/models/text_encoders/*.safetensors 2>/dev/null | wc -l) file(s)"
echo "  VAE: $(ls -1 /tmp/comfyui/models/vae/*.safetensors 2>/dev/null | wc -l) file(s)"
echo "  LoRA: $(ls -1 /tmp/comfyui/models/loras/*.safetensors 2>/dev/null | wc -l) file(s)"
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  ✅ Installation Complete!                       ║"
echo "║  Restart ComfyUI to load the new setup           ║"
echo "╚══════════════════════════════════════════════════╝"
