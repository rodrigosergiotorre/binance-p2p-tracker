# Recolector de precios P2P de Binance (USDT/USD por Zinli)

Recolecta cada 3 horas, de forma automatica y en la nube (gratis, con GitHub
Actions), los precios de **compra y venta de USDT contra USD** en el P2P de
Binance, usando **Zinli** como metodo de pago. No necesita que tu Mac este
prendida.

## Que hace

- Cada 3 horas toma el mejor precio de compra y de venta, el promedio de los
  primeros anuncios y cuantos anuncios hay.
- Guarda todo en `data.csv`, con fecha y hora (UTC y hora Bolivia).
- Con `stats.py` genera un resumen de subidas/bajadas y un grafico.

Los dos filtros que pediri **estan desactivados** en el codigo (ver `scrape.py`):
- "Comerciante verificado" -> desactivado (`publisherType = None`)
- "Solo anuncios comerciables" -> desactivado (`filterType = "all"`)

## Archivos

- `scrape.py` -> el recolector (lo corre GitHub solo).
- `.github/workflows/scrape.yml` -> la tarea programada cada 3 horas.
- `stats.py` -> las estadisticas y el grafico (lo corres cuando quieras).
- `requirements.txt` -> dependencias.
- `data.csv` -> el resumen, una fila por lado por lectura.
- `snapshots/AAAA-MM-DD.jsonl` -> la respuesta CRUDA y completa de Binance,
  un archivo por dia. Nada se descarta: si manana queremos una estadistica
  distinta, se puede recalcular hacia atras sobre estos archivos.

---

## Mercados

Se recolectan varios mercados en la misma ejecucion. Estan definidos arriba de
todo en `scrape.py`, en la lista `MERCADOS`:

| mercado | que es | metodos de pago |
|---|---|---|
| `USD-Zinli` | USDT contra dolar | solo Zinli |
| `BOB-todos` | USDT contra boliviano | todos |

En `data.csv` la columna `mercado` dice de cual es cada fila, asi que todo
convive en el mismo archivo.

**Para agregar otro mercado** (por ejemplo pesos argentinos), copia un bloque de
`MERCADOS` y cambia los valores:

```python
{
    "nombre": "ARS-todos",
    "fiat": "ARS",
    "asset": "USDT",
    "payTypes": [],      # lista vacia = todos los metodos de pago
},
```

Si un mercado falla, los demas siguen funcionando igual: se anota el fallo y la
ejecucion continua. Solo da error si ninguno devuelve datos.

La columna `metodos_pago_vistos` te dice que metodos aparecieron en cada lectura.
Sirve para descubrir los nombres exactos que usa Binance, por si despues quieres
filtrar por uno solo.

---

## El filtro de outliers

A veces el primer anuncio de la lista esta muy alejado del resto: alguien
urgido, un monto minusculo, un error de dedo. Ese precio no representa al
mercado y ensucia el promedio.

Como lo resolvemos: se calcula la **mediana de los primeros 10 anuncios** (la
mediana casi no se mueve por uno o dos precios locos) y se recorre la lista
desde el mejor precio hacia abajo, salteando los que se alejen **mas de 1%**
de esa mediana. El primero que entra dentro del 1% es el precio bueno.

Ejemplo: si los precios son 1.000 / 1.014 / 1.014 / 1.014 / 1.015, la mediana
es 1.014 y el 1.000 se descarta por estar 1.4% abajo.

**No se pierde nada:** se guardan las dos versiones, `mejor_precio_bruto` (sin
filtrar) y `mejor_precio_limpio`, mas cuales precios se descartaron. En el
grafico de `stats.py` la linea punteada es el bruto; donde se separa de la
solida, ahi actuo el filtro.

Para cambiar que tan estricto es, edita `UMBRAL_OUTLIER` en `scrape.py`
(0.01 = 1%).

### Columnas de data.csv

| Columna | Que es |
|---|---|
| `fecha_utc` / `fecha_bolivia` | Momento de la lectura |
| `mercado` / `fiat` | De que mercado es la fila (`USD-Zinli`, `BOB-todos`...) |
| `lado` | `compra` o `venta` |
| `mejor_precio_bruto` | El primero de la lista, sin filtrar |
| `mejor_precio_limpio` | El primero que pasa el filtro de outliers |
| `promedio_top5_limpio` | Promedio de los 5 mejores ya filtrados |
| `mediana_top10` | La referencia que usa el filtro |
| `descartados` / `precios_descartados` | Cuantos se saltaron y cuales |
| `cantidad_anuncios` | Anuncios devueltos en esa lectura |
| `liquidez_total_usdt` | Suma de lo disponible en todos los anuncios |
| `mejor_min_orden` / `mejor_max_orden` | Limites de orden del mejor anuncio (util: un precio buenisimo que solo acepta $20 no sirve de mucho) |
| `mejor_comerciante` / `mejor_tipo` | Quien publica el mejor precio |
| `mejor_ordenes_mes` / `mejor_tasa_completado` | Reputacion de ese anunciante |
| `metodos_pago_vistos` | Que metodos aparecieron en esa lectura |

---

## Puesta en marcha (una sola vez)

Estos son los pasos. La parte de crear la cuenta e iniciar sesion la haces vos;
Cowork te puede acompanar y hacer el resto.

1. **Crear una cuenta en GitHub** (si no tienes): https://github.com/signup
   Esto lo haces vos con tu correo y contrasena. Es gratis.

2. **Crear un repositorio nuevo** (puede ser privado). Nombre sugerido:
   `binance-p2p-tracker`. No marques "Add a README" para no duplicar.

3. **Subir estos archivos** al repositorio (arrastrando en "Add file" ->
   "Upload files", o con git). Deben quedar con la misma estructura, incluida
   la carpeta `.github/workflows/`.

4. **Activar los workflows**: entra a la pestana **Actions** del repositorio.
   La primera vez GitHub pide confirmar que quieres habilitar las acciones ->
   dale "I understand my workflows, go ahead and enable them".

5. **Probar una lectura ya**: en **Actions** -> "Recolector P2P Binance" ->
   boton **Run workflow**. En un par de minutos deberia aparecer un `data.csv`
   nuevo en el repositorio con la primera lectura. Si aparece, todo funciona.

6. De ahi en mas, corre solo cada 3 horas. No tienes que tocar nada.

---

## Ver las estadisticas

Cuando ya tengas varias lecturas acumuladas, descarga el `data.csv` y corre:

```bash
pip install -r requirements.txt
python stats.py
```

Te muestra el resumen (minimo, maximo, promedio, ultimo precio, subida o bajada
frente a la lectura anterior, spread) y guarda un grafico `evolucion_precios.png`.

---

## Notas honestas / posibles ajustes

- GitHub corre sus servidores en EE.UU. A veces Binance limita el acceso desde
  centros de datos. Si la primera prueba (paso 5) no trae datos, no es un error
  tuyo: puede requerir un pequeno ajuste. Avisame y lo adaptamos.
- Los horarios programados en GitHub pueden atrasarse unos minutos cuando hay
  mucha carga. Para lecturas cada 3 horas no afecta nada.
- Si algun dia Binance cambia el nombre interno de "Zinli" como metodo de pago,
  habria que actualizar `payTypes` en `scrape.py`.

