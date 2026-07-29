#!/usr/bin/env python3
"""
Genera tablero.html: una pagina web autocontenida con los graficos.

Se abre con doble clic, no necesita internet salvo para cargar la libreria de
graficos, ni Excel, ni instalar nada. Los datos van embebidos dentro del propio
archivo, asi que se puede copiar o mandar por correo y sigue funcionando.

Secciones:
  1. Historico diario del ultimo ano (Yadio)  -> contexto largo
  2. Precio propio por mercado (Binance P2P)  -> lo que recolectamos
  3. Spread compra/venta en el tiempo
  4. Patron por hora del dia, cruzado con liquidez

Uso:
    python tablero.py

Solo necesita la libreria estandar de Python.
"""

import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE, "data.csv")
HIST_FILE = os.path.join(BASE, "historico_bob.csv")
# Se escribe el mismo contenido en dos nombres:
#   index.html   -> es el que sirve GitHub Pages en la raiz del sitio
#   tablero.html -> nombre explicito, por si se busca el archivo en el repo
SALIDAS = [os.path.join(BASE, "index.html"), os.path.join(BASE, "tablero.html")]

COL = "mejor_precio_limpio"
COL_BRUTO = "mejor_precio_bruto"

# Minimo de muestras por franja horaria para mostrar conclusiones
MIN_MUESTRAS_HORA = 5


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def leer_data():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f)]


def leer_historico():
    if not os.path.exists(HIST_FILE):
        return []
    salida = []
    with open(HIST_FILE, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t = num(r.get("tasa_yadio"))
            if r.get("fecha") and t:
                salida.append({"x": r["fecha"], "y": t})
    return salida


def series_por_mercado(filas):
    """{mercado: {lado: [{x,y}...]}} usando el precio limpio."""
    datos = defaultdict(lambda: defaultdict(list))
    for r in filas:
        p = num(r.get(COL))
        if p is None:
            continue
        mercado = r.get("mercado") or "USD-Zinli"
        datos[mercado][r.get("lado", "")].append({"x": r.get("fecha_bolivia", ""), "y": p})
    return {m: dict(l) for m, l in datos.items()}


def series_spread(filas):
    """Spread compra/venta por mercado, emparejando por fecha."""
    porfecha = defaultdict(dict)
    for r in filas:
        p = num(r.get(COL))
        if p is None:
            continue
        mercado = r.get("mercado") or "USD-Zinli"
        porfecha[(mercado, r.get("fecha_bolivia", ""))][r.get("lado", "")] = p

    datos = defaultdict(list)
    for (mercado, fecha), lados in sorted(porfecha.items(), key=lambda kv: kv[0][1]):
        if "compra" in lados and "venta" in lados:
            datos[mercado].append({"x": fecha, "y": round(abs(lados["compra"] - lados["venta"]), 4)})
    return dict(datos)


def series_por_hora(filas):
    """
    Promedio de precio y de liquidez por hora del dia.
    Devuelve tambien cuantas muestras hay, para no mentir con pocos datos.
    """
    acc = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in filas:
        p = num(r.get(COL))
        if p is None:
            continue
        fecha = r.get("fecha_bolivia", "")
        try:
            hora = datetime.strptime(fecha, "%Y-%m-%d %H:%M:%S").hour
        except ValueError:
            continue
        mercado = r.get("mercado") or "USD-Zinli"
        acc[mercado][r.get("lado", "")][hora].append((p, num(r.get("liquidez_total_usdt"))))

    salida = {}
    for mercado, lados in acc.items():
        salida[mercado] = {}
        for lado, horas in lados.items():
            puntos = []
            for h in range(24):
                vals = horas.get(h, [])
                if not vals:
                    continue
                precios = [v[0] for v in vals]
                liqs = [v[1] for v in vals if v[1] is not None]
                puntos.append({
                    "hora": h,
                    "precio": round(sum(precios) / len(precios), 4),
                    "liquidez": round(sum(liqs) / len(liqs), 2) if liqs else None,
                    "muestras": len(precios),
                })
            salida[mercado][lado] = puntos
    return salida


def construir_datos():
    filas = leer_data()
    dias_distintos = len({r.get("fecha_bolivia", "")[:10] for r in filas if r.get("fecha_bolivia")})
    return {
        "generado": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "historico": leer_historico(),
        "precios": series_por_mercado(filas),
        "spread": series_spread(filas),
        "porhora": series_por_hora(filas),
        "lecturas": len(filas),
        "dias": dias_distintos,
        "min_muestras_hora": MIN_MUESTRAS_HORA,
    }


PLANTILLA = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tablero P2P Binance</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
  :root { --tinta:#1a1a1a; --suave:#666; --linea:#e3e3e3; --fondo:#fafafa;
          --compra:#2e7d32; --venta:#c62828; --azul:#1565c0; }
  * { box-sizing:border-box; }
  body { margin:0; padding:24px; background:var(--fondo); color:var(--tinta);
         font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
  .wrap { max-width:1080px; margin:0 auto; }
  h1 { font-size:26px; margin:0 0 4px; }
  h2 { font-size:19px; margin:0 0 4px; }
  .sub { color:var(--suave); font-size:14px; margin:0 0 24px; }
  .card { background:#fff; border:1px solid var(--linea); border-radius:10px;
          padding:20px; margin-bottom:20px; }
  .nota { font-size:13.5px; color:var(--suave); margin:6px 0 14px; }
  .aviso { background:#fff8e1; border:1px solid #ffe082; border-radius:8px;
           padding:12px 14px; font-size:14px; margin:10px 0 16px; }
  .chart { position:relative; height:340px; }
  .chart-baja { height:260px; }
  table { border-collapse:collapse; width:100%; font-size:14px; margin-top:12px; }
  th,td { text-align:left; padding:7px 10px; border-bottom:1px solid var(--linea); }
  th { color:var(--suave); font-weight:600; }
  td.n { text-align:right; font-variant-numeric:tabular-nums; }
  .pie { color:var(--suave); font-size:13px; text-align:center; margin-top:28px; }
  .kpis { display:flex; gap:14px; flex-wrap:wrap; margin-bottom:6px; }
  .kpi { flex:1; min-width:150px; background:var(--fondo);
         border:1px solid var(--linea); border-radius:8px; padding:12px 14px; }
  .kpi .v { font-size:22px; font-weight:600; font-variant-numeric:tabular-nums; }
  .kpi .t { font-size:12.5px; color:var(--suave); text-transform:uppercase;
            letter-spacing:.4px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Tablero P2P Binance</h1>
  <p class="sub">Generado el __GENERADO__ &middot; __LECTURAS__ filas propias en __DIAS__ dia(s)</p>
  <div id="app"></div>
  <p class="pie">Datos propios: Binance P2P. Historico diario: Yadio.io.<br>
     Son medidas distintas y por eso van en graficos separados.</p>
</div>

<script id="datos" type="application/json">__DATOS__</script>
<script>
const D = JSON.parse(document.getElementById('datos').textContent);
const app = document.getElementById('app');
const COLOR = { compra:'#2e7d32', venta:'#c62828' };
const fmt = n => n==null ? '—' : n.toLocaleString('es-BO',{maximumFractionDigits:4});
const hh = h => String(h).padStart(2,'0') + ':00';

function card(html){ const d=document.createElement('div'); d.className='card'; d.innerHTML=html; app.appendChild(d); return d; }

function linea(ctx, datasets, opts){
  new Chart(ctx, { type:'line', data:{datasets},
    options: Object.assign({
      responsive:true, maintainAspectRatio:false,
      interaction:{mode:'index',intersect:false},
      scales:{ x:{type:'category', ticks:{maxTicksLimit:12, autoSkip:true}, grid:{display:false}},
               y:{ticks:{callback:v=>fmt(v)}} },
      plugins:{ legend:{labels:{boxWidth:12}} }
    }, opts||{}) });
}

/* ---------- 1. Historico del ano ---------- */
if (D.historico && D.historico.length > 1) {
  const h = D.historico;
  const ult = h[h.length-1].y, pri = h[0].y;
  const min = h.reduce((a,b)=>b.y<a.y?b:a), max = h.reduce((a,b)=>b.y>a.y?b:a);
  const c = card(`
    <h2>Historico USDT/BOB &mdash; ultimo ano</h2>
    <p class="nota">Tasa diaria de Yadio.io. Sirve de contexto largo: tendencia y
       estacionalidad. No es la misma medida que el precio de Binance P2P de abajo.</p>
    <div class="kpis">
      <div class="kpi"><div class="t">Hoy</div><div class="v">${fmt(ult)}</div></div>
      <div class="kpi"><div class="t">Hace un ano</div><div class="v">${fmt(pri)}</div></div>
      <div class="kpi"><div class="t">Minimo</div><div class="v">${fmt(min.y)}</div><div class="t">${min.x}</div></div>
      <div class="kpi"><div class="t">Maximo</div><div class="v">${fmt(max.y)}</div><div class="t">${max.x}</div></div>
    </div>
    <div class="chart"><canvas></canvas></div>`);
  linea(c.querySelector('canvas'), [{
    label:'USDT/BOB (Yadio)', data:h.map(p=>({x:p.x,y:p.y})),
    borderColor:'#1565c0', backgroundColor:'rgba(21,101,192,.08)',
    fill:true, pointRadius:0, borderWidth:2, tension:.2
  }]);
}

/* ---------- 2. Precio propio por mercado ---------- */
const mercados = Object.keys(D.precios||{});
if (!mercados.length) {
  card(`<h2>Tus datos</h2><div class="aviso">Todavia no hay lecturas propias.
        Aparecen solas conforme el recolector vaya corriendo.</div>`);
}
mercados.forEach(m => {
  const lados = D.precios[m];
  const n = Object.values(lados).reduce((a,b)=>a+b.length,0);
  const c = card(`
    <h2>${m} &mdash; mejor precio</h2>
    <p class="nota">Binance P2P, ya sin anuncios promocionados. ${n} punto(s).</p>
    ${n<6 ? '<div class="aviso">Con tan pocos puntos el grafico todavia no dice nada. Se llena solo con las horas.</div>' : ''}
    <div class="chart"><canvas></canvas></div>`);
  linea(c.querySelector('canvas'), Object.entries(lados).map(([lado,pts])=>({
    label: lado, data: pts, borderColor: COLOR[lado]||'#666',
    backgroundColor:'transparent', pointRadius: pts.length>60?0:3,
    borderWidth:2, tension:.2
  })));
});

/* ---------- 3. Spread ---------- */
Object.entries(D.spread||{}).forEach(([m,pts]) => {
  if (!pts.length) return;
  const vals = pts.map(p=>p.y);
  const prom = vals.reduce((a,b)=>a+b,0)/vals.length;
  const c = card(`
    <h2>${m} &mdash; spread compra/venta</h2>
    <p class="nota">Diferencia entre lo que pagas al comprar y lo que recibes al
       vender. Cuanto mas bajo, mejor momento para operar.</p>
    <div class="kpis">
      <div class="kpi"><div class="t">Ahora</div><div class="v">${fmt(vals[vals.length-1])}</div></div>
      <div class="kpi"><div class="t">Promedio</div><div class="v">${fmt(prom)}</div></div>
      <div class="kpi"><div class="t">Minimo</div><div class="v">${fmt(Math.min(...vals))}</div></div>
      <div class="kpi"><div class="t">Maximo</div><div class="v">${fmt(Math.max(...vals))}</div></div>
    </div>
    <div class="chart chart-baja"><canvas></canvas></div>`);
  linea(c.querySelector('canvas'), [{
    label:'spread', data:pts, borderColor:'#1565c0',
    backgroundColor:'rgba(21,101,192,.08)', fill:true,
    pointRadius: pts.length>60?0:3, borderWidth:2, tension:.2
  }]);
});

/* ---------- 4. Por hora del dia ---------- */
Object.entries(D.porhora||{}).forEach(([m,lados]) => {
  const listas = Object.values(lados);
  const suficientes = listas.some(p => p.some(x => x.muestras >= D.min_muestras_hora));
  const c = card(`
    <h2>${m} &mdash; por hora del dia</h2>
    <p class="nota">Precio promedio segun la hora (hora Bolivia). Para comprar
       interesa el punto mas bajo; para vender, el mas alto.</p>
    ${!suficientes ? `<div class="aviso"><b>Aun no hay suficientes datos.</b>
       Hacen falta al menos ${D.min_muestras_hora} lecturas en una misma franja horaria,
       o sea cerca de una semana. Lo que se dibuje abajo hasta entonces es ruido, no un patron.</div>` : ''}
    <div class="chart chart-baja"><canvas></canvas></div>
    <div class="tabla"></div>`);

  const ds = Object.entries(lados).map(([lado,pts])=>({
    label: lado, data: pts.map(p=>({x:hh(p.hora), y:p.precio})),
    borderColor: COLOR[lado]||'#666', backgroundColor:'transparent',
    pointRadius:3, borderWidth:2, tension:.25
  }));
  linea(c.querySelector('canvas'), ds);

  if (suficientes) {
    let filas = '';
    Object.entries(lados).forEach(([lado,pts])=>{
      const ok = pts.filter(p=>p.muestras >= D.min_muestras_hora);
      if (!ok.length) return;
      const mejor = lado==='compra'
        ? ok.reduce((a,b)=>b.precio<a.precio?b:a)
        : ok.reduce((a,b)=>b.precio>a.precio?b:a);
      const liqProm = ok.filter(p=>p.liquidez!=null)
                        .reduce((a,b,_,arr)=>a+b.liquidez/arr.length,0);
      const poca = mejor.liquidez!=null && liqProm && mejor.liquidez < liqProm*0.5;
      filas += `<tr><td>${lado==='compra'?'Comprar':'Vender'}</td>
                    <td><b>${hh(mejor.hora)}</b></td>
                    <td class="n">${fmt(mejor.precio)}</td>
                    <td class="n">${fmt(mejor.liquidez)}${poca?' ⚠️':''}</td>
                    <td class="n">${mejor.muestras}</td></tr>`;
    });
    if (filas) c.querySelector('.tabla').innerHTML =
      `<table><tr><th>Accion</th><th>Mejor hora</th><th>Precio</th>
        <th>Liquidez (USDT)</th><th>Muestras</th></tr>${filas}</table>
       <p class="nota">⚠️ = a esa hora hay menos de la mitad de la liquidez promedio.
          Buen precio sin profundidad puede no ser operable.</p>`;
  }
});
</script>
</body>
</html>
"""


def main():
    datos = construir_datos()

    html = (PLANTILLA
            .replace("__GENERADO__", datos["generado"])
            .replace("__LECTURAS__", str(datos["lecturas"]))
            .replace("__DIAS__", str(datos["dias"]))
            .replace("__DATOS__", json.dumps(datos, ensure_ascii=False)))

    for ruta in SALIDAS:
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(html)

    print(f"{', '.join(os.path.basename(r) for r in SALIDAS)}: {len(html) // 1024} KB")
    print(f"  historico: {len(datos['historico'])} dias")
    print(f"  mercados:  {', '.join(datos['precios']) or 'ninguno todavia'}")
    print(f"  lecturas propias: {datos['lecturas']} en {datos['dias']} dia(s)")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"ERROR generando el tablero: {e}", file=sys.stderr)
        sys.exit(1)
