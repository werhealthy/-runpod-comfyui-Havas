#!/bin/bash

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔═════════════════════════════════════╗${NC}"
echo -e "${BLUE}║    🔄 Restart ComfyUI completo       ║${NC}"
echo -e "${BLUE}╚═════════════════════════════════════╝${NC}"

WORKFLOWS_DIR="/tmp/comfyui/user/default/workflows"
WORKFLOWS_BASE_URL="https://api.github.com/repos/werhealthy/-runpod-comfyui-Havas/contents/workflows"
MODELS_LIST_URL="https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/main/modelli.txt"
MODELS_DIR="/tmp/comfyui/models"
CUSTOM_NODES_FILE="https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/main/custom_nodes.txt"
NODES_DIR="/tmp/comfyui/custom_nodes"

download_model() {
    local url=$1
    local output=$2
    wget -q "$url" -O "$output" && echo -e "${GREEN}✓ Scaricato: $(basename "$output")${NC}" || echo -e "${RED}✗ Fallito download: $(basename "$output")${NC}"
}

get_model_dir() {
    local tipo=$1
    case "$tipo" in
        checkpoint) echo "$MODELS_DIR/checkpoints" ;;
        lora) echo "$MODELS_DIR/loras" ;;
        vae) echo "$MODELS_DIR/vae" ;;
        text_encoder) echo "$MODELS_DIR/clip" ;;
        upscale) echo "$MODELS_DIR/upscale_models" ;;
        controlnet) echo "$MODELS_DIR/controlnet" ;;
        *) echo "$MODELS_DIR" ;;
    esac
}

sync_workflows() {
    echo -e "${YELLOW}⏳ Sincronizzo workflows...${NC}"
    workflow_files=$(curl -s "$WORKFLOWS_BASE_URL" | jq -r '.[] | select(.name | endswith(".json")) | .name')
    for wf in $workflow_files; do
        download_model "https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/main/workflows/$wf" "$WORKFLOWS_DIR/$wf"
    done
}

sync_models() {
    echo -e "${YELLOW}⏳ Sincronizzo modelli...${NC}"
    wget -q "$MODELS_LIST_URL" -O /tmp/modelli.txt || { echo -e "${RED}Impossibile scaricare modelli.txt${NC}"; return; }
    while IFS='|' read -r filename url tipo; do
        [[ "$filename" =~ ^[[:space:]]*# ]] && continue
        [[ -z "$filename" ]] && continue
        dest_dir=$(get_model_dir "$tipo")
        mkdir -p "$dest_dir"
        dest_path="$dest_dir/$filename"
        if [ ! -f "$dest_path" ]; then
            download_model "$url" "$dest_path"
        else
            echo -e "${GREEN}✓ Presente: $filename${NC}"
        fi
    done < /tmp/modelli.txt
    echo -e "${GREEN}Sincronizzazione modelli completa${NC}"
}

sync_custom_nodes() {
    echo -e "${YELLOW}⏳ Sincronizzo custom nodes...${NC}"
    wget -q "$CUSTOM_NODES_FILE" -O /tmp/custom_nodes.txt || { echo -e "${RED}Impossibile scaricare custom_nodes.txt${NC}"; return; }
    while IFS='|' read -r name repo; do
        [[ "$name" =~ ^[[:space:]]*# ]] && continue
        [[ -z "$name" ]] && continue
        node_path="$NODES_DIR/$name"
        if [ ! -d "$node_path/.git" ]; then
            echo "📥 Clono $name..."
            git clone --depth=1 "$repo" "$node_path" || echo "⚠️ Clone fallito: $name"
            [ -f "$node_path/requirements.txt" ] && pip install -q -r "$node_path/requirements.txt"
            [ -f "$node_path/install.py" ] && (cd "$node_path" && python install.py)
        else
            echo -e "${GREEN}✓ Presente: $name${NC}"
        fi
    done < /tmp/custom_nodes.txt
    echo -e "${GREEN}Sincronizzazione custom nodes completata${NC}"
}

echo -e "${BLUE}Sincronizzo tutti gli elementi...${NC}"
sync_workflows
sync_models
sync_custom_nodes

# Ferma ComfyUI se attivo
pid=$(pgrep -f "python main.py")
if [ ! -z "$pid" ]; then
    echo "⏹️ Stop ComfyUI (pid $pid)"
    kill $pid
    sleep 3
fi

# Riavvia ComfyUI
echo "🚀 Avvio ComfyUI..."
cd /tmp/comfyui
python main.py --listen 0.0.0.0 --port 8188 --enable-cors-header --force-fp16 --preview-method auto &
sleep 5
echo -e "${GREEN}✔ ComfyUI avviato.${NC}"

EOF
