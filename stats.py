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


# Cuantas muestras necesita una franja horaria para que su promedio
# signifique algo. Por debajo de esto no mostramos conclusiones.
MIN_MUESTRAS_HORA = 5


def por_hora(df, mercado):
    """
    A que hora del dia conviene comprar o vender.

    Importante: un precio bueno a una hora sin liquidez no sirve de nada,
    asi que mostramos precio Y profundidad del mercado juntos.
    """
    d = df.dropna(subset=[COL]).copy()
    if d.empty:
        return
    d["hora"] = d["fecha_bolivia"].dt.hour

    print(f"  --- POR HORA DEL DIA (hora Bolivia) ---")

    dias = d["fecha_bolivia"].dt.date.nunique()
    if dias < 3:
        print(f"    Solo {dias} dia(s) de datos. Se necesita mas historia;")
        print(f"    con lecturas cada hora, en 1-2 semanas esto ya dice algo.")
        return

    hubo_algo = False
    for lado in ("compra", "venta"):
        dl = d[d["lado"] == lado]
        if dl.empty:
            continue

        g = dl.groupby("hora").agg(
            precio=(COL, "mean"),
            muestras=(COL, "size"),
        )
        if "liquidez_total_usdt" in dl.columns:
            liq = pd.to_numeric(dl["liquidez_total_usdt"], errors="coerce")
            g["liquidez"] = liq.groupby(dl["hora"]).mean()

        g = g[g["muestras"] >= MIN_MUESTRAS_HORA]
        if g.empty:
            continue

        hubo_algo = True
        # compra: buscamos pagar menos. venta: buscamos recibir mas.
        mejor = g["precio"].idxmin() if lado == "compra" else g["precio"].idxmax()
        peor = g["precio"].idxmax() if lado == "compra" else g["precio"].idxmin()
        dif = abs(g.loc[mejor, "precio"] - g.loc[peor, "precio"])
        pct = dif / g.loc[peor, "precio"] * 100

        verbo = "comprar" if lado == "compra" else "vender"
        print(f"    Mejor hora para {verbo}: {int(mejor):02d}:00 "
              f"({g.loc[mejor, 'precio']:.4f}, {int(g.loc[mejor, 'muestras'])} muestras)")
        print(f"      peor hora: {int(peor):02d}:00 ({g.loc[peor, 'precio']:.4f})"
              f"   diferencia: {dif:.4f} ({pct:.2f}%)")

        if "liquidez" in g.columns and pd.notna(g.loc[mejor, "liquidez"]):
            liq_mejor = g.loc[mejor, "liquidez"]
            liq_media = g["liquidez"].mean()
            if liq_media and liq_mejor < liq_media * 0.5:
                print(f"      OJO: a esa hora hay poca liquidez "
                      f"({liq_mejor:,.0f} vs {liq_media:,.0f} de promedio).")

        if pct < 0.1:
            print(f"      (diferencia muy chica: puede ser ruido, no un patron)")

    if not hubo_algo:
        print(f"    Aun no hay {MIN_MUESTRAS_HORA} muestras por franja horaria.")


def evolucion_spread(df, mercado):
    """Como se movio el spread compra/venta en el tiempo."""
    c = df[df["lado"] == "compra"].dropna(subset=[COL])[["fecha_bolivia", COL]]
    v = df[df["lado"] == "venta"].dropna(subset=[COL])[["fecha_bolivia", COL]]
    if c.empty or v.empty:
        return

    j = pd.merge(c, v, on="fecha_bolivia", suffixes=("_compra", "_venta"))
    if j.empty:
        return

    j["spread"] = (j[f"{COL}_compra"] - j[f"{COL}_venta"]).abs()
    j["spread_pct"] = j["spread"] / j[f"{COL}_venta"] * 100

    print(f"  --- SPREAD EN EL TIEMPO ---")
    print(f"    Promedio: {j['spread'].mean():.4f} ({j['spread_pct'].mean():.2f}%)")
    print(f"    Minimo:   {j['spread'].min():.4f}   Maximo: {j['spread'].max():.4f}")
    print(f"    Ahora:    {j['spread'].iloc[-1]:.4f} ({j['spread_pct'].iloc[-1]:.2f}%)")

    if len(j) >= 4:
        umbral = j["spread"].quantile(0.25)
        print(f"    Spread 'estrecho' (25% mejor): por debajo de {umbral:.4f}")

    plt.figure(figsize=(11, 4))
    plt.plot(j["fecha_bolivia"], j["spread"], marker="o", markersize=3, color="#1565c0")
    plt.axhline(j["spread"].mean(), linestyle="--", alpha=0.5, color="gray",
                label=f"promedio {j['spread'].mean():.4f}")
    plt.title(f"Spread compra/venta - {mercado}")
    plt.xlabel("Fecha (hora Bolivia)")
    plt.ylabel("Diferencia")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    ruta = os.path.join(BASE, f"spread_{re.sub(r'[^A-Za-z0-9_-]+', '_', str(mercado))}.png")
    plt.savefig(ruta, dpi=120)
    plt.close()
    print(f"    Grafico: {os.path.basename(ruta)}")


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
        evolucion_spread(d, mercado)
        por_hora(d, mercado)
        efecto_filtro(d)
        promocionados(d)
        metodos(d)
        grafico(d, mercado)


if __name__ == "__main__":
    main()
