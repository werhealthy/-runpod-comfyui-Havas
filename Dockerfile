FROM runpod/comfyui:latest

# Lo script di avvio personalizzato (se serve)
COPY startup.sh /startup.sh
RUN chmod +x /startup.sh

# Esponi la porta web di ComfyUI
EXPOSE 8188

# Comando di avvio
CMD ["/startup.sh"]
