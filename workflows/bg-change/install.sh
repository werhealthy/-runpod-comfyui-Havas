#!/bin/bash
echo "✅ Installazione workflow: bg-change"

MODEL_DIR="/tmp/comfyui/models"
NODE_DIR="/tmp/comfyui/custom_nodes"

# Modelli (puoi aggiungere altri se servono solo a questo workflow)
wget -c --show-progress "https://huggingface.co/aidiffuser/Qwen-Image-Edit-2509/resolve/main/Qwen-Image-Edit-2509_fp8_e4m3fn.safetensors" -O $MODEL_DIR/diffusion_models/Qwen-Image-Edit-2509_fp8_e4m3fn.safetensors
wget -c --show-progress "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors" -O $MODEL_DIR/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors
wget -c --show-progress "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors" -O $MODEL_DIR/vae/qwen_image_vae.safetensors
wget -c --show-progress "https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-8steps-V1.1.safetensors" -O $MODEL_DIR/loras/Qwen-Image-Lightning-8steps-V1.1.safetensors

# Custom nodes
cd $NODE_DIR
git clone --depth=1 https://github.com/rgthree/rgthree-comfy.git || echo "custom node già presente"
git clone --depth=1 https://github.com/kijai/ComfyUI-KJNodes.git || echo "custom node già presente"
git clone --depth=1 https://github.com/1038lab/ComfyUI-RMBG.git || echo "custom node già presente"
git clone --depth=1 https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes.git || echo "custom node già presente"
git clone --depth=1 https://github.com/lrzjason/Comfyui-QwenEditUtils.git || echo "custom node già presente"
git clone --depth=1 https://github.com/ltdrdata/was-node-suite-comfyui.git || echo "custom node già presente"
