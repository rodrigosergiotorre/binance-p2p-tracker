#!/usr/bin/env python3
"""
Recolector de precios P2P de Binance.

Mercado: USDT (cripto) / USD (fiat)
Metodo de pago: Zinli
Lados: COMPRA (BUY) y VENTA (SELL)

Filtros DESACTIVADOS a proposito:
  - "Comerciante verificado"     -> publisherType = None
  - "Solo anuncios comerciables" -> filterType = "all"

Cada ejecucion:
  1. Agrega una fila por lado (compra y venta) a data.csv con el resumen.
  2. Guarda la respuesta COMPLETA de Binance en snapshots/AAAA-MM-DD.jsonl
     (una linea JSON por lado, por lectura). Nada se pierde: si algun dia
     queremos calcular otra estadistica, se puede recalcular hacia atras.

Sobre el filtro de outliers
---------------------------
A veces el primer anuncio de la lista esta muy alejado del resto (alguien
urgido, un monto ridiculamente chico, etc.) y ensucia el "mejor precio".

Lo que hacemos: calculamos la MEDIANA de los primeros 10 anuncios (la mediana
casi no se mueve por uno o dos precios locos) y vamos recorriendo la lista
desde el mejor precio hacia abajo, descartando los que se alejen mas de 1% de
esa mediana. El primero que entra dentro del 1% es el "mejor precio limpio".

Se guardan LAS DOS cosas: mejor_precio_bruto (sin filtrar, como antes) y
mejor_precio_limpio. Asi podes comparar y decidir si el filtro te sirve.
"""

import csv
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone, timedelta

import requests

API_URL = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"

# Bolivia = UTC-4 (para guardar tambien la hora local, mas facil de leer)
BOLIVIA_TZ = timezone(timedelta(hours=-4))

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE, "data.csv")
SNAPSHOT_DIR = os.path.join(BASE, "snapshots")

# ------------------------------------------------------------------
# MERCADOS QUE SE RECOLECTAN
# ------------------------------------------------------------------
# Para agregar un mercado nuevo, copia un bloque y cambia los valores.
#   nombre   -> como se llamara en la columna "mercado" del CSV
#   fiat     -> la moneda (USD, BOB, ARS, BRL...)
#   asset    -> la cripto (USDT, BTC...)
#   payTypes -> metodos de pago. Lista vacia [] = TODOS los metodos.
MERCADOS = [
    {
        "nombre": "USD-Zinli",
        "fiat": "USD",
        "asset": "USDT",
        "payTypes": ["Zinli"],
    },
    {
        "nombre": "BOB-todos",
        "fiat": "BOB",          # bolivianos
        "asset": "USDT",
        "payTypes": [],         # sin filtrar: todos los metodos de pago
    },
]

# Cuantos anuncios pedimos por lado
ROWS = 20

# Cuantos anuncios (los mejores) tomar para calcular el promedio
TOP_N = 5

# Filtro de outliers
VENTANA_MEDIANA = 10    # sobre cuantos anuncios se calcula la mediana
UMBRAL_OUTLIER = 0.01   # 1% de desvio respecto a la mediana

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

COLUMNAS = [
    "fecha_utc",
    "fecha_bolivia",
    "mercado",               # "USD-Zinli", "BOB-todos", ...
    "fiat",                  # USD, BOB, ...
    "lado",                  # "compra" o "venta"
    "mejor_precio_bruto",    # el primero de la lista, sin filtrar
    "mejor_precio_limpio",   # el primero que pasa el filtro de outliers
    "promedio_top5_limpio",  # promedio de los 5 mejores ya filtrados
    "mediana_top10",         # referencia usada por el filtro
    "descartados",           # cuantos anuncios se saltaron por outliers
    "precios_descartados",   # cuales, separados por "|"
    "cantidad_anuncios",
    "liquidez_total_usdt",   # suma de lo disponible en todos los anuncios
    "mejor_min_orden",       # limite minimo de la orden del mejor anuncio
    "mejor_max_orden",       # limite maximo de la orden del mejor anuncio
    "mejor_comerciante",     # apodo del anunciante del mejor precio
    "mejor_tipo",            # user / merchant
    "mejor_ordenes_mes",
    "mejor_tasa_completado",
    "metodos_pago_vistos",   # que metodos aparecen en esa lectura, separados por "|"
]


def fetch_side(mercado: dict, trade_type: str, rows: int = ROWS):
    """Pide a Binance los anuncios de un lado (BUY o SELL) de un mercado."""
    payload = {
        "fiat": mercado["fiat"],
        "asset": mercado["asset"],
        "tradeType": trade_type,          # "BUY" o "SELL"
        "page": 1,
        "rows": rows,
        "payTypes": mercado["payTypes"],  # [] = todos los metodos
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
            return resp.json().get("data", []) or []
        except Exception as e:  # noqa: BLE001
            last_error = e
            time.sleep(3 * (intento + 1))
    raise RuntimeError(
        f"No se pudo consultar Binance ({mercado['nombre']} / {trade_type}): {last_error}"
    )


def campo(dic, *nombres, default=""):
    """Devuelve el primer campo que exista. Binance a veces cambia nombres."""
    if not isinstance(dic, dict):
        return default
    for n in nombres:
        v = dic.get(n)
        if v not in (None, ""):
            return v
    return default


def numero(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def precios_de(anuncios):
    """Lista de (precio, anuncio) en el orden que los devuelve Binance."""
    salida = []
    for a in anuncios:
        if not isinstance(a, dict):
            continue
        p = numero(campo(a.get("adv"), "price", default=None))
        if p is not None and p > 0:
            salida.append((p, a))
    return salida


def filtrar_outliers(pares):
    """
    Descarta los anuncios del tope de la lista que se alejen mas de
    UMBRAL_OUTLIER de la mediana de los primeros VENTANA_MEDIANA.

    Devuelve: (pares_limpios, precios_descartados, mediana)
    """
    if len(pares) < 3:
        return pares, [], None

    muestra = [p for p, _ in pares[:VENTANA_MEDIANA]]
    mediana = statistics.median(muestra)
    if not mediana:
        return pares, [], None

    descartados = []
    for i, (precio, _) in enumerate(pares):
        if abs(precio - mediana) / mediana > UMBRAL_OUTLIER:
            descartados.append(precio)
            continue
        # Primer anuncio que entra dentro del umbral: de aqui en adelante
        # nos quedamos con la lista tal cual.
        return pares[i:], descartados, mediana

    # Caso raro: ninguno paso el filtro. No inventamos nada, devolvemos todo.
    return pares, [], mediana


def resumen(anuncios):
    """Calcula todas las metricas de un lado."""
    pares = precios_de(anuncios)
    fila = {c: "" for c in COLUMNAS}
    fila["cantidad_anuncios"] = len(pares)

    liquidez = 0.0
    metodos = []
    for _, a in pares:
        adv_a = a.get("adv") or {}
        q = numero(campo(adv_a, "surplusAmount", "tradableQuantity", default=None))
        if q:
            liquidez += q
        for m in (adv_a.get("tradeMethods") or []):
            nombre = campo(m, "identifier", "tradeMethodName", "payType")
            if nombre and nombre not in metodos:
                metodos.append(nombre)
    fila["liquidez_total_usdt"] = round(liquidez, 2) if liquidez else ""
    fila["metodos_pago_vistos"] = "|".join(sorted(metodos))

    if not pares:
        return fila

    fila["mejor_precio_bruto"] = pares[0][0]

    limpios, descartados, mediana = filtrar_outliers(pares)
    fila["mediana_top10"] = round(mediana, 4) if mediana else ""
    fila["descartados"] = len(descartados)
    fila["precios_descartados"] = "|".join(str(p) for p in descartados)

    if not limpios:
        return fila

    mejor_precio, mejor_anuncio = limpios[0]
    fila["mejor_precio_limpio"] = mejor_precio

    top = [p for p, _ in limpios[:TOP_N]]
    fila["promedio_top5_limpio"] = round(sum(top) / len(top), 4)

    adv = mejor_anuncio.get("adv") or {}
    anunciante = mejor_anuncio.get("advertiser") or {}
    fila["mejor_min_orden"] = campo(adv, "minSingleTransAmount")
    fila["mejor_max_orden"] = campo(adv, "maxSingleTransAmount", "dynamicMaxSingleTransAmount")
    fila["mejor_comerciante"] = campo(anunciante, "nickName", "nickname")
    fila["mejor_tipo"] = campo(anunciante, "userType")
    fila["mejor_ordenes_mes"] = campo(anunciante, "monthOrderCount")
    fila["mejor_tasa_completado"] = campo(anunciante, "monthFinishRate")

    return fila


def asegurar_cabecera():
    """
    Crea data.csv con su cabecera si no existe.

    Si ya existe pero con las columnas viejas (version anterior del script),
    lo renombra a data_anterior.csv y arranca uno nuevo. Asi no se mezclan
    filas con distinta cantidad de columnas, y no se pierde lo ya recolectado.
    """
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, newline="", encoding="utf-8") as f:
            cabecera = next(csv.reader(f), [])
        if cabecera == COLUMNAS:
            return
        # Buscamos un nombre libre para no pisar un respaldo anterior
        n = 1
        anterior = os.path.join(BASE, "data_anterior.csv")
        while os.path.exists(anterior):
            n += 1
            anterior = os.path.join(BASE, f"data_anterior_{n}.csv")
        os.replace(DATA_FILE, anterior)
        print(f"data.csv tenia el formato viejo -> guardado como {os.path.basename(anterior)}")

    with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(COLUMNAS)


def guardar_snapshot(ahora_utc, mercado, lado, anuncios):
    """Guarda la respuesta cruda completa, un archivo por dia."""
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    ruta = os.path.join(SNAPSHOT_DIR, ahora_utc.strftime("%Y-%m-%d") + ".jsonl")
    registro = {
        "fecha_utc": ahora_utc.strftime("%Y-%m-%d %H:%M:%S"),
        "mercado": mercado["nombre"],
        "fiat": mercado["fiat"],
        "asset": mercado["asset"],
        "payTypes": mercado["payTypes"],
        "lado": lado,
        "anuncios": anuncios,
    }
    with open(ruta, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def main():
    ahora_utc = datetime.now(timezone.utc)
    ahora_bo = ahora_utc.astimezone(BOLIVIA_TZ)

    asegurar_cabecera()

    filas = []
    fallos = []

    for mercado in MERCADOS:
        print(f"\n=== {mercado['nombre']} ({mercado['asset']}/{mercado['fiat']}) ===")

        # "BUY" en la API = anuncios donde vos COMPRAS la cripto
        # "SELL" en la API = anuncios donde vos VENDES la cripto
        for trade_type, etiqueta in (("BUY", "compra"), ("SELL", "venta")):
            try:
                anuncios = fetch_side(mercado, trade_type)
            except Exception as e:  # noqa: BLE001
                # Un mercado caido no debe tumbar a los demas
                print(f"[{etiqueta}] FALLO: {e}", file=sys.stderr)
                fallos.append(f"{mercado['nombre']}/{etiqueta}")
                continue

            guardar_snapshot(ahora_utc, mercado, etiqueta, anuncios)

            fila = resumen(anuncios)
            fila["fecha_utc"] = ahora_utc.strftime("%Y-%m-%d %H:%M:%S")
            fila["fecha_bolivia"] = ahora_bo.strftime("%Y-%m-%d %H:%M:%S")
            fila["mercado"] = mercado["nombre"]
            fila["fiat"] = mercado["fiat"]
            fila["lado"] = etiqueta
            filas.append([fila[c] for c in COLUMNAS])

            aviso = ""
            if fila["descartados"]:
                aviso = f"  (descartados {fila['descartados']}: {fila['precios_descartados']})"
            print(
                f"[{etiqueta}] bruto={fila['mejor_precio_bruto']} "
                f"limpio={fila['mejor_precio_limpio']} "
                f"mediana={fila['mediana_top10']} "
                f"anuncios={fila['cantidad_anuncios']}{aviso}"
            )
            if fila["metodos_pago_vistos"]:
                print(f"          metodos: {fila['metodos_pago_vistos']}")

    if filas:
        with open(DATA_FILE, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(filas)

    print(f"\nLectura guardada: {ahora_bo.strftime('%Y-%m-%d %H:%M')} (hora Bolivia)")
    print(f"Filas nuevas: {len(filas)}")

    if fallos:
        # Fallan algunos pero no todos -> avisamos sin romper la ejecucion
        print(f"ATENCION, mercados sin datos: {', '.join(fallos)}", file=sys.stderr)
    if not filas:
        raise RuntimeError("Ningun mercado devolvio datos")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
