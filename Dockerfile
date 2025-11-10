# Usa immagine PyTorch base senza ComfyUI pre-installato
FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-devel

# Installa dipendenze di sistema
RUN apt-get update && apt-get install -y \
    git \
    wget \
    curl \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copia lo script di avvio
COPY startup.sh /startup.sh
RUN chmod +x /startup.sh

# Esponi la porta
EXPOSE 8188

# Comando di avvio
CMD ["/startup.sh"]
