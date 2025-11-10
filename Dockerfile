FROM runpod/pytorch:2.1.0-py3.10-cuda12.1.1-devel-ubuntu22.04

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

# Installa ComfyUI Manager (opzionale ma utile)
RUN cd /tmp/comfyui/custom_nodes && \
    git clone https://github.com/ltdrdata/ComfyUI-Manager.git

# Copia lo script di avvio
COPY startup.sh /startup.sh
RUN chmod +x /startup.sh

# Esponi la porta web di ComfyUI
EXPOSE 8188

# Comando di avvio
CMD ["/startup.sh"]
