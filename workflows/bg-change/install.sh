#!/usr/bin/env bash
set -e

echo "[BG CHANGE] Installazione workflow BG Change..."

COMFY_DIR="/tmp/comfyui"
WORKFLOWS_DIR="$COMFY_DIR/user/default/workflows"
mkdir -p "$WORKFLOWS_DIR"

########################################
# 1. COPIA DEL WORKFLOW JSON IN COMFYUI
########################################

# Se cambi nome al file JSON, aggiorna questa riga:
WORKFLOW_URL="https://raw.githubusercontent.com/werhealthy/-runpod-comfyui-Havas/refs/heads/main/workflows/bg-change/bg-change.json"

echo "[BG CHANGE] Scarico il file JSON del workflow..."
curl -fSL "$WORKFLOW_URL" -o "$WORKFLOWS_DIR/bg-change.json"

echo "[BG CHANGE] Workflow copiato in: $WORKFLOWS_DIR/bg-change.json"

########################################
# 2. (IN FUTURO) MODELLI E CUSTOM NODES
########################################
# Qui in futuro puoi aggiungere:
# - comandi wget per checkpoint / lora
# - git clone per custom nodes specifici
# Per ora lasciamo vuoto.

########################################
# 3. SETUP FRONTEND (usa frontend_product_demo)
########################################

FRONTEND_ROOT="/tmp/havas_frontends"
FRONTEND_DIR="$FRONTEND_ROOT/bg-change"
REPO_GIT="https://github.com/werhealthy/-runpod-comfyui-Havas.git"

mkdir -p "$FRONTEND_ROOT"

if [ ! -d "$FRONTEND_DIR" ]; then
  echo "[BG CHANGE] Clono il repo per recuperare il frontend..."
  git clone --depth 1 "$REPO_GIT" "$FRONTEND_DIR-repo"

  if [ -d "$FRONTEND_DIR-repo/frontend_product_demo" ]; then
    mv "$FRONTEND_DIR-repo/frontend_product_demo" "$FRONTEND_DIR"
    rm -rf "$FRONTEND_DIR-repo"
    echo "[BG CHANGE] Frontend copiato in $FRONTEND_DIR"
  else
    echo "[BG CHANGE] ATTENZIONE: non trovo 'frontend_product_demo' nel repo clonato."
  fi
else
  echo "[BG CHANGE] Frontend già presente in $FRONTEND_DIR"
fi

if [ -d "$FRONTEND_DIR" ]; then
  echo "[BG CHANGE] Installo requirements del frontend..."
  if [ -f "$FRONTEND_DIR/requirements.txt" ]; then
    pip install -r "$FRONTEND_DIR/requirements.txt"
  else
    echo "[BG CHANGE] Nessun requirements.txt trovato nel frontend."
  fi

  echo "[BG CHANGE] Creo comando 'run-bg-change-frontend'..."
  cat >/usr/local/bin/run-bg-change-frontend <<EOF
#!/usr/bin/env bash
cd "$FRONTEND_DIR"
nohup python3 app.py > /tmp/bg-change-frontend.log 2>&1 &
echo "Frontend BG Change avviato su http://0.0.0.0:7860 (log: /tmp/bg-change-frontend.log)"
EOF
  chmod +x /usr/local/bin/run-bg-change-frontend

  echo "[BG CHANGE] Avvio subito il frontend..."
  /usr/local/bin/run-bg-change-frontend
else
  echo "[BG CHANGE] Frontend non disponibile, salto setup Gradio."
fi

echo "[BG CHANGE] Installazione completata. Se vuoi, esegui 'restartcomfy' per ricaricare ComfyUI."
