#!/usr/bin/env python3
"""
Genera estadisticas a partir de data.csv:
  - Resumen por lado (compra / venta): minimo, maximo, promedio, ultimo precio
  - Subidas y bajadas: variacion respecto a la lectura anterior
  - Spread compra/venta
  - Un grafico PNG con la evolucion de precios

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


def cargar():
    if not os.path.exists(DATA_FILE):
        print("Todavia no hay data.csv. Corre el recolector primero.")
        sys.exit(1)
    df = pd.read_csv(DATA_FILE)
    df["fecha_bolivia"] = pd.to_datetime(df["fecha_bolivia"])
    df = df.sort_values("fecha_bolivia")
    return df


def resumen_lado(df, lado):
    d = df[df["lado"] == lado].dropna(subset=["mejor_precio"])
    if d.empty:
        print(f"\n[{lado.upper()}] sin datos todavia.")
        return

    precios = d["mejor_precio"]
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


def spread(df):
    compra = df[df["lado"] == "compra"].dropna(subset=["mejor_precio"])
    venta = df[df["lado"] == "venta"].dropna(subset=["mejor_precio"])
    if compra.empty or venta.empty:
        return
    c = compra["mejor_precio"].iloc[-1]
    v = venta["mejor_precio"].iloc[-1]
    print("\n===== SPREAD (ultima lectura) =====")
    print(f"  Compra: {c:.4f}   Venta: {v:.4f}   Diferencia: {abs(v - c):.4f}")


def grafico(df):
    plt.figure(figsize=(11, 5))
    for lado, color in (("compra", "#2e7d32"), ("venta", "#c62828")):
        d = df[df["lado"] == lado].dropna(subset=["mejor_precio"])
        if not d.empty:
            plt.plot(d["fecha_bolivia"], d["mejor_precio"],
                     marker="o", markersize=3, label=lado.capitalize(), color=color)
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
    grafico(df)


if __name__ == "__main__":
    main()

