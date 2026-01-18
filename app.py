from flask import Flask, request, jsonify, Response
import requests
import json
from bs4 import BeautifulSoup
import os

app = Flask(__name__)

def consultar_saldo_unemi(cedula):
    session = requests.Session()
    r1 = session.get("https://sagest.epunemi.gob.ec/consultarsaldos", headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    
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
        "cedula": cedula,
        "tipoiden": "1"
    }
    
    r2 = session.post("https://sagest.epunemi.gob.ec/consultarsaldos",
                      headers=headers, cookies=cookies, data=data)
    
    try:
        result_html = r2.json().get("data", "")
    except:
        result_html = r2.text
    
    soup = BeautifulSoup(result_html, "html.parser")
    
    # ────────────────────────────────────────────────
    # 🧍 Extraer datos del estudiante (sin cambios)
    # ────────────────────────────────────────────────
    datos_estudiante = {}
    card_body = soup.find("div", class_="card-body")
    if card_body:
        for p in card_body.find_all("p"):
            text = p.get_text(strip=True)
            if "Cédula" in text:
                datos_estudiante["cedula"] = text.split(":", 1)[-1].strip()
            elif "Nombres" in text:
                datos_estudiante["nombres"] = text.split(":", 1)[-1].strip()
            elif "Email" in text:
                datos_estudiante["correo"] = text.split(":", 1)[-1].strip()
    
    # ────────────────────────────────────────────────
    # 🧾 Extraer SOLO la tabla de RUBROS UNEMI
    # ────────────────────────────────────────────────
    rubros = []
    
    # Intentamos encontrar el título de la sección deseada
    seccion_encontrada = None
    posibles_titulos = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'strong', 'p', 'span'])
    
    for elem in posibles_titulos:
        texto = elem.get_text(strip=True).upper()
        if any(palabra in texto for palabra in ["RUBROS UNEMI", "MAESTRIAS", "EDUCACION CONTINUA", "POSGRADOS", "CERTIFICADO ACAD"]):
            seccion_encontrada = elem
            break
    
    tabla = None
    if seccion_encontrada:
        # Buscamos la siguiente tabla después del título
        tabla = seccion_encontrada.find_next("table", class_="table-bordered")
    
    # Si no encontramos por título → fallback: segunda tabla bordered
    if not tabla:
        tablas = soup.find_all("table", class_="table-bordered")
        if len(tablas) >= 2:
            tabla = tablas[1]  # asumimos: 0 = Jornadas, 1 = Rubros UNEMI
    
    if tabla:
        # Tomamos todas las filas (con o sin tbody)
        filas = tabla.select("tbody tr") or tabla.select("tr")
        for fila in filas:
            celdas = fila.find_all("td")
            if len(celdas) < 4:  # mínimo para tener sentido
                continue
            
            rubro_data = {
                "rubro": celdas[1].get_text(strip=True) if len(celdas) > 1 else "",
                "mes": celdas[2].get_text(strip=True) if len(celdas) > 2 else "",
                "fecha_vencimiento": celdas[3].get_text(strip=True) if len(celdas) > 3 else "",
            }
            
            # Columnas adicionales si existen (tu ejemplo tiene hasta 6-7)
            if len(celdas) >= 7:
                rubro_data.update({
                    "valor_total": celdas[4].get_text(strip=True),
                    "total_pagado": celdas[5].get_text(strip=True),
                    "saldo": celdas[6].get_text(strip=True),
                })
            elif len(celdas) >= 5:
                rubro_data["valor"] = celdas[4].get_text(strip=True)
            
            rubros.append(rubro_data)
    
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
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
