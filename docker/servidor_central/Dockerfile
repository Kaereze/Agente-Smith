# Servidor central do Painel Fiscal. Só usa a biblioteca padrão do Python: nada para instalar.
FROM python:3.12-slim
WORKDIR /app
COPY src/servidor_central /app/servidor_central
ENV PYTHONUNBUFFERED=1 CENTRAL_BANCO=/dados/central.sqlite
EXPOSE 8770
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8770/v1/saude', timeout=4).status == 200 else 1)"
CMD ["python", "-m", "servidor_central"]
