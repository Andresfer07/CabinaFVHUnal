import pandas as pd
import os

# ============================================================
# CONFIGURACIÓN
# ============================================================

CARPETA = "."

FECHA_INICIO = "2026-08-27 00:00:00"
FECHA_FIN    = "2026-09-08 02:00:00"

# ============================================================
# BUSCAR ARCHIVOS DEL CULTIVO
# 27 DE AGOSTO → 8 DE SEPTIEMBRE
# ============================================================

archivos = []

for fecha in pd.date_range("2026-08-27", "2026-09-08"):
    nombre = f"cultivo_{fecha.strftime('%Y-%m-%d')}.csv"
    ruta = os.path.join(CARPETA, nombre)

    if os.path.exists(ruta):
        archivos.append(ruta)

if not archivos:
    print("No se encontraron archivos del cultivo.")
    exit()

print(f"Archivos encontrados: {len(archivos)}")

# ============================================================
# LEER ARCHIVOS
# ============================================================

dfs = []

for archivo in archivos:

    print(f"Leyendo {archivo}...")

    try:
        df = pd.read_csv(archivo, low_memory=False)

    except pd.errors.EmptyDataError:
        print(f"  AVISO: archivo vacío, se omite.")
        continue

    # Eliminar columna "name" si existe
    if "name" in df.columns:
        df = df.drop(columns=["name"])

    dfs.append(df)

if not dfs:
    print("No se encontraron datos válidos.")
    exit()

# ============================================================
# UNIR TODOS LOS ARCHIVOS
# ============================================================

datos = pd.concat(dfs, ignore_index=True)

print(f"Registros antes de limpiar: {len(datos)}")

# ============================================================
# ELIMINAR DUPLICADOS
# ============================================================

datos = datos.drop_duplicates()

# ============================================================
# CONVERTIR TIMESTAMP
# ============================================================

datos["time"] = pd.to_datetime(
    datos["time"],
    unit="ns",
    utc=True
)

# ============================================================
# CONVERTIR A HORA COLOMBIA
# ============================================================

datos["time"] = (
    datos["time"]
    .dt.tz_convert("America/Bogota")
    .dt.tz_localize(None)
)

# ============================================================
# ORDENAR
# ============================================================

datos = datos.sort_values("time")

# ============================================================
# FILTRAR EL PERÍODO COMPLETO
# 27 AGO 00:00 → 8 SEP 02:00
# ============================================================

datos = datos[
    (datos["time"] >= FECHA_INICIO) &
    (datos["time"] <= FECHA_FIN)
].copy()

datos = datos.reset_index(drop=True)

# ============================================================
# GUARDAR
# ============================================================

nombre_salida = "cultivo_completo_2026-08-27_a_2026-09-08"

datos.to_csv(
    f"{nombre_salida}.csv",
    index=False
)

datos.to_excel(
    f"{nombre_salida}.xlsx",
    index=False
)

# ============================================================
# RESUMEN
# ============================================================

print()
print("=" * 60)
print("CULTIVO UNIFICADO CORRECTAMENTE")
print("=" * 60)

print(f"Archivos utilizados: {len(dfs)}")
print(f"Registros finales:   {len(datos)}")
print(f"Inicio:              {datos['time'].min()}")
print(f"Fin:                 {datos['time'].max()}")

print()
print("Archivos generados:")
print(f" - {nombre_salida}.csv")
print(f" - {nombre_salida}.xlsx")

print("=" * 60)