# Usa l'immagine PyTorch più recente di Runpod (novembre 2025)
FROM runpod/pytorch:1.0.2-cu1281-torch271-ubuntu2204

# Imposta directory di lavoro temporanea
WORKDIR /tmp/comfyui

# Installa dipendenze di sistema
RUN apt-get update && apt-get install -y \
    git \
    wget \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Clona ComfyUI (ultima versione stabile)
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /tmp/comfyui

# Installa dipendenze Python
RUN pip install --no-cache-dir -r /tmp/comfyui/requirements.txt

# Installa ComfyUI Manager
RUN cd /tmp/comfyui/custom_nodes && \
    git clone https://github.com/ltdrdata/ComfyUI-Manager.git

# Copia lo script di avvio
COPY startup.sh /startup.sh
RUN chmod +x /startup.sh

# Esponi la porta web di ComfyUI
EXPOSE 8188

# Comando di avvio
CMD ["/startup.sh"]
