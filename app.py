from flask import Flask, request, jsonify, Response
import requests, json
from bs4 import BeautifulSoup

app = Flask(__name__)

def consultar_saldo_unemi(cedula):
    session = requests.Session()

    r1 = session.get("https://sagest.epunemi.gob.ec/consultarsaldos", headers={
        "User-Agent": "Mozilla/5.0"
    })

    soup = BeautifulSoup(r1.text, "html.parser")
    token_input = soup.find("input", {"name": "csrfmiddlewaretoken"})
    if not token_input:
        return {"error": "No se encontró csrfmiddlewaretoken"}

    csrf_token_form = token_input["value"]
    csrf_token_cookie = session.cookies.get("csrftoken")

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://sagest.epunemi.gob.ec/consultarsaldos",
        "Origin": "https://sagest.epunemi.gob.ec",
        "X-CSRFToken": csrf_token_cookie,
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "application/json, text/javascript, */*; q=0.01"
    }

    cookies = {
        "csrftoken": csrf_token_cookie
    }

    data = {
        "action": "segmento",
        "csrfmiddlewaretoken": csrf_token_form,
        "cedula": cedula,
        "tipoiden": "1"
    }

    r2 = session.post("https://sagest.epunemi.gob.ec/consultarsaldos", headers=headers, cookies=cookies, data=data)

    try:
        result_html = r2.json().get("data", "")
    except:
        result_html = r2.text

    soup = BeautifulSoup(result_html, "html.parser")

    # 🧍 Extraer datos del estudiante
    datos_estudiante = {}
    card_body = soup.find("div", class_="card-body")
    if card_body:
        for p in card_body.find_all("p"):
            if "Cédula" in p.text:
                datos_estudiante["cedula"] = p.text.split(":")[-1].strip()
            elif "Nombres" in p.text:
                datos_estudiante["nombres"] = p.text.split(":")[-1].strip()
            elif "Email" in p.text:
                datos_estudiante["correo"] = p.text.split(":")[-1].strip()

    # 🧾 Extraer tabla de rubros
    rubros = []
    tabla = soup.find("table", class_="table-bordered")
    if tabla:
        filas = tabla.find("tbody").find_all("tr")
        for fila in filas:
            celdas = fila.find_all("td")
            if len(celdas) >= 7:
                rubros.append({
                    "rubro": celdas[1].text.strip(),
                    "mes": celdas[2].text.strip(),
                    "fecha_vencimiento": celdas[3].text.strip(),
                    "valor_total": celdas[4].text.strip(),
                    "total_pagado": celdas[5].text.strip(),
                    "saldo": celdas[6].text.strip()
                })

    return {
        "datos_estudiante": datos_estudiante,
        "rubros_unemi": rubros
    }

@app.route('/consultar', methods=['GET'])
def consultar():
    cedula = request.args.get('cedula')
    if not cedula:
        return jsonify({"error": "Parámetro 'cedula' es requerido"}), 400

    resultado = consultar_saldo_unemi(cedula)
    return Response(
        json.dumps(resultado, ensure_ascii=False),
        content_type='application/json; charset=utf-8'
    )

if __name__ == '__main__':
    app.run(debug=True)
