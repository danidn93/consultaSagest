from flask import Flask, request, jsonify, Response
import requests
import json
from bs4 import BeautifulSoup
import os

app = Flask(__name__)

def consultar_saldo_unemi(identificacion, tipoiden=1):
    session = requests.Session()
    r1 = session.get(
        "https://sagest.epunemi.gob.ec/consultarsaldos",
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    
    soup = BeautifulSoup(r1.text, "html.parser")
    token_input = soup.find("input", {"name": "csrfmiddlewaretoken"})
    if not token_input:
        return {"error": "No se encontró csrfmiddlewaretoken"}
    
    csrf_token_form = token_input["value"]
    csrf_token_cookie = session.cookies.get("csrftoken")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://sagest.epunemi.gob.ec/consultarsaldos",
        "Origin": "https://sagest.epunemi.gob.ec",
        "X-CSRFToken": csrf_token_cookie,
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "application/json, text/javascript, */*; q=0.01"
    }
    
    cookies = {"csrftoken": csrf_token_cookie}
    
    data = {
        "action": "segmento",
        "csrfmiddlewaretoken": csrf_token_form,
        "cedula": identificacion,           # el campo siempre se llama "cedula" en el POST
        "tipoiden": str(tipoiden)           # 1 = cédula, 2 = pasaporte (ajusta si son otros valores)
    }
    
    r2 = session.post(
        "https://sagest.epunemi.gob.ec/consultarsaldos",
        headers=headers,
        cookies=cookies,
        data=data
    )
    
    try:
        result_html = r2.json().get("data", "")
    except:
        result_html = r2.text
    
    soup = BeautifulSoup(result_html, "html.parser")
    
    # ────────────────────────────────────────────────
    # Datos del estudiante
    # ────────────────────────────────────────────────
    datos_estudiante = {}
    card_body = soup.find("div", class_="card-body")
    if card_body:
        for p in card_body.find_all("p"):
            text = p.get_text(strip=True)
            if "Cédula" in text or "Identificación" in text:
                datos_estudiante["identificacion"] = text.split(":", 1)[-1].strip()
            elif "Nombres" in text:
                datos_estudiante["nombres"] = text.split(":", 1)[-1].strip()
            elif "Email" in text:
                datos_estudiante["correo"] = text.split(":", 1)[-1].strip()
    
    # ────────────────────────────────────────────────
    # Extraer SOLO tabla RUBROS UNEMI (maestrías, educación continua, etc.)
    # ────────────────────────────────────────────────
    rubros = []
    
    # Filtro correcto para encontrar el <th> con el título
    def es_titulo_rubros_unemi(tag):
        if not tag or tag.name != 'th':
            return False
        texto = tag.get_text(separator=" ", strip=True).upper()
        return "RUBROS UNEMI" in texto
    
    th_titulo = soup.find(es_titulo_rubros_unemi)
    
    tabla = None
    
    if th_titulo:
        card = th_titulo.find_parent("div", class_="card")
        if card:
            tabla = card.find("table", class_="table-bordered")
    
    # Fallback: segunda tabla bordered si no se encontró por título
    if not tabla:
        tablas = soup.find_all("table", class_="table-bordered")
        if len(tablas) >= 2:
            tabla = tablas[1]
    
    if tabla:
        filas = tabla.select("tbody tr") or tabla.select("tr")
        for fila in filas:
            celdas = fila.find_all("td")
            if len(celdas) < 7:
                continue
            
            rubros.append({
                "codigo": celdas[0].get_text(strip=True),
                "rubro": celdas[1].get_text(strip=True),
                "mes": celdas[2].get_text(strip=True),
                "fecha_vencimiento": celdas[3].get_text(strip=True),
                "valor_total": celdas[4].get_text(strip=True),
                "total_pagado": celdas[5].get_text(strip=True),
                "total_pendiente": celdas[6].get_text(strip=True),
            })
    
    return {
        "datos_estudiante": datos_estudiante,
        "rubros_unemi": rubros
    }


@app.route('/consultar', methods=['GET'])
def consultar():
    # Acepta cedula o identificacion (para mayor flexibilidad)
    identificacion = request.args.get('cedula') or request.args.get('identificacion')
    tipoiden_str = request.args.get('tipo') or request.args.get('tipoiden', '1')
    
    if not identificacion:
        return jsonify({"error": "Parámetro 'cedula' o 'identificacion' es requerido"}), 400
    
    try:
        tipoiden = int(tipoiden_str)
        if tipoiden not in [1, 2]:
            return jsonify({"error": "tipoiden debe ser 1 (cédula) o 2 (pasaporte)"}), 400
    except ValueError:
        return jsonify({"error": "tipoiden debe ser un número (1 o 2)"}), 400
    
    resultado = consultar_saldo_unemi(identificacion, tipoiden)
    
    return Response(
        json.dumps(resultado, ensure_ascii=False),
        content_type='application/json; charset=utf-8'
    )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
