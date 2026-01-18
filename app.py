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
    # 🧾 Extraer SOLO la tabla de RUBROS UNEMI (MAESTRIAS, EDUCACIÓN CONTINUA, ETC)
    # ────────────────────────────────────────────────
    rubros = []

    # Buscar el <th> que contenga el título deseado (dentro de cualquier texto descendiente)
    th_titulo = soup.find('th', lambda tag: tag and 'RUBROS UNEMI' in tag.get_text(separator=' ', strip=True).upper())

    if th_titulo:
        # Subimos al card padre (el contenedor principal de esa sección)
        card = th_titulo.find_parent('div', class_='card')
        if card:
            # Dentro del card, buscamos la tabla bordered/striped
            tabla = card.find('table', class_='table-bordered')
            if tabla:
                # Extraemos filas del tbody (o directamente tr si no hay tbody)
                filas = tabla.find('tbody')
                if filas:
                    filas = filas.find_all('tr')
                else:
                    filas = tabla.find_all('tr')

                for fila in filas:
                    celdas = fila.find_all('td')
                    if len(celdas) < 7:  # mínimo para tener las columnas clave
                        continue

                    rubros.append({
                        "codigo": celdas[0].get_text(strip=True),               # P[1601055] o similar
                        "rubro": celdas[1].get_text(strip=True),
                        "mes": celdas[2].get_text(strip=True),
                        "fecha_vencimiento": celdas[3].get_text(strip=True),
                        "valor_total": celdas[4].get_text(strip=True),
                        "total_pagado": celdas[5].get_text(strip=True),
                        "total_pendiente": celdas[6].get_text(strip=True),
                        # Si quieres la factura link o algo, puedes extraer celdas[7] pero es más complejo (onclick)
                    })

    # Opcional: fallback si por alguna razón no encuentra el título (rara vez necesario)
    if not rubros:
        tablas = soup.find_all('table', class_='table-bordered')
        if len(tablas) >= 2:
            # Si la primera es Jornadas → toma la segunda
            tabla = tablas[1]
            
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
