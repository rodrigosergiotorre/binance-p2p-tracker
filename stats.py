#!/usr/bin/env python3
"""
Genera estadisticas a partir de data.csv, separadas por mercado:
  - Resumen por lado (compra / venta): minimo, maximo, promedio, ultimo precio
  - Subidas y bajadas: variacion respecto a la lectura anterior
  - Spread compra/venta
  - Cuanto trabajo esta haciendo el filtro de outliers
  - Un grafico PNG por mercado (precio limpio vs bruto)

Uso:
    python stats.py

Requiere: pandas, matplotlib
    pip install pandas matplotlib
"""

import os
import re
import sys

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE, "data.csv")

# Columna principal (con filtro de outliers) y su respaldo sin filtrar
COL = "mejor_precio_limpio"
COL_BRUTO = "mejor_precio_bruto"


def cargar():
    if not os.path.exists(DATA_FILE):
        print("Todavia no hay data.csv. Corre el recolector primero.")
        sys.exit(1)

    df = pd.read_csv(DATA_FILE)

    # Compatibilidad con versiones viejas del archivo
    if COL not in df.columns and "mejor_precio" in df.columns:
        df[COL] = df["mejor_precio"]
        df[COL_BRUTO] = df["mejor_precio"]
        df["descartados"] = 0
    if "mercado" not in df.columns:
        df["mercado"] = "USD-Zinli"

    for c in (COL, COL_BRUTO):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    df["fecha_bolivia"] = pd.to_datetime(df["fecha_bolivia"])
    return df.sort_values("fecha_bolivia")


def resumen_lado(df, lado):
    d = df[df["lado"] == lado].dropna(subset=[COL])
    if d.empty:
        print(f"  [{lado.upper()}] sin datos todavia.")
        return

    precios = d[COL]
    ultimo = precios.iloc[-1]
    anterior = precios.iloc[-2] if len(precios) > 1 else None

    print(f"  --- {lado.upper()} ---")
    print(f"    Lecturas:        {len(d)}")
    print(f"    Precio minimo:   {precios.min():.4f}")
    print(f"    Precio maximo:   {precios.max():.4f}")
    print(f"    Precio promedio: {precios.mean():.4f}")
    print(f"    Ultimo precio:   {ultimo:.4f}  ({d['fecha_bolivia'].iloc[-1]})")

    if anterior is not None:
        cambio = ultimo - anterior
        pct = (cambio / anterior) * 100 if anterior else 0
        flecha = "SUBIO" if cambio > 0 else ("BAJO" if cambio < 0 else "igual")
        print(f"    vs. lectura previa: {flecha} {cambio:+.4f} ({pct:+.2f}%)")


def efecto_filtro(df):
    """Cuanto esta cambiando el filtro de outliers los numeros."""
    if "descartados" not in df.columns:
        return

    d = df.dropna(subset=[COL, COL_BRUTO])
    if d.empty:
        return

    con_descarte = pd.to_numeric(d["descartados"], errors="coerce").fillna(0) > 0
    n = int(con_descarte.sum())

    print(f"  --- FILTRO DE OUTLIERS ---")
    print(f"    Lecturas con algun descarte: {n} de {len(d)} ({n / len(d) * 100:.1f}%)")
    if n:
        dif = (d.loc[con_descarte, COL] - d.loc[con_descarte, COL_BRUTO]).abs()
        print(f"    Correccion promedio: {dif.mean():.4f}   maxima: {dif.max():.4f}")
    else:
        print("    Nunca hizo falta.")


def spread(df):
    compra = df[df["lado"] == "compra"].dropna(subset=[COL])
    venta = df[df["lado"] == "venta"].dropna(subset=[COL])
    if compra.empty or venta.empty:
        return
    c = compra[COL].iloc[-1]
    v = venta[COL].iloc[-1]
    print(f"  --- SPREAD (ultima lectura) ---")
    print(f"    Compra: {c:.4f}   Venta: {v:.4f}   Diferencia: {abs(v - c):.4f}")


def promocionados(df):
    """Cuanto se aleja la publicidad pagada del mercado real."""
    if "precio_promocionado" not in df.columns:
        return

    filas = []
    for _, r in df.iterrows():
        crudo = str(r.get("precio_promocionado") or "").strip()
        real = r.get(COL)
        if not crudo or pd.isna(real):
            continue
        for p in crudo.split("|"):
            try:
                p = float(p)
            except ValueError:
                continue
            # Positivo = la publicidad te conviene; negativo = te perjudica
            ventaja = (p - real) if r["lado"] == "venta" else (real - p)
            filas.append({"pct": ventaja / real * 100})

    if not filas:
        return

    d = pd.DataFrame(filas)
    peores = int((d["pct"] < 0).sum())
    print(f"  --- ANUNCIOS PROMOCIONADOS ---")
    print(f"    Vistos: {len(d)}   peores que el mercado real: {peores} ({peores/len(d)*100:.0f}%)")
    print(f"    Diferencia promedio frente al mejor precio real: {d['pct'].mean():+.2f}%")


def metodos(df):
    """Que metodos de pago aparecieron en la ultima lectura."""
    if "metodos_pago_vistos" not in df.columns:
        return
    vistos = df["metodos_pago_vistos"].dropna()
    vistos = vistos[vistos.astype(str).str.strip() != ""]
    if vistos.empty:
        return
    ultimos = sorted(set(str(vistos.iloc[-1]).split("|")))
    print(f"  --- METODOS DE PAGO (ultima lectura) ---")
    print(f"    {', '.join(ultimos)}")


def nombre_archivo(mercado):
    limpio = re.sub(r"[^A-Za-z0-9_-]+", "_", str(mercado))
    return os.path.join(BASE, f"evolucion_{limpio}.png")


def grafico(df, mercado):
    plt.figure(figsize=(11, 5))
    hay_datos = False

    for lado, color in (("compra", "#2e7d32"), ("venta", "#c62828")):
        d = df[df["lado"] == lado].dropna(subset=[COL])
        if d.empty:
            continue
        hay_datos = True
        plt.plot(d["fecha_bolivia"], d[COL],
                 marker="o", markersize=3, color=color,
                 label=f"{lado.capitalize()} (filtrado)")
        # El bruto va tenue por detras: donde se separa de la linea solida,
        # ahi actuo el filtro de outliers.
        if COL_BRUTO in d.columns:
            plt.plot(d["fecha_bolivia"], d[COL_BRUTO],
                     linewidth=1, alpha=0.35, linestyle="--", color=color,
                     label=f"{lado.capitalize()} (sin filtrar)")

    if not hay_datos:
        plt.close()
        return

    plt.title(f"Binance P2P - {mercado} - evolucion del mejor precio")
    plt.xlabel("Fecha (hora Bolivia)")
    plt.ylabel("Precio")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    ruta = nombre_archivo(mercado)
    plt.savefig(ruta, dpi=120)
    plt.close()
    print(f"    Grafico: {os.path.basename(ruta)}")


def main():
    df = cargar()
    print(f"Total de lecturas en la base: {len(df)}")

    for mercado in df["mercado"].dropna().unique():
        d = df[df["mercado"] == mercado]
        print(f"\n========== {mercado} ==========")
        resumen_lado(d, "compra")
        resumen_lado(d, "venta")
        spread(d)
        efecto_filtro(d)
        promocionados(d)
        metodos(d)
        grafico(d, mercado)


if __name__ == "__main__":
    main()
