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
echo "📥 Scarico lo script restart-comfyui.sh..."
wget -q https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/main/scripts/restart-comfyui.sh -O /usr/local/bin/restart-comfyui.sh
chmod +x /usr/local/bin/restart-comfyui.sh

echo "🔧 Alias per restartcomfy..."
echo "alias restartcomfy='/usr/local/bin/restart-comfyui.sh'" >> /root/.bashrc
source /root/.bashrc

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

# === MAPPA TIPO → CARTELLA ===
get_model_dir() {
    local tipo=$1
    case "$tipo" in
        checkpoint) echo "$MODELS_DIR/checkpoints" ;;
        lora) echo "$LORA_DIR" ;;
        vae) echo "$VAE_DIR" ;;
        text_encoder) echo "$MODELS_DIR/clip" ;;
        upscale) echo "$MODELS_DIR/upscale_models" ;;
        controlnet) echo "$CONTROLNET_DIR" ;;
        unet) echo "$MODELS_DIR/unet" ;;
        clip) echo "$MODELS_DIR/clip" ;;
        *) echo "$MODELS_DIR" ;;
    esac
}

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
: <<'SKIP_MODELS_DOWNLOAD'
# === SCARICA MODELLI DA FILE ===

echo "📋 Scarico lista modelli da GitHub..."
wget -q "$MODELS_LIST_URL" -O /tmp/modelli.txt || {
    echo "❌ Impossibile scaricare modelli.txt"
    exit 1
}

echo "📦 Download modelli da lista..."
while IFS='|' read -r filename url tipo; do
    # Salta commenti e vuoti
    [[ "$filename" =~ ^[[:space:]]*# ]] && continue
    [[ -z "$filename" ]] && continue
    
    # Usa funzione per ottenere cartella
    dest_dir=$(get_model_dir "$tipo")
    mkdir -p "$dest_dir"
    dest_file="$dest_dir/$filename"
    
    # Skip se esiste
    if [ -f "$dest_file" ]; then
        echo "  ✓ $(basename "$filename")"
    else
        echo "  📥 $(basename "$filename")..."
        download_model "$url" "$dest_file"
    fi
done < /tmp/modelli.txt

# === FINE DOWNLOAD MODELLI ===
SKIP_MODELS_DOWNLOAD
# === CUSTOM NODES ===
echo ""
echo "🔌 Installazione Custom Nodes..."
NODES_DIR="$COMFY_DIR/custom_nodes"
mkdir -p "$NODES_DIR"
: <<'SKIP_CUSTOM_NODES'

# === CUSTOM NODES DA FILE ===
CUSTOM_NODES_URL="https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/main/custom_nodes.txt"

echo "📥 Scarico lista custom nodes..."
wget -q "$CUSTOM_NODES_URL" -O /tmp/custom_nodes.txt || echo "⚠️  File custom_nodes.txt non trovato, salto"

if [ -f /tmp/custom_nodes.txt ]; then
    while IFS='|' read -r name repo; do
        [[ "$name" =~ ^[[:space:]]*# ]] && continue
        [[ -z "$name" ]] && continue
        
        node_path="$NODES_DIR/$name"
        
        if [ -d "$node_path/.git" ]; then
            echo "  ✓ $name"
        else
            echo "[$(date '+%H:%M:%S')] 📥 Inizio clone: $name"
            echo "   📍 Repository: $repo"
            git clone --depth=1 --progress "$repo" "$node_path" 2>&1 | while IFS= read -r line; do
                echo "   $line"
            done || {
                echo "[$(date '+%H:%M:%S')] ⚠️ Clone fallito: $name"
                continue
            }
            echo "[$(date '+%H:%M:%S')] ✅ Completato: $name"

            
            # Installa dipendenze
            [ -f "$node_path/requirements.txt" ] && \
                pip install -q --no-cache-dir -r "$node_path/requirements.txt" 2>/dev/null
            
            [ -f "$node_path/install.py" ] && \
                (cd "$node_path" && python install.py 2>/dev/null) || true
        fi
    done < /tmp/custom_nodes.txt
fi


echo "✓ Custom nodes installati"
SKIP_CUSTOM_NODES
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

echo "✅ Tutti i modelli scaricati"
# Crea extra_model_paths.yaml
echo "⚙️  Configurazione percorsi modelli..."
cat > /tmp/comfyui/extra_model_paths.yaml <<'EOF'
runpod:
    base_path: /tmp/comfyui/models/
    checkpoints: checkpoints
    unet: checkpoints
    diffusion_models: checkpoints
    vae: vae
    clip: clip
    loras: loras
    upscale_models: upscale_models
    controlnet: controlnet
EOF
# === CREA HOOK PRE-RESTART PER AUTO-SYNC WORKFLOWS ===
echo "🔧 Configurazione auto-sync workflows al restart..."

# Crea script di sync
cat > /tmp/comfyui/sync_workflows.sh <<'SYNCSCRIPT'
#!/bin/bash
WORKFLOWS_DIR="/tmp/comfyui/user/default/workflows"
WORKFLOWS_BASE_URL="https://api.github.com/repos/werhealthy/-runpod-comfyui-Havas/contents/workflows"

echo "[$(date '+%H:%M:%S')] 🔄 Auto-sync workflows da GitHub..."

workflow_files=$(curl -s "$WORKFLOWS_BASE_URL" | jq -r '.[] | select(.name | endswith(".json")) | .name')

if [ -z "$workflow_files" ]; then
    echo "[$(date '+%H:%M:%S')] ℹ️  Nessun workflow trovato"
    exit 0
fi

echo "$workflow_files" | while read workflow_name; do
    workflow_url="https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/main/workflows/$workflow_name"
    workflow_path="$WORKFLOWS_DIR/$workflow_name"
    
    if wget -q "$workflow_url" -O "$workflow_path"; then
        echo "[$(date '+%H:%M:%S')] ✅ Sincronizzato: $workflow_name"
    fi
done

echo "[$(date '+%H:%M:%S')] ✅ Sync workflows completato"
SYNCSCRIPT

chmod +x /tmp/comfyui/sync_workflows.sh

# Crea wrapper per python main.py che esegue sync prima di partire
cat > /tmp/comfyui/start_comfyui.sh <<'STARTSCRIPT'
#!/bin/bash
# Questo script wrappa main.py e sincronizza workflows prima dell'avvio

# Sync workflows se disponibile
if [ -f /tmp/comfyui/sync_workflows.sh ]; then
    bash /tmp/comfyui/sync_workflows.sh
fi

# Avvia ComfyUI
cd /tmp/comfyui
exec python main.py "$@"
STARTSCRIPT

chmod +x /tmp/comfyui/start_comfyui.sh

echo "✅ Auto-sync workflows configurato"
: <<'SKIP_AUTO_SYNC'
# === Sincronizza workflows e modelli automaticamente ===
echo "🔧 Sincronizzo i workflow e i modelli con GitHub..."

# Sincronizza workflows
WORKFLOWS_DIR="/tmp/comfyui/user/default/workflows"
WORKFLOWS_BASE_URL="https://api.github.com/repos/werhealthy/-runpod-comfyui-Havas/contents/workflows"

workflow_files=$(curl -s "$WORKFLOWS_BASE_URL" | jq -r '.[] | select(.name | endswith(".json")) | .name')
if [ -z "$workflow_files" ]; then
    echo "⚠️ Nessun workflow da sincronizzare"
else
    echo "$workflow_files" | while read workflow_name; do
        workflow_url="https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/main/workflows/$workflow_name"
        workflow_path="$WORKFLOWS_DIR/$workflow_name"
        wget -q "$workflow_url" -O "$workflow_path" && echo "✅ $workflow_name sincronizzato"
    done
fi

# Sincronizza modelli
MODELS_LIST_URL="https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/main/modelli.txt"
MODELS_DIR="/tmp/comfyui/models"
CHECKPOINT_DIR="$MODELS_DIR/checkpoints"
LORA_DIR="$MODELS_DIR/loras"
VAE_DIR="$MODELS_DIR/vae"

while IFS='|' read -r filename url tipo; do
    [[ "$filename" =~ ^[[:space:]]*# ]] && continue
    [[ -z "$filename" ]] && continue
    dest_dir=$(get_model_dir "$tipo")
    mkdir -p "$dest_dir"
    dest_path="$dest_dir/$filename"
    wget -q "$url" -O "$dest_path"
done < <(curl -s "$MODELS_LIST_URL")

# Sincronizza custom nodes
CUSTOM_NODES_URL="https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/main/custom_nodes.txt"
NODES_DIR="/tmp/comfyui/custom_nodes"
mkdir -p "$NODES_DIR"

echo "[$(date '+%H:%M:%S')] 🔌 Sincronizzo custom nodes..."

wget -q "$CUSTOM_NODES_URL" -O /tmp/custom_nodes.txt || {
    echo "[$(date '+%H:%M:%S')] ⚠️ File custom_nodes.txt non trovato" >&2
    exit 1
}

while IFS='|' read -r name repo; do
    [[ "$name" =~ ^[[:space:]]*# ]] && continue
    [[ -z "$name" ]] && continue

    node_path="$NODES_DIR/$name"

    if [ ! -d "$node_path/.git" ]; then
        echo "[$(date '+%H:%M:%S')] 📥 Clono custom node: $name"
        echo "   📍 Repo: $repo"
        git clone --depth=1 --progress "$repo" "$node_path" 2>&1 | while IFS= read -r line; do
            echo "   $line"
        done || {
            echo "[$(date '+%H:%M:%S')] ⚠️ Clone fallito: $name"
            continue
        }
        if [ -f "$node_path/requirements.txt" ]; then
            pip install -q --no-cache-dir -r "$node_path/requirements.txt" 2>/dev/null || echo "[$(date '+%H:%M:%S')] ⚠️ Install dipendenze fallito $name"
        fi
        if [ -f "$node_path/install.py" ]; then
            (cd "$node_path" && python install.py 2>/dev/null) || echo "[$(date '+%H:%M:%S')] ⚠️ Install.py fallito $name"
        fi
    else
        echo "[$(date '+%H:%M:%S')] ✓ Custom node già presente: $name"
    fi
done < /tmp/custom_nodes.txt
echo "[$(date '+%H:%M:%S')] ✅ Sincronizzazione custom nodes completata"
SKIP_AUTO_SYNC
# Avvia ComfyUI con wrapper auto-sync
cd "$COMFY_DIR"
echo "🌐 ComfyUI in avvio su porta 8188..."
# Usa wrapper che sincronizza workflows prima di partire
/tmp/comfyui/start_comfyui.sh \
    --listen 0.0.0.0 \
    --port 8188 \
    --enable-cors-header \
    --force-fp16 \
    --preview-method auto &

# Aspetta che ComfyUI si avvii
sleep 5

    
# === INSTALLA JUPYTER LAB CON TERMINALS ===
echo ""
echo "📓 Installazione Jupyter Lab con supporto terminals..."

# Disinstalla eventuali versioni problematiche
pip uninstall -y jupyter-server-terminals terminado 2>/dev/null || true

# Installa versioni specifiche testate
pip install -q --no-cache-dir terminado==0.18.0
pip install -q --no-cache-dir jupyter-server-terminals==0.5.0
pip install -q --no-cache-dir jupyterlab jupyter-server jupyterlab-server

# Verifica installazione
echo "🔍 Verifica moduli..."
python3 -c "import terminado; print('✅ terminado:', terminado.__version__)" || echo "⚠️  terminado non trovato"
python3 -c "import jupyter_server_terminals; print('✅ jupyter-server-terminals OK')" || echo "⚠️  jupyter-server-terminals non trovato"

# Crea config per bypassare XSRF/CORS (necessario per proxy Runpod)
echo "⚙️  Configurazione Jupyter per proxy..."
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

echo "🚀 Avvio Jupyter Lab su porta 8888..."
jupyter lab \
    --ip=0.0.0.0 \
    --port=8888 \
    --no-browser \
    --allow-root \
    --notebook-dir=/tmp/comfyui \
    > /tmp/jupyter.log 2>&1 &

# Attendi avvio
sleep 5

# Verifica che sia partito
if ps aux | grep -q "[j]upyter lab"; then
    echo "✅ Jupyter Lab avviato correttamente su porta 8888"
else
    echo "❌ Errore avvio Jupyter, controlla /tmp/jupyter.log"
    tail -20 /tmp/jupyter.log
fi


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
# === COMANDO DOWNLOAD MODELLI ===
cat > /usr/local/bin/download-models <<'SCRIPT'
#!/bin/bash
MODELS_LIST_URL="https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/main/modelli.txt"
MODELS_DIR="/tmp/comfyui/models"

echo "📦 Download modelli da modelli.txt..."
wget -q "$MODELS_LIST_URL" -O /tmp/modelli.txt

get_model_dir() {
    case "$1" in
        checkpoint) echo "$MODELS_DIR/checkpoints" ;;
        lora) echo "$MODELS_DIR/loras" ;;
        vae) echo "$MODELS_DIR/vae" ;;
        controlnet) echo "$MODELS_DIR/controlnet" ;;
        *) echo "$MODELS_DIR" ;;
    esac
}

while IFS='|' read -r filename url tipo; do
    [[ "$filename" =~ ^[[:space:]]*# ]] && continue
    [[ -z "$filename" ]] && continue
    
    dest_dir=$(get_model_dir "$tipo")
    mkdir -p "$dest_dir"
    dest_file="$dest_dir/$filename"
    
    if [ -f "$dest_file" ]; then
        echo "✓ $filename"
    else
        echo "📥 Scarico $filename..."
        wget -c -q --show-progress "$url" -O "$dest_file"
        echo "✅ $filename completato"
    fi
done < /tmp/modelli.txt
SCRIPT

chmod +x /usr/local/bin/download-models
echo "✅ Comando 'download-models' installato!"
# === COMANDO INSTALL CUSTOM NODES ===
cat > /usr/local/bin/install-nodes <<'SCRIPT'
#!/bin/bash
CUSTOM_NODES_URL="https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/main/custom_nodes.txt"
NODES_DIR="/tmp/comfyui/custom_nodes"

echo "🔌 Installazione custom nodes..."
wget -q "$CUSTOM_NODES_URL" -O /tmp/custom_nodes.txt

while IFS='|' read -r name repo; do
    [[ "$name" =~ ^[[:space:]]*# ]] && continue
    [[ -z "$name" ]] && continue
    
    node_path="$NODES_DIR/$name"
    
    if [ -d "$node_path/.git" ]; then
        echo "✓ $name già presente"
    else
        echo "📥 Installo $name..."
        git clone --depth=1 "$repo" "$node_path"
        
        [ -f "$node_path/requirements.txt" ] && \
            pip install -q --no-cache-dir -r "$node_path/requirements.txt"
        
        [ -f "$node_path/install.py" ] && \
            (cd "$node_path" && python install.py)
        
        echo "✅ $name installato"
    fi
done < /tmp/custom_nodes.txt
SCRIPT

chmod +x /usr/local/bin/install-nodes
echo "✅ Comando 'install-nodes' installato!"


echo "✅ Comando 'download-lora' installato!"
echo "   Usa: download-lora (da qualsiasi terminale)"

# === INSTALL WORKFLOWS COMMAND ===
echo "🔧 Installing workflow manager..."

cat > /usr/local/bin/workflows <<'WORKFLOWS_SCRIPT'
#!/bin/bash
REPO_BASE="https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/main/workflows"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

clear
echo -e "${BLUE}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          ComfyUI Workflow Manager               ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Available workflows:${NC}"
echo ""
echo "  1) Qwen Edit 2509 - Object Migration"
echo "     └─ Image editing with object insertion/removal"
echo ""
echo "  Q) Quit"
echo ""
echo -e "${BLUE}──────────────────────────────────────────────────${NC}"
read -p "Select workflow number: " choice
echo ""

case "$choice" in
    1)
        echo -e "${GREEN}Installing Qwen Edit 2509 workflow...${NC}"
        echo ""
        INSTALL_URL="$REPO_BASE/qwen-edit-2509/install.sh"
        if curl -f -s "$INSTALL_URL" > /tmp/workflow_install.sh; then
            chmod +x /tmp/workflow_install.sh
            bash /tmp/workflow_install.sh
            rm /tmp/workflow_install.sh
        else
            echo -e "${RED}❌ Error downloading installation script${NC}"
            exit 1
        fi
        ;;
    [Qq])
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid selection${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅ Installation complete!                       ║${NC}"
echo -e "${GREEN}║  Run 'restartcomfy' to reload ComfyUI           ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
WORKFLOWS_SCRIPT

chmod +x /usr/local/bin/workflows
echo "alias workflows='/usr/local/bin/workflows'" >> /root/.bashrc
echo "✅ Workflow manager installed! Type 'workflows' to use it."

echo "✅ Setup completato!"
echo "   ComfyUI: http://0.0.0.0:8188"
echo "   Jupyter: http://0.0.0.0:8888"
echo "   Comando: download-lora"

# Mantieni container attivo
wait

# Altri comandi di configurazione...

# Aggiungo alias restartcomfy per il riavvio user-friendly
echo "alias restartcomfy='/usr/local/bin/restart-comfyui.sh'" >> /root/.bashrc
source /root/.bashrc

# Eventuali altri comandi finali

