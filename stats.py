#!/usr/bin/env python3
"""
Genera estadisticas a partir de data.csv:
  - Resumen por lado (compra / venta): minimo, maximo, promedio, ultimo precio
  - Subidas y bajadas: variacion respecto a la lectura anterior
  - Spread compra/venta
  - Cuanto trabajo esta haciendo el filtro de outliers
  - Un grafico PNG con la evolucion de precios (limpio vs bruto)

Uso:
    python stats.py

Requiere: pandas, matplotlib
    pip install pandas matplotlib
"""

import os
import sys

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE, "data.csv")
GRAFICO = os.path.join(BASE, "evolucion_precios.png")

# Columna principal (con filtro de outliers) y su respaldo sin filtrar
COL = "mejor_precio_limpio"
COL_BRUTO = "mejor_precio_bruto"


def cargar():
    if not os.path.exists(DATA_FILE):
        print("Todavia no hay data.csv. Corre el recolector primero.")
        sys.exit(1)

    df = pd.read_csv(DATA_FILE)

    # Compatibilidad con la version vieja del archivo (columna "mejor_precio")
    if COL not in df.columns and "mejor_precio" in df.columns:
        df[COL] = df["mejor_precio"]
        df[COL_BRUTO] = df["mejor_precio"]
        df["descartados"] = 0

    for c in (COL, COL_BRUTO):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    df["fecha_bolivia"] = pd.to_datetime(df["fecha_bolivia"])
    return df.sort_values("fecha_bolivia")


def resumen_lado(df, lado):
    d = df[df["lado"] == lado].dropna(subset=[COL])
    if d.empty:
        print(f"\n[{lado.upper()}] sin datos todavia.")
        return

    precios = d[COL]
    ultimo = precios.iloc[-1]
    anterior = precios.iloc[-2] if len(precios) > 1 else None

    print(f"\n===== {lado.upper()} (USDT/USD, Zinli) =====")
    print(f"  Lecturas:        {len(d)}")
    print(f"  Precio minimo:   {precios.min():.4f}")
    print(f"  Precio maximo:   {precios.max():.4f}")
    print(f"  Precio promedio: {precios.mean():.4f}")
    print(f"  Ultimo precio:   {ultimo:.4f}  ({d['fecha_bolivia'].iloc[-1]})")

    if anterior is not None:
        cambio = ultimo - anterior
        pct = (cambio / anterior) * 100 if anterior else 0
        flecha = "SUBIO" if cambio > 0 else ("BAJO" if cambio < 0 else "igual")
        print(f"  vs. lectura previa: {flecha} {cambio:+.4f} ({pct:+.2f}%)")


def efecto_filtro(df):
    """Cuanto esta cambiando el filtro de outliers los numeros."""
    if "descartados" not in df.columns:
        return

    d = df.dropna(subset=[COL, COL_BRUTO])
    if d.empty:
        return

    con_descarte = (pd.to_numeric(d["descartados"], errors="coerce").fillna(0) > 0)
    n = int(con_descarte.sum())

    print("\n===== FILTRO DE OUTLIERS =====")
    print(f"  Lecturas con algun anuncio descartado: {n} de {len(d)} "
          f"({n / len(d) * 100:.1f}%)")

    if n:
        dif = (d.loc[con_descarte, COL] - d.loc[con_descarte, COL_BRUTO]).abs()
        print(f"  Cuando actua, corrige en promedio: {dif.mean():.4f}")
        print(f"  Correccion mas grande:             {dif.max():.4f}")
    else:
        print("  Nunca hizo falta: ningun precio se alejo mas de 1% de la mediana.")


def spread(df):
    compra = df[df["lado"] == "compra"].dropna(subset=[COL])
    venta = df[df["lado"] == "venta"].dropna(subset=[COL])
    if compra.empty or venta.empty:
        return
    c = compra[COL].iloc[-1]
    v = venta[COL].iloc[-1]
    print("\n===== SPREAD (ultima lectura) =====")
    print(f"  Compra: {c:.4f}   Venta: {v:.4f}   Diferencia: {abs(v - c):.4f}")


def grafico(df):
    plt.figure(figsize=(11, 5))
    for lado, color in (("compra", "#2e7d32"), ("venta", "#c62828")):
        d = df[df["lado"] == lado].dropna(subset=[COL])
        if d.empty:
            continue
        plt.plot(d["fecha_bolivia"], d[COL],
                 marker="o", markersize=3, label=f"{lado.capitalize()} (filtrado)",
                 color=color)
        # El bruto se dibuja tenue por detras: donde se separa de la linea
        # solida, ahi actuo el filtro de outliers.
        if COL_BRUTO in d.columns:
            plt.plot(d["fecha_bolivia"], d[COL_BRUTO],
                     linewidth=1, alpha=0.35, linestyle="--",
                     label=f"{lado.capitalize()} (sin filtrar)", color=color)

    plt.title("USDT/USD por Zinli en Binance P2P - evolucion del mejor precio")
    plt.xlabel("Fecha (hora Bolivia)")
    plt.ylabel("Precio")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(GRAFICO, dpi=120)
    print(f"\nGrafico guardado en: {GRAFICO}")


def main():
    df = cargar()
    print(f"Total de lecturas en la base: {len(df)}")
    resumen_lado(df, "compra")
    resumen_lado(df, "venta")
    spread(df)
    efecto_filtro(df)
    grafico(df)


if __name__ == "__main__":
    main()
