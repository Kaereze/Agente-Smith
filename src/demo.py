"""Modo demonstração: o Painel inteiro com dados FICTÍCIOS — pra abrir no PC de casa, sem Google, sem Outlook,
sem chave e sem Dropbox (pedido do usuário, 08/10/2026).

    python src\\app_servidor.py --demo        (ou PAINEL_DEMO_EM_CASA.bat, que clona/atualiza e abre)

Hotéis, caixas e agentes são os reais da rede (endereços da empresa). Hóspedes, CPFs, CNPJs, e-mails, textos e
números de NF são inventados (sementes fixas: os mesmos dados toda vez). Nada sai deste PC: "responder", "excluir"
e "encaminhar" só fingem — o e-mail some da caixa como se o Outlook do PC dono tivesse feito.
"""
import datetime
import hashlib
import random

import app_dados as dados
import atividade
import envio_nf
import espelho_emails as ee
import ligacoes
import rede_pcs
from sheets import STATUS_LINHAS

CENTRAL = "DEMO"
PCS = {"João": "DEMO-JOAO", "Clara": "DEMO-CLARA", "Cristian": "DEMO-CRISTIAN", "Bernardo": "DEMO-BERNARDO"}
DESLIGADO = "Bernardo"   # um PC desligado, pra ver o aviso e a fila de espera
HOTEIS = [
    ("AMAZONIA", "notafiscal@redeandradeamazonia.com.br", "Cristian"),
    ("AQUARIUS", "notafiscal@redeandradeaquarius.com.br", "Cristian"),
    ("ARACAJU", "notafiscal@redeandradearacaju.com.br", "Clara"),
    ("ARARAS", "notafiscal@redeandradeararas.com.br", "Bernardo"),
    ("ATLÂNTICO", "notafiscal@redeandradeatlantico.com.br", "Bernardo"),
    ("BAHIA", "notafiscal@redeandradebahia.com.br", "João"),
    ("BARRA", "notafiscal@redeandradebarra.com.br", "Cristian"),
    ("BARRAVENTO", "notafiscal@redeandradebarravento.com.br", "Bernardo"),
    ("BAÍA DOS CORAIS", "notafiscal@redeandradebaiadoscorais.com.br", "Bernardo"),
    ("BELLO MARE", "notafiscal@redeandradebellomare.com.br", "Bernardo"),
    ("BITON", "notafiscal@redeandradebiton.com.br", "João"),
    ("BOA VIAGEM", "notafiscal@redeandradeboaviagem.com.br", "João"),
    ("BRAZ", "notafiscal@redeandradebraz.com.br", "Clara"),
    ("CALAMARINA", "notafiscal@redeandradecalamarina.com.br", "Bernardo"),
    ("CANADA", "notafiscal@redeandradecanada.com.br", "Clara"),
    ("CASA BLANCA", "notafiscal@redeandradecasablanca.com.br", "João"),
    ("CECOMTUR", "notafiscal@hotelcecomturflorianopolis.com.br", "João"),
    ("CENTER PREMIUM", "notafiscal@redeandradecenterpremium.com.br", "Clara"),
    ("COIMBRA", "notafiscal@redeandradecoimbra.com.br", "João"),
    ("COMFORT", "notafiscal@redeandradecomfort.com.br", "João"),
    ("CRICIÚMA", "notafiscal@redeandradecriciuma.com.br", "Cristian"),
    ("DOCAS", "notafiscal@redeandradedocas.com.br", "Clara"),
    ("DUNAS HOTEL", "notafiscal@redeandradedunashotel.com.br", "Cristian"),
    ("ESTRELA CENTRO", "notafiscal@estreladalvacentrohotel.com.br", "João"),
    ("ESTRELA DALVA PRAIA", "notafiscal@estreladalvapraiahotel.com.br", "Clara"),
    ("EXPRESS", "notafiscal@redeandradeexpress.com.br", "Bernardo"),
    ("FROTA", "notafiscal@redeandradefrota.com.br", "Bernardo"),
    ("GALEÃO", "notafiscal@redeandradegaleao.com.br", "Bernardo"),
    ("GOIÂNIA CENTRO", "notafiscal@redeandradegoianiacentro.com.br", "Cristian"),
    ("GUAÍRA", "notafiscal@redeandradeguaira.com.br", "Bernardo"),
    ("GV", "notafiscal@redeandradegv.com.br", "Bernardo"),
    ("HANGAR", "notafiscal@hotelhangar.com.br", "Cristian"),
    ("ITABUNA", "notafiscal@redeandradeitabuna.com.br", "Clara"),
    ("JANGADEIRO", "notafiscal@redeandradejangadeiro.com.br", "João"),
    ("JERI", "notafiscal@redeandradejerihotel.com.br", "João"),
    ("L GINN", "notafiscal@redeandradelginn.com.br", "Clara"),
    ("LAGOA", "notafiscal@redeandradelagoa.com.br", "João"),
    ("LAPA", "notafiscal@redeandradelapa.com.br", "Cristian"),
    ("LUXOR", "notafiscal@redeandradeluxor.com.br", "João"),
    ("MAR HOTEL", "notafiscal@redeandrademarhotel.com.br", "Bernardo"),
    ("MAUÁ EXPRESS", "notafiscal@redeandrademauaexpress.com.br", "Cristian"),
    ("MERCADO", "notafiscal@redeandrademercado.com.br", "Cristian"),
    ("MINI HOTEL", "notafiscal@redeandrademinihotel.com.br", "Clara"),
    ("MIRANTE FOZ", "notafiscal@hotelmirantefoz.com.br", "Clara"),
    ("NAVEGANTES", "notafiscal@redeandradenavegantes.com.br", "Bernardo"),
    ("NAVEGANTESBPS", "notafiscal@redeandradenavegantesbps.com.br", "Clara"),
    ("NOVO CWB", "notafiscal@novocwb.com.br", "Bernardo"),
    ("NOVO VERNON", "notafiscal@novovernonhotel.com.br", "Cristian"),
    ("ONDA MAR", "notafiscal@redeandradeondamar.com.br", "Bernardo"),
    ("ONDINA", "notafiscal@redeandradeondina.com.br", "João"),
    ("PAMPULHA", "notafiscal@redeandradepampulha.com.br", "Cristian"),
    ("PIRATININGA", "notafiscal@redeandradepiratininga.com.br", "Bernardo"),
    ("PLAZA RECIFE", "notafiscal@plazarecife.com.br", "Clara"),
    ("PLAZA SALVADOR", "notafiscal@plazasalvador.com.br", "Clara"),
    ("PORTO CENTER", "notafiscal@redeandradeportocenter.com.br", "Cristian"),
    ("PORTO MAR", "notafiscal@redeandradeportomar.com.br", "Cristian"),
    ("PORTO PRAIA", "notafiscal@redeandradeportopraia.com.br", "Cristian"),
    ("PORTO SEGURO", "notafiscal@redeandradeportoseguro.com.br", "Clara"),
    ("POUSADA DO NORTE", "notafiscal@redeandradepousadadonorte.com.br", "Clara"),
    ("REAL", "notafiscal@redeandradereal.com.br", "Cristian"),
    ("RENASSENÇA", "notafiscal@redeandraderenascenca.com.br", "Cristian"),
    ("RIO BRANCO", "notafiscal@redeandraderiobranco.com.br", "Bernardo"),
    ("RIVIERA", "notafiscal@redeandraderiviera.com.br", "Cristian"),
    ("RONDONÓPOLIS", "notafiscal@redeandraderondonopolis.com.br", "João"),
    ("ROYAL", "notafiscal@redeandraderoyal.com.br", "Bernardo"),
    ("ROYAL CRICIÚMA", "notafiscal@redeandraderoyalcriciuma.com.br", "Cristian"),
    ("SAN MARTIN", "notafiscal@redeandradesanmartin.com.br", "Clara"),
    ("SLZ", "notafiscal@redeandradeslz.com.br", "Clara"),
    ("SOLMAR", "notafiscal@redeandradesolmar.com.br", "Clara"),
    ("SÃO FRANCISCO", "notafiscal@redeandradesaofrancisco.com.br", "João"),
    ("TERRA BRASIL", "notafiscal@redeandradeterrabrasil.com.br", "João"),
    ("VELA BRANCA", "notafiscal@redeandradevelabranca.com.br", "João"),
    ("VILA JERI", "notafiscal@redeandradevilajerihotel.com.br", "João"),
    ("VIVALDI", "notafiscal@redeandradevivaldi.com.br", "Bernardo"),
]
NOMES = ["Ana", "Bruno", "Carla", "Daniel", "Eduarda", "Felipe", "Gabriela", "Henrique", "Isabela", "João Pedro", "Karina",
         "Lucas", "Mariana", "Nelson", "Olívia", "Paulo", "Rafaela", "Sérgio", "Tatiane", "Vinícius", "Larissa", "Marcos",
         "Patrícia", "Ricardo", "Juliana", "Thiago", "Fernanda", "Gustavo", "Renata", "André"]
SOBRENOMES = ["Silva", "Souza", "Oliveira", "Pereira", "Costa", "Rodrigues", "Almeida", "Nascimento", "Lima", "Araújo",
              "Fernandes", "Carvalho", "Gomes", "Martins", "Rocha", "Ribeiro", "Barbosa", "Teixeira", "Moreira", "Cardoso"]
EMPRESAS = ["Construtora Horizonte Ltda", "Agro Vale Verde S/A", "TecnoServ Manutenção Ltda", "Instituto Sol Nascente",
            "Transportes Rota Sul Ltda", "Clínica Bem Viver Ltda", "Distribuidora Litoral ME", "Engenharia Atlas Ltda"]
DOMINIOS = ["gmail.com", "hotmail.com", "outlook.com", "yahoo.com.br", "uol.com.br"]
CAB_HOTEL = ["Carimbo de data/hora", "Endereço de e-mail", "Documento Tomador", "Nome Tomador", "CEP", "Telefone para contato",
             "CPF do Titular da Reserva", "Nome do Titular da Reserva", "Check-in da Hospedagem", "Check-out da Hospedagem",
             "Informações necessárias na Nota Fiscal", "Nota Dividida", "Enviado"]
MODELOS = [   # (assunto, texto) dos e-mails dos hóspedes — os casos do dia a dia do financeiro
    ("Nota fiscal da hospedagem", "Boa tarde!\nPreciso da nota fiscal da minha hospedagem de {ci} a {co}.\nSegue o CPF: {cpf}.\nObrigado(a)."),
    ("Re: Nota fiscal", "Bom dia, ainda não recebi a nota fiscal. Poderiam verificar, por favor? Já faz alguns dias."),
    ("Dados para emissão da NF", "Olá, seguem os dados para emissão:\nRazão social: {empresa}\nCNPJ: {cnpj}\nE-mail: {email}"),
    ("Re: NF {nf} - {nome_up}", "Boa tarde, recebi a nota, mas ficou faltando a outra diária (dia {co}). Podem emitir a complementar?"),
    ("Solicitação de correção da NF", "Olá! A NF {nf} saiu com o valor errado (R$ 480,00 no lugar de R$ 560,00). Preciso que seja corrigida, por favor."),
    ("Nota fiscal - reserva {reserva}", "Prezados, solicito a nota fiscal referente à reserva {reserva}, no nome da empresa {empresa}, CNPJ {cnpj}."),
    ("Re: Solicitação NF", "Obrigado pelo retorno! Fico no aguardo da nota."),
    ("Cancelamento de nota", "Bom dia, a nota precisa ser cancelada e refeita no CNPJ da empresa, não no meu CPF."),
]


def _dv_cpf(base):
    for n in (9, 10):
        s = sum(int(base[i]) * (n + 1 - i) for i in range(n))
        base += str((s * 10) % 11 % 10)
    return base


def _dv_cnpj(base):
    for pesos in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        resto = sum(int(d) * p for d, p in zip(base, pesos)) % 11
        base += str(0 if resto < 2 else 11 - resto)
    return base


def _cpf(r, errado=False):
    """CPF fictício com os dígitos conferindo (o Painel agora confere); errado=True troca o último dígito."""
    d = _dv_cpf("".join(str(r.randint(0, 9)) for _ in range(9)))
    if errado:
        d = d[:-1] + str((int(d[-1]) + 1) % 10)
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"


def _cnpj(r, errado=False):
    d = _dv_cnpj("".join(str(r.randint(0, 9)) for _ in range(8)) + "0001")
    if errado:
        d = d[:-1] + str((int(d[-1]) + 1) % 10)
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def _pessoa(r):
    nome = f"{r.choice(NOMES)} {r.choice(SOBRENOMES)} {r.choice(SOBRENOMES)}"
    base = nome.lower().replace(" ", ".").translate(str.maketrans("áâãéêíóôõúç", "aaaeeiooouc"))
    return nome, f"{base}{r.randint(1, 99)}@{r.choice(DOMINIOS)}"


def _id(*partes):
    return hashlib.sha1("|".join(map(str, partes)).encode()).hexdigest()[:12]


class BackendDemo:
    """Imita o BackendGoogle: as "abas" ficam na memória, geradas na hora com dados fictícios."""

    def __init__(self, agora=None):
        self.agora = agora or datetime.datetime.now()
        self.abas = {}
        self.arquivo = []       # o "Outlook" fictício: tudo que entrou e saiu (inclui respondidos e excluídos)
        self._gerar()

    # ---------- geração ----------
    def _gerar(self):
        r = random.Random(20261008)
        agora = self.agora
        self.abas["Cadastro_Hoteis"] = [["Hotel", "E-mail", "Agente"]] + [list(h) for h in HOTEIS]
        self.abas["Status"] = [[rot, "TRUE" if rot == STATUS_LINHAS[0][0] else ""] for rot, _ in STATUS_LINHAS]
        self.abas["Status"][1][1] = agora.strftime("%d/%m/%Y %H:%M")
        self.abas["Status"][11][1] = agora.isoformat(timespec="seconds")
        trat = [dados.CABECALHO_TRATAMENTO]
        hospedes = []
        nf_enviada = set()   # (hotel, e-mail, carimbo) que já receberam a NF: saíram da Caixa de Entrada
        for hotel, caixa, agente in r.sample(HOTEIS, 30):
            aba = f"Solicitação Nota Fiscal ({hotel}) (respostas)"
            linhas = [CAB_HOTEL]
            for _ in range(r.randint(4, 16)):
                dias = r.choice([0, 0, 1, 1, 2, 3, 4, 5, 6, 8, 9, 12, 15, 20, 25, 29])
                quando = agora - datetime.timedelta(days=dias, hours=r.randint(0, 9), minutes=r.randint(0, 59))
                nome, email = _pessoa(r)
                empresa = r.random() < 0.3
                ci = (quando - datetime.timedelta(days=r.randint(2, 6))).date()
                co = ci + datetime.timedelta(days=r.randint(1, 4))
                carimbo = f"{quando.month}/{quando.day}/{quando.year} {quando:%H:%M:%S}"
                errado = r.random() < 0.07   # alguns pedidos chegam com 1 dígito do CPF/CNPJ errado e outros sem CEP (o Painel reconhece)
                sem_cep = r.random() < 0.05
                linhas.append([carimbo, email, _cnpj(r, errado) if empresa else _cpf(r, errado), r.choice(EMPRESAS) if empresa else nome,
                               "" if sem_cep else f"{r.randint(10000, 99999)}-{r.randint(100, 999)}", f"(11) 9{r.randint(1000, 9999)}-{r.randint(1000, 9999)}",
                               _cpf(r), nome, ci.strftime("%d/%m/%Y"), co.strftime("%d/%m/%Y"),
                               r.choice(["", "", "Colocar o número da reserva", "Descrever as diárias"]),
                               "Sim" if r.random() < 0.08 else "Não", "TRUE" if dias >= 1 else "FALSE"])
                hospedes.append((hotel, caixa, agente, nome, email, quando, ci, co, carimbo))
                # o que já foi feito (NF, envio, tratativa), como o robô e a equipe registram
                sorte = r.random()
                if dias >= 1 and sorte < 0.62:
                    nf = str(r.randint(150, 2400))
                    q = quando + datetime.timedelta(hours=r.randint(2, 30))
                    trat.append(dados.evento(q.astimezone(), "Robô", "DEMO", aba, carimbo, email, dados.NF, nf))
                    if r.random() < 0.85:
                        nf_enviada.add((hotel, email, carimbo))
                        trat.append(dados.evento(q.astimezone(), "Robô", "DEMO", aba, carimbo, email, dados.OBS,
                                                 f"E-mail com a NF {nf} enviado para {email} em {q:%d/%m/%Y %H:%M} [m-{_id(email)[:6]}]"))
                elif dias >= 2 and sorte < 0.75:
                    trat.append(dados.evento((quando + datetime.timedelta(hours=5)).astimezone(), agente, "DEMO", aba, carimbo,
                                             email, dados.TRATATIVA, "E-mail ao hóspede: pedi o CNPJ correto"))
            self.abas[aba] = linhas
        self.abas[dados.ABA_TRATAMENTO] = trat
        for aba, cab in ((envio_nf.ABA_FILA, envio_nf.CAB_FILA), (envio_nf.ABA_ANEXOS, envio_nf.CAB_ANEXOS),
                         (rede_pcs.ABA_COMANDOS, rede_pcs.CAB_COMANDOS), (ee.ABA_EVENTOS, ee.CAB_EVENTOS)):
            self.abas[aba] = [list(cab)]
        uso = {"João": "aberto|E-mails|", "Clara": "aberto|Notas fiscais|", "Cristian": "fechado", "Bernardo": ""}
        self.abas[atividade.ABA] = [list(atividade.CABECALHO)] + [
            [(agora - datetime.timedelta(minutes=m)).isoformat(timespec="seconds"), PCS[ag], ag, tipo, hotel, pedido, ""]
            for m, ag, tipo, hotel, pedido in [(4, "João", "NF_ENVIADA", "LUXOR", "Ana Lima"), (9, "Clara", "EMAIL_RECEBIDO", "SOLMAR", "Renata Souza"),
                                               (15, "Cristian", "TRATATIVA", "LAPA", "André Rocha"), (22, "João", "NOVA_SOLICITACAO", "BAHIA", "Paulo Lima"),
                                               (31, "Clara", "NF_DROPBOX", "ARACAJU", "Juliana Costa"), (47, "Cristian", "NF_ENVIADA", "GV", "Lucas Souza")]]
        self.abas[envio_nf.ABA_PCS] = [list(envio_nf.CAB_PCS)] + [
            [pc, ag, ",".join(h[1] for h in HOTEIS if h[2] == ag), "", "aberto", "", "principal" if ag == "João" else "conferente",
             agora.isoformat(timespec="seconds") + "|2 NF · 1 tratativa · 3 recebido(s)", "", "3/1", uso[ag]] for ag, pc in PCS.items()]
        self._gerar_correio(r, [h[:8] for h in hospedes])
        # metade dos envios mais recentes marcados como ligação (22/10/2026), pra Itens Enviados e a Visão geral terem o que mostrar
        recentes = sorted((a for a in self.arquivo if a["pasta"] == "enviado"), key=lambda a: a["quando"], reverse=True)[:16:2]
        self.abas[ligacoes.ABA] = [list(ligacoes.CABECALHO)] + [
            ligacoes.evento(a["id"], ligacoes.MARCAR, next((g for g, pc in PCS.items() if pc == a["pc"]), "João"), a["hotel"],
                            a["caixa"], a["para"], a["assunto"], pc=a["pc"], quando=datetime.datetime.fromisoformat(a["quando"]))
            for a in recentes]
        self._gerar_pedidos_na_caixa([h for h in hospedes if (h[0], h[4], h[8]) not in nf_enviada])

    def _gerar_pedidos_na_caixa(self, pendentes):
        """Abas CaixaPedidos_<PC>: as solicitações do robô ainda na Caixa de Entrada (é o que a tela Notas fiscais mostra)."""
        r = random.Random(20261012)   # sorteio separado: não muda os outros dados fictícios
        por_pc = {pc: {} for pc in PCS.values()}
        for hotel, caixa, agente, nome, email, quando, ci, co, carimbo in pendentes:
            if r.random() < 0.15:   # parte o agente já tirou da caixa
                continue
            pc = PCS.get(agente, "DEMO-JOAO")
            i = _id("pedido", pc, email, carimbo)
            recebido = min(quando + datetime.timedelta(minutes=r.randint(5, 40)), self.agora)
            por_pc[pc][i] = {"id": i, "caixa": caixa, "hotel": hotel, "assunto": f"Solicitação NF - {hotel} - {nome}",
                             "recebido": recebido.isoformat(timespec="seconds"), "lido": r.random() < 0.6,
                             "pedidos": [{"nome": nome, "email": email, "carimbo": f"{quando:%d/%m/%Y %H:%M:%S}",
                                          "ref": f"NF-{i[:8].upper()}"}]}
        for pc, itens in por_pc.items():
            self.abas[ee.nome_aba_pedidos(pc)] = ee.linhas_pedidos(itens, pc, self.agora)

    def _gerar_correio(self, r, hospedes):
        agora = self.agora
        por_pc = {pc: {} for pc in PCS.values()}
        enviados = {pc: {} for pc in PCS.values()}
        for hotel, caixa, agente, nome, email, quando, ci, co in r.sample(hospedes, min(70, len(hospedes))):
            pc = PCS.get(agente, "DEMO-JOAO")
            reserva, nf = str(r.randint(10000, 99999)), str(r.randint(150, 2400))
            for k in range(r.choice([1, 1, 1, 2, 3])):
                assunto, modelo = r.choice(MODELOS)
                q = agora - datetime.timedelta(days=r.choice([0, 0, 0, 0, 1, 1, 2, 3, 4, 6, 9]), hours=r.randint(0, 8), minutes=r.randint(0, 59))
                campos = {"ci": ci.strftime("%d/%m"), "co": co.strftime("%d/%m"), "cpf": _cpf(r), "empresa": r.choice(EMPRESAS),
                          "cnpj": _cnpj(r), "email": email, "nf": nf, "nome_up": nome.upper(), "reserva": reserva}
                texto = modelo.format(**campos) + f"\n\n{nome}"
                assunto = assunto.format(**campos)
                i = _id(pc, email, k, q.isoformat())
                respondido = r.random() < 0.35
                item = {"id": i, "entry_id": i, "pasta": ee.ENTRADA, "caixa": caixa, "hotel": hotel, "de": email, "nome": nome,
                        "para": caixa, "assunto": assunto, "quando": q.isoformat(timespec="seconds"),
                        "anexos": ["voucher.pdf"] if r.random() < 0.2 else [], "texto": texto,
                        "citado": f"De: {caixa}\nEnviada em: {(q - datetime.timedelta(days=2)):%d/%m/%Y}\nAssunto: {assunto}\n\nPrezado(a), segue...",
                        "quartos": [0, []], "classes": ee.classificar(assunto, texto, [])}
                if "corrigir" in item["classes"]:   # a mesma verificação da NF do robô, com uma nota fictícia
                    import analise_nf
                    nf_ficticia = {"valor": "480,00", "competencia": co.strftime("%d/%m/%Y"),
                                   "checkin": ci.strftime("%d/%m/%Y"), "checkout": co.strftime("%d/%m/%Y")}
                    item["analise"] = analise_nf.resumo(analise_nf.pedido_do_cliente(assunto, texto), nf_ficticia, nf)
                self.arquivo.append({**item, "pc": pc, "pasta": "excluido" if respondido else "entrada"})
                if respondido:   # já respondido: está só no "Outlook" (Itens Excluídos/Enviados), não no Painel
                    resp = q + datetime.timedelta(hours=r.randint(1, 20))
                    if resp < agora:
                        enviados[pc][email] = max(enviados[pc].get(email, ""), resp.isoformat(timespec="seconds"))
                        self.arquivo.append({"id": _id("env", i), "entry_id": _id("env", i), "pasta": "enviado", "caixa": caixa,
                                             "hotel": hotel, "de": caixa, "nome": "", "para": email, "assunto": "RE: " + assunto,
                                             "quando": resp.isoformat(timespec="seconds"), "anexos": [f"NF {nf} - {nome.upper()}.pdf"],
                                             "texto": f"Prezado(a) {nome.split()[0]},\n\nSegue em anexo a nota fiscal da sua hospedagem.\n\nAtenciosamente,\nFinanceiro · {hotel}",
                                             "citado": "", "pc": pc})
                        if agora - resp < datetime.timedelta(hours=24):
                            ie = _id("env", i)
                            por_pc[pc][ie] = {**self.arquivo[-1], "pc": pc}
                        continue
                por_pc[pc][i] = item
        self._enviados = enviados
        self._por_pc = por_pc
        self._publicar_correio()

    def _publicar_correio(self):
        for pc, itens in self._por_pc.items():
            env = {e: datetime.datetime.fromisoformat(q) for e, q in self._enviados[pc].items()}
            vivos = ee.resolver(itens, env, self.agora)
            versao = ee.versao_textos(vivos)
            self.abas[ee.nome_aba(pc)] = ee.linhas_da_aba(vivos, env, pc, self.agora, versao)
            self.abas[ee.nome_aba_textos(pc)] = ee.linhas_textos(vivos)

    def responder(self, id_email):
        """Simula a resposta pelo Outlook do PC dono: o e-mail some da caixa (vai pros enviados)."""
        for pc, itens in self._por_pc.items():
            e = itens.get(id_email)
            if e:
                agora = datetime.datetime.now()
                self._enviados[pc][e["de"]] = agora.isoformat(timespec="seconds")
                self.arquivo.append({**e, "pasta": "excluido", "pc": pc})
                self._publicar_correio()
                return pc
        return ""

    def excluir(self, id_email):
        for pc, itens in self._por_pc.items():
            if itens.pop(id_email, None):
                self._publicar_correio()
                return pc
        return ""

    # ---------- a "API" ----------
    def listar_abas(self, planilha_id):
        return list(self.abas) if planilha_id == CENTRAL else []

    def ler_abas(self, planilha_id, nomes, faixas=None):
        if planilha_id != CENTRAL:
            return {}, {n: "planilha inexistente no modo demonstração" for n in nomes}
        agora = datetime.datetime.now().isoformat(sep=" ", timespec="seconds")
        for l in self.abas[envio_nf.ABA_PCS][1:]:   # os PCs "ligados" parecem vistos agora
            if l[1] != DESLIGADO:
                l[3] = agora
        saida, erros = {}, {}
        for n in nomes:
            if n not in self.abas:
                erros[n] = f"Unable to parse range: {n}"
                continue
            linhas = [list(l) for l in self.abas[n]]
            if faixas and n in faixas:
                inicio = int("".join(c for c in faixas[n].split(":")[0] if c.isdigit()))
                linhas = linhas[inicio - 1:]
            saida[n] = linhas
        return saida, erros

    def anexar_linhas(self, planilha_id, aba, linhas):
        self.abas.setdefault(aba, []).extend([list(map(str, l)) for l in linhas])

    def escrever(self, planilha_id, atualizacoes):
        pass

    def substituir_aba(self, planilha_id, aba, linhas):
        self.abas[aba] = [list(l) for l in linhas]

    def criar_aba_log(self, planilha_id, nome, cabecalho):
        self.abas.setdefault(nome, [list(cabecalho)])

    def garantir_colunas(self, *a):
        pass

    def apagar_linhas(self, planilha_id, aba, inicio, fim, novas=None):
        self.abas[aba][inicio - 1:fim - 1] = [list(map(str, l)) for l in (novas or [])]

    def apagar_aba(self, planilha_id, aba):
        self.abas.pop(aba, None)


def preparar(estado, backend):
    """Liga o Estado do Painel ao "Outlook" fictício: busca, texto, responder, excluir, encaminhar."""
    import types
    estado.envio_nf.ler_contas = lambda: []
    for l in backend.abas[envio_nf.ABA_PCS][1:]:   # todos na mesma versão deste Painel
        l[5] = str(getattr(estado, "versao", ""))
    contador = {"n": 0}

    def pedir(self, sol, para, assunto, conta_de, anexos, quem, mensagem=None, cc="", selo="", responder="", acao="", livre=False, ligacao=False):
        contador["n"] += 1
        id_envio = f"DEMO-{contador['n']}"
        pc = backend.excluir(responder) if acao == envio_nf.EXCLUIR else backend.responder(responder) if responder and acao not in (envio_nf.ENCAMINHAR, envio_nf.URGENCIA) else ""
        self.locais[id_envio] = {"estado": "enviado", "pc": pc or "DEMO-JOAO"}
        return {"ok": True, "id": id_envio, "destino": pc or "DEMO-JOAO",
                "aviso": "modo demonstração: nada foi enviado de verdade"}
    estado.envio_nf.pedir = types.MethodType(pedir, estado.envio_nf)
    estado.envio_nf.tick = lambda lidas, agente: setattr(estado.envio_nf, "pcs_linhas", lidas.get(envio_nf.ABA_PCS, [[]]))
    estado._rede = lambda *a: None
    estado._avisar_urgencias = lambda: None

    def buscar(termo, vivo=False):
        from busca_outlook import limpar_termo
        t = limpar_termo(termo).lower()
        if len(t) < 3:
            return {"resultados": [], "pcs": {}, "termo": t}
        achados = [{**{k: v for k, v in x.items() if k not in ("texto", "citado")}, "entry": x["entry_id"],
                    "previa": ee.previa(x.get("texto", ""))} for x in backend.arquivo
                   if t in " ".join([x["nome"], x["de"], x["para"], x["assunto"], x.get("texto", ""), x["hotel"]]).lower()]
        achados.sort(key=lambda x: x["quando"], reverse=True)
        pcs = {pc: ({"ok": True, "achados": sum(1 for a in achados if a["pc"] == pc), "completo": True}
                    if ag != DESLIGADO else {"ok": False, "erro": "desligado"}) for ag, pc in PCS.items()}
        for s in pcs.values():
            if s.get("ok") and not vivo:
                s["fonte"] = "indice"
        return {"resultados": [a for a in achados if a["pc"] != PCS[DESLIGADO]][:200], "pcs": pcs, "termo": termo,
                "vivo": vivo, "agentes": {pc: ag for ag, pc in PCS.items()}}
    estado.buscar_outlook = buscar

    def texto(id_email="", pc="", entry=""):
        alvo = id_email or entry
        x = next((x for x in backend.arquivo if x["id"] == alvo or x["entry_id"] == alvo), None)
        if x is None:
            raise KeyError("e-mail não encontrado no Outlook fictício")
        return {"texto": x.get("texto", ""), "citado": x.get("citado", ""), "pc": x["pc"], "origem": "ao vivo"}
    estado.texto_email = texto


def configurar_cfg(cfg):
    """Tudo que procuraria coisa de fora (Dropbox, outra planilha) fica desligado."""
    cfg = dict(cfg)
    cfg["planilha_central_id"] = CENTRAL
    cfg["dropbox_notas"] = {}
    cfg["painel"] = {**cfg.get("painel", {}), "fiscal_intelligence_id": ""}
    return cfg
