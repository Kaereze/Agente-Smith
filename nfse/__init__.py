"""Emissão de NFS-e pelo Emissor Nacional (Sefin Nacional / ADN).

Pacote novo (07/11/2026), separado do resto do Painel Fiscal. Por enquanto só fala com a PRODUÇÃO RESTRITA (ambiente de
teste do governo). A trava que impede qualquer outro endereço fica em `nfse/trava.py`.

Regras que valem para tudo aqui (ver nfse/LEIA-ME.md):
- Certificado (.pfx/.p12) e senha NUNCA entram no repositório, no log nem na conversa.
- Nada é emitido sem uma pessoa conferir e confirmar.
- POST de emissão nunca é repetido sozinho (pode duplicar nota).
- Dados de teste são sempre inventados (ADR-05).
"""
