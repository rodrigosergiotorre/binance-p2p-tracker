#!/usr/bin/env python3
"""
Recolector de precios P2P de Binance.

Mercado: USDT (cripto) / USD (fiat)
Metodo de pago: Zinli
Lados: COMPRA (BUY) y VENTA (SELL)

Filtros DESACTIVADOS a proposito (para que coincida con lo que pediste):
  - "Comerciante verificado"   -> publisherType = None
  - "Solo anuncios comerciables" -> filterType = "all"

Cada ejecucion agrega una fila por lado (compra y venta) al archivo data.csv,
con la fecha/hora, el mejor precio, el promedio de los primeros anuncios y
cuantos anuncios habia. Con eso despues se arman las subidas y bajadas.
"""

import csv
import os
import sys
import time
from datetime import datetime, timezone, timedelta

import requests

API_URL = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"

# Bolivia = UTC-4 (para guardar tambien la hora local, mas facil de leer)
BOLIVIA_TZ = timezone(timedelta(hours=-4))

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.csv")

# Cuantos anuncios (los mejores) tomar para calcular el promedio
TOP_N = 5

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Origin": "https://p2p.binance.com",
    "Referer": "https://p2p.binance.com/",
}


def fetch_side(trade_type: str, rows: int = 20):
    """Pide a Binance los anuncios de un lado (BUY o SELL)."""
    payload = {
        "fiat": "USD",
        "asset": "USDT",
        "tradeType": trade_type,          # "BUY" o "SELL"
        "page": 1,
        "rows": rows,
        "payTypes": ["Zinli"],            # metodo de pago Zinli
        "publisherType": None,            # <- "Comerciante verificado" DESACTIVADO
        "proMerchantAds": False,
        "shieldMerchantAds": False,
        "filterType": "all",              # <- "Solo anuncios comerciables" DESACTIVADO
        "countries": [],
        "periods": [],
        "additionalKycVerifyFilter": 0,
        "classifies": ["mass", "profession", "fiat_trade"],
    }

    # Un par de reintentos por si la red falla momentaneamente
    last_error = None
    for intento in range(3):
        try:
            resp = requests.post(API_URL, json=payload, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json().get("data", [])
            return data
        except Exception as e:  # noqa: BLE001
            last_error = e
            time.sleep(3 * (intento + 1))
    raise RuntimeError(f"No se pudo consultar Binance ({trade_type}): {last_error}")


def resumen_precios(anuncios):
    """Calcula mejor precio, promedio de los primeros y cantidad de anuncios."""
    precios = []
    for a in anuncios:
        try:
            precios.append(float(a["adv"]["price"]))
        except (KeyError, TypeError, ValueError):
            continue

    if not precios:
        return None, None, 0

    mejor = precios[0]  # Binance ya los devuelve ordenados por mejor precio
    top = precios[:TOP_N]
    promedio = round(sum(top) / len(top), 4)
    return mejor, promedio, len(precios)


def asegurar_cabecera():
    """Crea data.csv con su cabecera si no existe todavia."""
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "fecha_utc",
                "fecha_bolivia",
                "lado",            # "compra" o "venta"
                "mejor_precio",
                "promedio_top5",
                "cantidad_anuncios",
            ])


def main():
    ahora_utc = datetime.now(timezone.utc)
    ahora_bo = ahora_utc.astimezone(BOLIVIA_TZ)

    asegurar_cabecera()

    filas = []
    # "BUY" en la API = anuncios donde vos COMPRAS USDT
    # "SELL" en la API = anuncios donde vos VENDES USDT
    for trade_type, etiqueta in (("BUY", "compra"), ("SELL", "venta")):
        anuncios = fetch_side(trade_type)
        mejor, promedio, cantidad = resumen_precios(anuncios)

        filas.append([
            ahora_utc.strftime("%Y-%m-%d %H:%M:%S"),
            ahora_bo.strftime("%Y-%m-%d %H:%M:%S"),
            etiqueta,
            mejor if mejor is not None else "",
            promedio if promedio is not None else "",
            cantidad,
        ])
        print(f"[{etiqueta}] mejor={mejor}  promedio_top{TOP_N}={promedio}  anuncios={cantidad}")

    with open(DATA_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerows(filas)

    print(f"Lectura guardada: {ahora_bo.strftime('%Y-%m-%d %H:%M')} (hora Bolivia)")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

