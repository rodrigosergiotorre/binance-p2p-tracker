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
- `data.csv` -> se crea solo con la primera lectura.

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

