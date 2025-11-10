# Usa l'immagine ComfyUI ufficiale di Runpod (già pronta)
FROM runpod/comfyui:latest

# Script di avvio personalizzato
COPY startup.sh /startup.sh
RUN chmod +x /startup.sh

# Esponi la porta
EXPOSE 8188

# Avvio
CMD ["/startup.sh"]
