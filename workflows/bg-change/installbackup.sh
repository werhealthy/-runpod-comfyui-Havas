#!/bin/bash
echo "✅ Installazione workflow: bg-change"

MODEL_DIR="/tmp/comfyui/models"
NODE_DIR="/tmp/comfyui/custom_nodes"

# Modelli (puoi aggiungere altri se servono solo a questo workflow)
wget -c --show-progress "https://huggingface.co/aidiffuser/Qwen-Image-Edit-2509/resolve/main/Qwen-Image-Edit-2509_fp8_e4m3fn.safetensors" -O $MODEL_DIR/diffusion_models/Qwen-Image-Edit-2509_fp8_e4m3fn.safetensors
wget -c --show-progress "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors" -O $MODEL_DIR/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors
wget -c --show-progress "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors" -O $MODEL_DIR/vae/qwen_image_vae.safetensors
wget -c --show-progress "https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-8steps-V1.1.safetensors" -O $MODEL_DIR/loras/Qwen-Image-Lightning-8steps-V1.1.safetensors

CUSTOM_NODES=(
  "ComfyUI-KJNodes|https://github.com/kijai/ComfyUI-KJNodes.git"
  "ComfyUI-RMBG|https://github.com/1038lab/ComfyUI-RMBG.git"
  "rgthree-comfy|https://github.com/rgthree/rgthree-comfy.git"
)

CUSTOM_NODES_DIR="/tmp/comfyui/custom_nodes"

for entry in "${CUSTOM_NODES[@]}"; do
  NAME=$(echo "$entry" | cut -d'|' -f1)
  REPO=$(echo "$entry" | cut -d'|' -f2)
  DEST="$CUSTOM_NODES_DIR/$NAME"
  if [ -d "$DEST/.git" ]; then
    echo "🔄 Aggiorno $NAME"
    cd "$DEST" && git pull && cd - > /dev/null
  else
    echo "📥 Clono $NAME"
    git clone --depth=1 "$REPO" "$DEST"
  fi
done

echo "🔧 Installa dipendenze Python custom nodes"
for folder in $CUSTOM_NODES_DIR/*; do
  [ -f "$folder/requirements.txt" ] && pip install -q --no-cache-dir -r "$folder/requirements.txt"
  [ -f "$folder/install.py" ] && python "$folder/install.py"
done
