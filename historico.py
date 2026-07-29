#!/usr/bin/env python3
"""
Trae el historico diario del USDT/BOB desde Yadio.io.

Por que existe este archivo aparte:
--------------------------------------
Binance NO guarda historia de su mercado P2P. Su API solo devuelve los anuncios
vivos en este momento. Por eso `scrape.py` solo puede construir la serie hacia
adelante, cada hora, desde el dia que lo encendimos.

Yadio.io si publica historia diaria (hasta 365 dias hacia atras), asi que este
script la trae para tener contexto largo: tendencia del ano, estacionalidad,
donde estamos parados frente a los ultimos 12 meses.

OJO, NO ES LA MISMA MEDIDA
--------------------------
Yadio publica SU tasa de mercado libre calculada. No es "el mejor precio de
compra en Binance P2P" que mide scrape.py. Son dos definiciones distintas.

Por eso vive en su propio archivo (historico_bob.csv) y no se mezcla con
data.csv. Si los grafican juntos, tienen que ir como series separadas y
etiquetadas, o veran saltos que parecen movimientos de mercado y en realidad
son cambios de definicion.

El historico se ACUMULA
-----------------------
Yadio da una ventana movil de 365 dias: lo mas viejo se va cayendo. Este script
mezcla lo que trae con lo que ya habia en el archivo, asi que con el tiempo
vamos a tener mas de un ano guardado.

Uso:
    python historico.py
"""

import csv
import os
import sys

import requests

API = "https://api.yadio.io/hist/{dias}/{moneda}"
DIAS = 365

BASE = os.path.dirname(os.path.abspath(__file__))

# moneda -> archivo de salida
MONEDAS = {
    "BOB": "historico_bob.csv",
}

COLUMNAS = ["fecha", "tasa_yadio"]


def traer(moneda: str) -> dict:
    """Devuelve {fecha_iso: tasa} desde la API de Yadio."""
    url = API.format(dias=DIAS, moneda=moneda)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    datos = resp.json()

    if not isinstance(datos, list):
        raise RuntimeError(f"Respuesta inesperada de Yadio para {moneda}: {type(datos)}")

    salida = {}
    for punto in datos:
        if not isinstance(punto, dict):
            continue
        fecha = punto.get("date")
        tasa = punto.get("rate")
        if not fecha or tasa is None:
            continue
        try:
            # Yadio manda MM/DD/AAAA; lo pasamos a AAAA-MM-DD para que ordene bien
            mes, dia, anio = str(fecha).split("/")
            iso = f"{anio}-{int(mes):02d}-{int(dia):02d}"
            salida[iso] = round(float(tasa), 4)
        except (ValueError, TypeError):
            continue
    return salida


def leer_existente(ruta: str) -> dict:
    if not os.path.exists(ruta):
        return {}
    previo = {}
    with open(ruta, newline="", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            fecha = fila.get("fecha")
            tasa = fila.get("tasa_yadio")
            if not fecha or not tasa:
                continue
            try:
                previo[fecha] = float(tasa)
            except ValueError:
                continue
    return previo


def guardar(ruta: str, datos: dict):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLUMNAS)
        for fecha in sorted(datos):
            w.writerow([fecha, datos[fecha]])


def main():
    for moneda, archivo in MONEDAS.items():
        ruta = os.path.join(BASE, archivo)

        previo = leer_existente(ruta)
        nuevo = traer(moneda)

        # Lo nuevo pisa a lo viejo si hay conflicto (el dia en curso se corrige)
        combinado = {**previo, **nuevo}
        agregados = len(set(combinado) - set(previo))

        guardar(ruta, combinado)

        fechas = sorted(combinado)
        print(
            f"[{moneda}] {archivo}: {len(combinado)} dias "
            f"({fechas[0]} a {fechas[-1]}), {agregados} nuevos"
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        # Que falle el historico no debe tumbar la recoleccion principal
        print(f"ERROR trayendo historico: {e}", file=sys.stderr)
        sys.exit(1)
