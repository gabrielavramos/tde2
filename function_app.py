import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import azure.functions as func
import json
import logging
import requests
import os

app = func.FunctionApp()

# ==============================================================
# 🎯 Função disparada pela fila "integracao-nf"
# ==============================================================

@app.service_bus_queue_trigger(
    arg_name="msg",
    queue_name="integracao-nf",
    connection="ServiceBusConnection"
)
def EnviarNFSEFunction(msg: func.ServiceBusMessage):
    try:
        body = msg.get_body().decode("utf-8")
        logging.info(f"📥 Mensagem recebida do Service Bus: {body}")

        data = json.loads(body)

        payload = {
            "cityServiceCode": data.get("codigo_servico", "101"),
            "description": data.get("descricao", "Serviço prestado"),
            "servicesAmount": data.get("valor", 0),
            "borrower": {
                "federalTaxNumber": data.get("cpf_cnpj_cliente", "00000000000"),
                "name": data.get("cliente", "Cliente não informado"),
                "email": data.get("email", ""),
                "address": {
                    "country": "BRA",
                    "postalCode": data.get("cep", "00000000"),
                    "street": data.get("endereco", "Rua não informada"),
                    "number": data.get("numero", "0"),
                    "district": data.get("bairro", ""),
                    "city": {
                        "code": data.get("codigo_municipio", "3550308"),
                        "name": data.get("municipio", "São Paulo")
                    },
                    "state": data.get("uf", "SP")
                }
            }
        }

        api_key = os.getenv("NFE_API_KEY")
        empresa_id = os.getenv("NFE_COMPANY_ID")

        if not api_key or not empresa_id:
            raise Exception("❌ Variáveis de ambiente NFE_API_KEY ou NFE_COMPANY_ID não configuradas.")

        url = f"https://api.nfe.io/v1/companies/{empresa_id}/serviceinvoices"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Basic {api_key}"
        }

        response = requests.post(url, headers=headers, data=json.dumps(payload))
        logging.info(f"📤 Enviando NFSe para NFE.io: {response.status_code}")

        if response.status_code in (200, 201):
            logging.info(f"✅ NFSe enviada com sucesso: {response.json()}")
        else:
            logging.error(f"❌ Erro ao enviar NFSe: {response.text}")

    except Exception as e:
        logging.error(f"❌ Erro geral na função: {e}")


# ==============================================================
# ✉️ Função HTTP para enviar e-mail (POST)
# ==============================================================

@app.route(route="EnviarEmailFunction", auth_level=func.AuthLevel.ANONYMOUS)
def EnviarEmailFunction(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("📨 Função de envio de e-mail acionada.")

    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse("❌ Corpo da requisição inválido.", status_code=400)

    destinatario = req_body.get("destinatario")
    assunto = req_body.get("assunto")
    mensagem = req_body.get("mensagem")

    if not destinatario or not assunto or not mensagem:
        return func.HttpResponse(
            "❌ Campos obrigatórios: destinatario, assunto e mensagem.",
            status_code=400
        )

    remetente = "seuemail@gmail.com"
    senha = "suasenha"
    servidor_smtp = "smtp.gmail.com"
    porta = 587

    try:
        msg_email = MIMEMultipart()
        msg_email["From"] = remetente
        msg_email["To"] = destinatario
        msg_email["Subject"] = assunto
        msg_email.attach(MIMEText(mensagem, "plain"))

        with smtplib.SMTP(servidor_smtp, porta) as server:
            server.starttls()
            server.login(remetente, senha)
            server.send_message(msg_email)

        logging.info(f"📧 E-mail enviado para {destinatario}")
        return func.HttpResponse(f"E-mail enviado para {destinatario}", status_code=200)

    except Exception as e:
        logging.error(f"❌ Erro ao enviar e-mail: {e}")
        return func.HttpResponse(f"Erro ao enviar e-mail: {str(e)}", status_code=500)
