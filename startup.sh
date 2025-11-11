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
    # Salta commenti (righe che iniziano con #)
    [[ "$url" =~ ^[[:space:]]*# ]] && continue
    # Salta righe vuote
    [[ -z "$url" ]] && continue
    
    # Determina directory destinazione
    case "$category" in
        "diffusion_models/wan")
            dest_dir="$MODELS_DIR/checkpoints"  # Root checkpoints, non wan/
            mkdir -p "$dest_dir"
            # Rimuovi sottocartella dal filename se presente
            filename=$(basename "$filename")
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
  ["RES4LYF"]="https://github.com/ClownsharkBatwing/RES4LYF.git"
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

# URL base della cartella workflows
WORKFLOWS_BASE_URL="https://api.github.com/repos/werhealthy/-runpod-comfyui-Havas/contents/workflows"

# Scarica lista file dalla cartella workflows usando jq per parsing JSON
echo "  📂 Recupero lista workflows..."

# Installa jq se non presente
if ! command -v jq &> /dev/null; then
    echo "  📦 Installo jq..."
    apt-get update -qq && apt-get install -y -qq jq > /dev/null 2>&1
fi

# Scarica e parsea JSON con jq
workflow_files=$(curl -s "$WORKFLOWS_BASE_URL" | jq -r '.[] | select(.name | endswith(".json")) | .name')

if [ -z "$workflow_files" ]; then
    echo "  ⚠️  Nessun workflow trovato nella cartella workflows/"
    echo "  💡 Verifica: https://github.com/werhealthy/-runpod-comfyui-Havas/tree/main/workflows"
else
    echo "  ✅ Trovati workflow:"
    echo "$workflow_files" | while read workflow_name; do
        echo "    - $workflow_name"
    done
    
    # Download workflows
    echo "$workflow_files" | while read workflow_name; do
        workflow_url="https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/main/workflows/$workflow_name"
        workflow_path="$WORKFLOWS_DIR/$workflow_name"
        
        if [ -f "$workflow_path" ]; then
            echo "  ✓ Già presente: $workflow_name"
            continue
        fi
        
        echo "  📥 Scarico workflow: $workflow_name"
        if wget -q "$workflow_url" -O "$workflow_path"; then
            echo "  ✅ Workflow salvato: $workflow_name"
        else
            echo "  ⚠️  Download fallito: $workflow_name"
        fi
    done
fi

workflow_count=$(ls -1 "$WORKFLOWS_DIR"/*.json 2>/dev/null | wc -l)
echo "✓ Workflow caricati: $workflow_count"

# === LORA PERSONALIZZATI ===
echo ""
echo "📦 Caricamento LoRA personalizzati da GitHub..."

# URL base della cartella loras
LORAS_BASE_URL="https://api.github.com/repos/werhealthy/-runpod-comfyui-Havas/contents/loras"
LORAS_DIR="$MODELS_DIR/loras"

# Installa jq se non presente
command -v jq &> /dev/null || apt-get install -y -qq jq

# Scarica lista file
lora_files=$(curl -s "$LORAS_BASE_URL" | jq -r '.[] | select(.name | endswith(".safetensors")) | .name')

if [ -z "$lora_files" ]; then
    echo "  ℹ️  Nessun LoRA personalizzato trovato"
else
    echo "  ✅ Trovati $(echo "$lora_files" | wc -l) LoRA personalizzati"
    echo "$lora_files" | while read lora_name; do
        lora_url="https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/main/loras/$lora_name"
        lora_path="$LORAS_DIR/$lora_name"
        
        if [ -f "$lora_path" ]; then
            echo "  ✓ Già presente: $lora_name"
        else
            echo "  📥 Scarico LoRA: $lora_name"
            wget -q "$lora_url" -O "$lora_path" && \
                echo "  ✅ Salvato: $lora_name" || \
                echo "  ⚠️  Fallito: $lora_name"
        fi
    done
fi

lora_count=$(ls -1 "$LORAS_DIR"/*.safetensors 2>/dev/null | wc -l)
echo "✓ LoRA disponibili: $lora_count"

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
    
# === INSTALLA JUPYTER ===
echo ""
echo "📓 Installazione Jupyter Lab..."
pip install -q jupyterlab

echo "🚀 Avvio Jupyter Lab su porta 8889..."
nohup jupyter lab \
    --ip=0.0.0.0 \
    --port=8888 \
    --no-browser \
    --allow-root \
    --NotebookApp.token='' \
    --NotebookApp.password='' \
    > /tmp/jupyter.log 2>&1 &

echo "✅ Jupyter Lab disponibile su porta 8888"

# === CREA ALIAS PER DOWNLOAD ON-DEMAND ===
echo "🔧 Configurazione comandi rapidi..."

# Crea script di download nel pod
cat > /usr/local/bin/download-lora <<'SCRIPT'
#!/bin/bash
LORA_DIR="/tmp/comfyui/models/loras"
CONFIG_URL="https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/main/modelli_opzionali.txt"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

clear
echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   📦 DOWNLOAD LORA ON-DEMAND            ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"

wget -q "$CONFIG_URL" -O /tmp/modelli_opzionali.txt || {
    echo -e "${RED}❌ Errore download config${NC}"
    exit 1
}

declare -A MODELS_NAME
declare -A MODELS_URL
declare -A MODELS_DESC
index=1

while IFS='|' read -r name url desc; do
    [[ "$name" =~ ^[[:space:]]*# ]] && continue
    [[ -z "$name" ]] && continue
    MODELS_NAME[$index]="$name"
    MODELS_URL[$index]="$url"
    MODELS_DESC[$index]="$desc"
    ((index++))
done < /tmp/modelli_opzionali.txt

total_models=$((index - 1))

if [ $total_models -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Nessun modello trovato${NC}"
    exit 1
fi

echo -e "\n${GREEN}LoRA disponibili:${NC}\n"

for i in $(seq 1 $total_models); do
    name="${MODELS_NAME[$i]}"
    desc="${MODELS_DESC[$i]}"
    
    if [ -f "$LORA_DIR/$name.safetensors" ]; then
        status="${GREEN}[SCARICATO]${NC}"
    else
        status="${YELLOW}[DA SCARICARE]${NC}"
    fi
    
    printf "%2d) %-30s %s\n   %s\n\n" "$i" "$name" "$status" "$desc"
done

echo -e "${BLUE}───────────────────────────────────────────${NC}"
echo "  3          → Scarica solo modello 3"
echo "  1,3,5      → Scarica modelli 1, 3 e 5"
echo "  1-4        → Scarica da 1 a 4"
echo "  A          → Scarica TUTTI"
echo "  L          → Lista già scaricati"
echo "  Q          → Esci"
echo -e "${BLUE}───────────────────────────────────────────${NC}\n"

read -p "Seleziona: " choice

download_model() {
    local idx=$1
    local name="${MODELS_NAME[$idx]}"
    local url="${MODELS_URL[$idx]}"
    local dest="$LORA_DIR/$name.safetensors"
    
    if [ -f "$dest" ]; then
        echo -e "  ${GREEN}✓ Già presente: $name${NC}"
        return 0
    fi
    
    echo "  📥 Scarico: $name..."
    wget -c -q --show-progress "$url" -O "$dest" && \
        echo -e "  ${GREEN}✅ Completato: $name${NC}" || \
        echo -e "  ${RED}❌ Fallito: $name${NC}"
}

case "$choice" in
    [Qq]) echo "👋 Uscita..."; exit 0 ;;
    [Ll])
        echo -e "\n${GREEN}📦 LoRA già scaricati:${NC}\n"
        ls -1 "$LORA_DIR"/*.safetensors 2>/dev/null | xargs -n1 basename || echo "  Nessuno"
        exit 0
        ;;
    [Aa])
        echo -e "\n${BLUE}📥 Download TUTTI...${NC}\n"
        for i in $(seq 1 $total_models); do
            download_model "$i"
        done
        ;;
    *-*)
        start=$(echo "$choice" | cut -d'-' -f1)
        end=$(echo "$choice" | cut -d'-' -f2)
        if [ "$start" -ge 1 ] && [ "$end" -le "$total_models" ] && [ "$start" -le "$end" ]; then
            echo -e "\n${BLUE}📥 Download $start-$end...${NC}\n"
            for i in $(seq "$start" "$end"); do
                download_model "$i"
            done
        fi
        ;;
    *,*)
        echo -e "\n${BLUE}📥 Download selezionati...${NC}\n"
        IFS=',' read -ra MODELS <<< "$choice"
        for i in "${MODELS[@]}"; do
            i=$(echo "$i" | xargs)
            [ "$i" -ge 1 ] && [ "$i" -le "$total_models" ] && download_model "$i"
        done
        ;;
    [0-9]*)
        [ "$choice" -ge 1 ] && [ "$choice" -le "$total_models" ] && {
            echo -e "\n${BLUE}📥 Download modello $choice...${NC}\n"
            download_model "$choice"
        }
        ;;
esac

echo -e "\n${GREEN}✨ Done! Refresh ComfyUI per vedere i nuovi LoRA.${NC}"
SCRIPT

chmod +x /usr/local/bin/download-lora

echo "✅ Comando 'download-lora' installato!"
echo "   Usa: download-lora (da qualsiasi terminale)"

