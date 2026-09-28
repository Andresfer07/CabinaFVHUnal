import pandas as pd
import numpy as np

# ============================================================
# CONFIGURACIÓN
# ============================================================

ARCHIVO = "cultivo_completo_2026-08-27_a_2026-09-08.csv"

# ============================================================
# PERÍODOS REALES DEL CICLO
# ============================================================

INICIO_CULTIVO = pd.Timestamp("2026-08-27 16:30:00")
FIN_RUNNING    = pd.Timestamp("2026-09-08 00:00:00")
FIN_SECADO     = pd.Timestamp("2026-09-08 02:00:00")

# ============================================================
# PARÁMETROS DE REFERENCIA DEL MÓDULO DE CLIMATIZACIÓN
# ============================================================

TEMP_MIN = 24.0
TEMP_MAX = 30.0

HUM_MIN = 70.0
HUM_MAX = 85.0

# Intervalos superiores a este valor no se consideran
# tiempo evaluable.
MAX_INTERVALO = 600  # 10 minutos


# ============================================================
# FUNCIÓN PARA CONVERTIR SEGUNDOS
# ============================================================

def formato_tiempo(segundos):

    if pd.isna(segundos):
        return "0 h 00 min 00 s"

    segundos = int(round(segundos))

    horas = segundos // 3600
    minutos = (segundos % 3600) // 60
    segundos_restantes = segundos % 60

    return (
        f"{horas} h "
        f"{minutos:02d} min "
        f"{segundos_restantes:02d} s"
    )


# ============================================================
# CARGAR DATOS
# ============================================================

df = pd.read_csv(
    ARCHIVO,
    low_memory=False
)

print("=" * 70)
print("AUDITORÍA DEL CULTIVO 2")
print("=" * 70)


# ============================================================
# INFORMACIÓN GENERAL
# ============================================================

print("\n--- INFORMACIÓN GENERAL ---")

print(f"Filas:    {len(df):,}")
print(f"Columnas: {len(df.columns)}")

print("\nColumnas:")

for columna in df.columns:
    print(f"  - {columna}")


# ============================================================
# TIMESTAMP
# ============================================================

print("\n--- TIEMPO ---")

df["time"] = pd.to_datetime(
    df["time"],
    errors="coerce"
)

df = df.dropna(
    subset=["time"]
)

df = df.sort_values(
    "time"
).reset_index(drop=True)

print(
    f"Inicio del archivo: "
    f"{df['time'].min()}"
)

print(
    f"Fin del archivo:    "
    f"{df['time'].max()}"
)

print(
    f"Fechas diferentes:  "
    f"{df['time'].dt.date.nunique()}"
)

duplicados_time = (
    df["time"].duplicated().sum()
)

print(
    f"Timestamps duplicados: "
    f"{duplicados_time:,}"
)


# ============================================================
# INTERVALOS GENERALES DE REGISTRO
# ============================================================

print("\n--- INTERVALOS GENERALES DE REGISTRO ---")

df["intervalo_s"] = (
    df["time"].shift(-1) -
    df["time"]
).dt.total_seconds()

intervalos_generales = df[
    df["intervalo_s"] > 0
]["intervalo_s"].dropna()

if len(intervalos_generales) > 0:

    print(
        f"Intervalo mínimo:  "
        f"{intervalos_generales.min():.1f} s"
    )

    print(
        f"Intervalo máximo:  "
        f"{intervalos_generales.max():.1f} s"
    )

    print(
        f"Intervalo medio:   "
        f"{intervalos_generales.mean():.1f} s"
    )

    print(
        f"Intervalo mediano: "
        f"{intervalos_generales.median():.1f} s"
    )

saltos_generales = df[
    df["intervalo_s"] > MAX_INTERVALO
].copy()

print(
    f"Saltos > 10 min: "
    f"{len(saltos_generales):,}"
)

if len(saltos_generales) > 0:

    print("\nMayores saltos generales:")

    print(
        saltos_generales[
            ["time", "intervalo_s"]
        ]
        .sort_values(
            "intervalo_s",
            ascending=False
        )
        .head(10)
        .to_string(index=False)
    )


# ============================================================
# DUPLICADOS COMPLETOS
# ============================================================

print("\n--- DUPLICADOS COMPLETOS ---")

duplicados_completos = df[
    df.duplicated(
        keep=False
    )
]

print(
    f"Filas duplicadas completas: "
    f"{len(duplicados_completos):,}"
)

if len(duplicados_completos) > 0:

    print("\nPrimeros duplicados:")

    print(
        duplicados_completos
        .head(20)
        .to_string(index=False)
    )


# ============================================================
# DATOS FALTANTES
# ============================================================

print("\n--- DATOS FALTANTES ---")

faltantes = df.isna().sum()

faltantes = faltantes[
    faltantes > 0
].sort_values(
    ascending=False
)

if len(faltantes) == 0:

    print(
        "No se encontraron datos faltantes."
    )

else:

    for columna, cantidad in faltantes.items():

        porcentaje = (
            cantidad /
            len(df) *
            100
        )

        print(
            f"{columna:30s} "
            f"{cantidad:8,} "
            f"({porcentaje:.2f} %)"
        )


# ============================================================
# DISTRIBUCIÓN DE ESTADOS
# ============================================================

print("\n--- ESTADOS DEL SISTEMA ---")

if "cycle_status" in df.columns:

    print(
        df["cycle_status"]
        .value_counts(
            dropna=False
        )
    )


# ============================================================
# SELECCIONAR PERÍODO REAL DEL CULTIVO
# ============================================================

df_cultivo = df[
    (df["time"] >= INICIO_CULTIVO) &
    (df["time"] <= FIN_SECADO)
].copy()

df_cultivo = (
    df_cultivo
    .sort_values("time")
    .reset_index(drop=True)
)

print("\n" + "=" * 70)
print("PERÍODO REAL DEL CICLO")
print("=" * 70)

print(
    f"Inicio del cultivo: "
    f"{INICIO_CULTIVO}"
)

print(
    f"Fin de running:     "
    f"{FIN_RUNNING}"
)

print(
    f"Fin del secado:     "
    f"{FIN_SECADO}"
)

duracion_periodo = (
    FIN_SECADO -
    INICIO_CULTIVO
).total_seconds()

print(
    "\nDuración definida del período: "
    f"{formato_tiempo(duracion_periodo)}"
)

print(
    f"Registros dentro del período: "
    f"{len(df_cultivo):,}"
)


# ============================================================
# DURACIÓN SEGÚN ESTADO
# ============================================================

print("\n--- DURACIÓN POR ESTADO ---")

if "cycle_status" in df_cultivo.columns:

    estado_df = df_cultivo[
        ["time", "cycle_status"]
    ].copy()

    estado_df["duracion_s"] = (
        estado_df["time"].shift(-1) -
        estado_df["time"]
    ).dt.total_seconds()

    estado_df.loc[
        (estado_df["duracion_s"] <= 0) |
        (estado_df["duracion_s"] > MAX_INTERVALO),
        "duracion_s"
    ] = np.nan

    for estado in [
        "running",
        "idle",
        "paused",
        "drying"
    ]:

        tiempo = estado_df.loc[
            estado_df["cycle_status"]
            .astype(str)
            .str.lower() == estado,
            "duracion_s"
        ].sum()

        print(
            f"{estado:8s}: "
            f"{formato_tiempo(tiempo)}"
        )


# ============================================================
# CONTINUIDAD DEL PERÍODO RUNNING
# ============================================================

print("\n" + "=" * 70)
print("CONTINUIDAD DEL PERÍODO RUNNING")
print("=" * 70)

df_continuidad = df[
    (df["time"] >= INICIO_CULTIVO) &
    (df["time"] < FIN_RUNNING)
].copy()

df_continuidad = (
    df_continuidad
    .sort_values("time")
    .reset_index(drop=True)
)

periodo_running_s = (
    FIN_RUNNING -
    INICIO_CULTIVO
).total_seconds()

if len(df_continuidad) > 0:

    df_continuidad["intervalo_s"] = (
        df_continuidad["time"].shift(-1) -
        df_continuidad["time"]
    ).dt.total_seconds()

    intervalos_validos_cont = (
        df_continuidad[
            (df_continuidad["intervalo_s"] > 0) &
            (df_continuidad["intervalo_s"] <= MAX_INTERVALO)
        ]["intervalo_s"]
        .dropna()
    )

    tiempo_continuo_s = (
        intervalos_validos_cont.sum()
    )

    interrupciones = df_continuidad[
        df_continuidad["intervalo_s"] > MAX_INTERVALO
    ].copy()

    tiempo_interrupciones_s = (
        interrupciones["intervalo_s"]
        .sum()
    )

    tiempo_sin_registros_s = (
        periodo_running_s -
        tiempo_continuo_s
    )

    print(
        "Período running definido: "
        f"{formato_tiempo(periodo_running_s)}"
    )

    print(
        "Tiempo con registros continuos: "
        f"{formato_tiempo(tiempo_continuo_s)}"
    )

    print(
        "Tiempo correspondiente a "
        "interrupciones >10 min: "
        f"{formato_tiempo(tiempo_interrupciones_s)}"
    )

    print(
        "Tiempo sin registros: "
        f"{formato_tiempo(tiempo_sin_registros_s)}"
    )

    print(
        "Número de interrupciones >10 min: "
        f"{len(interrupciones):,}"
    )

    if len(interrupciones) > 0:

        print(
            "Mayor interrupción: "
            f"{formato_tiempo(interrupciones['intervalo_s'].max())}"
        )

        print("\nMayores interrupciones:")

        print(
            interrupciones[
                ["time", "intervalo_s"]
            ]
            .sort_values(
                "intervalo_s",
                ascending=False
            )
            .head(10)
            .to_string(index=False)
        )


# ============================================================
# FILTRAR RUNNING REAL
# ============================================================

if "cycle_status" not in df.columns:

    print(
        "\nERROR: No existe la columna "
        "cycle_status."
    )

    exit()

df_run = df[
    (df["time"] >= INICIO_CULTIVO) &
    (df["time"] < FIN_RUNNING) &
    (
        df["cycle_status"]
        .astype(str)
        .str.lower() == "running"
    )
].copy()

df_run = (
    df_run
    .sort_values("time")
    .reset_index(drop=True)
)

print("\n" + "=" * 70)
print("ANÁLISIS DEL CULTIVO — RUNNING")
print("=" * 70)

print(
    f"\nRegistros running: "
    f"{len(df_run):,}"
)

if len(df_run) > 0:

    print(
        f"Inicio running: "
        f"{df_run['time'].min()}"
    )

    print(
        f"Fin running:    "
        f"{df_run['time'].max()}"
    )


# ============================================================
# INTERVALOS DEL RUNNING
# ============================================================

df_run["duracion_s"] = (
    df_run["time"].shift(-1) -
    df_run["time"]
).dt.total_seconds()

saltos_running = df_run[
    df_run["duracion_s"] > MAX_INTERVALO
].copy()

print("\n--- INTERVALOS DURANTE RUNNING ---")

intervalos_validos = df_run[
    (df_run["duracion_s"] > 0) &
    (df_run["duracion_s"] <= MAX_INTERVALO)
]["duracion_s"]

if len(intervalos_validos) > 0:

    print(
        f"Intervalo mínimo:       "
        f"{intervalos_validos.min():.1f} s"
    )

    print(
        f"Intervalo máximo válido: "
        f"{intervalos_validos.max():.1f} s"
    )

    print(
        f"Intervalo medio:         "
        f"{intervalos_validos.mean():.1f} s"
    )

    print(
        f"Intervalo mediano:       "
        f"{intervalos_validos.median():.1f} s"
    )

print(
    f"Saltos > 10 min durante running: "
    f"{len(saltos_running):,}"
)

if len(saltos_running) > 0:

    print("\nMayores saltos durante running:")

    print(
        saltos_running[
            ["time", "duracion_s"]
        ]
        .sort_values(
            "duracion_s",
            ascending=False
        )
        .head(10)
        .to_string(index=False)
    )


# ============================================================
# ANÁLISIS DE RANGO
# ============================================================

def analizar_rango(
    datos,
    variable,
    minimo,
    maximo
):

    if variable not in datos.columns:

        print(
            f"\n{variable}: NO EXISTE"
        )

        return

    temp = datos[
        ["time", variable, "duracion_s"]
    ].copy()

    temp[variable] = pd.to_numeric(
        temp[variable],
        errors="coerce"
    )

    temp.loc[
        (temp["duracion_s"] <= 0) |
        (temp["duracion_s"] > MAX_INTERVALO),
        "duracion_s"
    ] = np.nan

    valido = temp[
        variable
    ].notna()

    dentro = (
        valido &
        (temp[variable] >= minimo) &
        (temp[variable] <= maximo)
    )

    debajo = (
        valido &
        (temp[variable] < minimo)
    )

    encima = (
        valido &
        (temp[variable] > maximo)
    )

    tiempo_dentro = temp.loc[
        dentro,
        "duracion_s"
    ].sum()

    tiempo_debajo = temp.loc[
        debajo,
        "duracion_s"
    ].sum()

    tiempo_encima = temp.loc[
        encima,
        "duracion_s"
    ].sum()

    tiempo_total = (
        tiempo_dentro +
        tiempo_debajo +
        tiempo_encima
    )

    print("\n" + "-" * 70)

    print(
        f"{variable.upper()} "
        f"({minimo} - {maximo})"
    )

    print("-" * 70)

    print(
        f"Tiempo dentro:   "
        f"{formato_tiempo(tiempo_dentro)}"
    )

    print(
        f"Tiempo debajo:   "
        f"{formato_tiempo(tiempo_debajo)}"
    )

    print(
        f"Tiempo encima:   "
        f"{formato_tiempo(tiempo_encima)}"
    )

    print(
        f"Tiempo evaluado: "
        f"{formato_tiempo(tiempo_total)}"
    )

    if tiempo_total > 0:

        print(
            f"% dentro:  "
            f"{tiempo_dentro / tiempo_total * 100:.2f} %"
        )

        print(
            f"% debajo:  "
            f"{tiempo_debajo / tiempo_total * 100:.2f} %"
        )

        print(
            f"% encima:  "
            f"{tiempo_encima / tiempo_total * 100:.2f} %"
        )


# ============================================================
# CUMPLIMIENTO DE PARÁMETROS
# ============================================================

print("\n" + "=" * 70)
print(
    "CUMPLIMIENTO DE PARÁMETROS "
    "DURANTE RUNNING"
)
print("=" * 70)

analizar_rango(
    df_run,
    "temp_in",
    TEMP_MIN,
    TEMP_MAX
)

analizar_rango(
    df_run,
    "hum_in",
    HUM_MIN,
    HUM_MAX
)


# ============================================================
# ESTADÍSTICAS DURANTE RUNNING
# ============================================================

print("\n" + "=" * 70)
print(
    "ESTADÍSTICAS DURANTE RUNNING"
)
print("=" * 70)

variables = [
    "temp_in",
    "temp_out",
    "hum_in",
    "hum_out",
    "vpd_kpa",
    "water_level",
    "roof_fan",
    "side_fan",
    "flow_rate"
]

for variable in variables:

    if variable not in df_run.columns:

        print(
            f"\n{variable}: NO EXISTE"
        )

        continue

    serie = pd.to_numeric(
        df_run[variable],
        errors="coerce"
    )

    print(f"\n{variable}")

    print(
        f"  Válidos:   "
        f"{serie.notna().sum():,}"
    )

    print(
        f"  Faltantes: "
        f"{serie.isna().sum():,}"
    )

    if serie.notna().sum() > 0:

        print(
            f"  Mínimo:    "
            f"{serie.min():.3f}"
        )

        print(
            f"  Máximo:    "
            f"{serie.max():.3f}"
        )

        print(
            f"  Promedio:  "
            f"{serie.mean():.3f}"
        )

        print(
            f"  Mediana:   "
            f"{serie.median():.3f}"
        )


# ============================================================
# VALORES POTENCIALMENTE INVÁLIDOS
# ============================================================

print("\n" + "=" * 70)
print(
    "VALORES POTENCIALMENTE INVÁLIDOS"
)
print("=" * 70)

validaciones = {

    "hum_in < 0": (
        "hum_in",
        lambda x: x < 0
    ),

    "hum_in > 100": (
        "hum_in",
        lambda x: x > 100
    ),

    "hum_out < 0": (
        "hum_out",
        lambda x: x < 0
    ),

    "hum_out > 100": (
        "hum_out",
        lambda x: x > 100
    ),

    "temp_in < 0": (
        "temp_in",
        lambda x: x < 0
    ),

    "temp_in > 50": (
        "temp_in",
        lambda x: x > 50
    ),

    "temp_out < 0": (
        "temp_out",
        lambda x: x < 0
    ),

    "temp_out > 50": (
        "temp_out",
        lambda x: x > 50
    )
}

for nombre, (
    columna,
    condicion
) in validaciones.items():

    if columna not in df_run.columns:

        print(
            f"{nombre}: columna no existe"
        )

        continue

    serie = pd.to_numeric(
        df_run[columna],
        errors="coerce"
    )

    cantidad = condicion(
        serie
    ).sum()

    print(
        f"{nombre:20s}: "
        f"{cantidad:,}"
    )


# ============================================================
# DATOS DEL SISTEMA DE RIEGO
# ============================================================

print("\n" + "=" * 70)
print(
    "DATOS DEL SISTEMA DE RIEGO"
)
print("=" * 70)

columnas_riego = [
    "irrigation_active",
    "pump",
    "valve_1",
    "valve_2",
    "irrigation_mode",
    "emergency_irrigation_event"
]

for columna in columnas_riego:

    if columna in df_run.columns:

        print(f"\n{columna}:")

        print(
            df_run[columna]
            .value_counts(
                dropna=False
            )
            .head(20)
        )


# ============================================================
# CAUDAL
# ============================================================

if "flow_rate" in df_run.columns:

    print("\n" + "=" * 70)
    print("CAUDAL")
    print("=" * 70)

    caudal = pd.to_numeric(
        df_run["flow_rate"],
        errors="coerce"
    )

    print(
        f"Valores negativos: "
        f"{(caudal < 0).sum():,}"
    )

    print(
        f"Valores iguales a cero: "
        f"{(caudal == 0).sum():,}"
    )

    print(
        f"Valores positivos: "
        f"{(caudal > 0).sum():,}"
    )

    print(
        f"Valores faltantes: "
        f"{caudal.isna().sum():,}"
    )


# ============================================================
# DATOS DEL SISTEMA DE VENTILACIÓN
# ============================================================

print("\n" + "=" * 70)
print(
    "DATOS DEL SISTEMA DE VENTILACIÓN"
)
print("=" * 70)

for columna in [
    "roof_fan",
    "side_fan",
    "ventilation_mode"
]:

    if columna in df_run.columns:

        serie = pd.to_numeric(
            df_run[columna],
            errors="coerce"
        )

        print(f"\n{columna}")

        print(
            f"  Mínimo:   "
            f"{serie.min():.2f}"
        )

        print(
            f"  Máximo:   "
            f"{serie.max():.2f}"
        )

        print(
            f"  Promedio: "
            f"{serie.mean():.2f}"
        )


# ============================================================
# NIVEL DEL TANQUE
# ============================================================

if "water_level" in df_run.columns:

    print(
        "\n--- NIVEL DEL TANQUE "
        "DURANTE RUNNING ---"
    )

    nivel = pd.to_numeric(
        df_run["water_level"],
        errors="coerce"
    )

    print(
        f"Valores -1: "
        f"{np.sum(nivel == -1):,}"
    )

    print(
        f"Valores 0:  "
        f"{np.sum(nivel == 0):,}"
    )

    print(
        f"Valores válidos: "
        f"{np.sum(nivel >= 0):,}"
    )


# ============================================================
# HUMEDAD > 100 %
# ============================================================

if "hum_in" in df_run.columns:

    hum = pd.to_numeric(
        df_run["hum_in"],
        errors="coerce"
    )

    print(
        "\n--- HUMEDAD REGISTRADA > 100 % ---"
    )

    print(
        f"hum_in > 100 % durante running: "
        f"{np.sum(hum > 100):,}"
    )

# ============================================================
# AUDITORÍA DEL VPD
# ============================================================

if "vpd_kpa" in df_run.columns:

    print("\n" + "=" * 80)
    print("AUDITORÍA DEL VPD")
    print("=" * 80)

    temp = pd.to_numeric(
        df_run["temp_in"],
        errors="coerce"
    )

    hum = pd.to_numeric(
        df_run["hum_in"],
        errors="coerce"
    )

    vpd_registrado = pd.to_numeric(
        df_run["vpd_kpa"],
        errors="coerce"
    )

    # --------------------------------------------------------
    # VPD RECALCULADO
    # --------------------------------------------------------

    es = (
        0.6108 *
        np.exp(
            (17.27 * temp) /
            (temp + 237.3)
        )
    )

    ea = es * (
        hum / 100.0
    )

    vpd_recalculado = (
        es - ea
    )

    # --------------------------------------------------------
    # VPD REGISTRADO
    # --------------------------------------------------------

    print("\n--- VPD REGISTRADO ---")

    print(
        f"Válidos:   "
        f"{vpd_registrado.notna().sum():,}"
    )

    print(
        f"Mínimo:    "
        f"{vpd_registrado.min():.3f} kPa"
    )

    print(
        f"Máximo:    "
        f"{vpd_registrado.max():.3f} kPa"
    )

    print(
        f"Promedio:  "
        f"{vpd_registrado.mean():.3f} kPa"
    )

    print(
        f"Mediana:   "
        f"{vpd_registrado.median():.3f} kPa"
    )

    # --------------------------------------------------------
    # VPD RECALCULADO
    # --------------------------------------------------------

    print("\n--- VPD RECALCULADO ---")

    print(
        f"Válidos:   "
        f"{vpd_recalculado.notna().sum():,}"
    )

    print(
        f"Mínimo:    "
        f"{vpd_recalculado.min():.3f} kPa"
    )

    print(
        f"Máximo:    "
        f"{vpd_recalculado.max():.3f} kPa"
    )

    print(
        f"Promedio:  "
        f"{vpd_recalculado.mean():.3f} kPa"
    )

    print(
        f"Mediana:   "
        f"{vpd_recalculado.median():.3f} kPa"
    )

    # --------------------------------------------------------
    # VPD CON HUMEDAD FÍSICAMENTE VÁLIDA
    # --------------------------------------------------------

    mascara_humedad = (
        hum <= 100
    )

    vpd_valido = (
        vpd_recalculado[
            mascara_humedad
        ]
        .dropna()
    )

    print(
        "\n--- VPD CON HUMEDAD <=100 % ---"
    )

    print(
        f"Válidos:   "
        f"{len(vpd_valido):,}"
    )

    print(
        f"Mínimo:    "
        f"{vpd_valido.min():.3f} kPa"
    )

    print(
        f"Máximo:    "
        f"{vpd_valido.max():.3f} kPa"
    )

    print(
        f"Promedio:  "
        f"{vpd_valido.mean():.3f} kPa"
    )

    print(
        f"Mediana:   "
        f"{vpd_valido.median():.3f} kPa"
    )

    # --------------------------------------------------------
    # DIFERENCIA
    # --------------------------------------------------------

    comparacion = pd.concat(
        [
            vpd_registrado.rename(
                "registrado"
            ),
            vpd_recalculado.rename(
                "recalculado"
            )
        ],
        axis=1
    ).dropna()

    diferencia = (
        comparacion["registrado"] -
        comparacion["recalculado"]
    ).abs()

    print(
        "\n--- DIFERENCIA ENTRE VPD "
        "REGISTRADO Y RECALCULADO ---"
    )

    print(
        f"Máxima diferencia: "
        f"{diferencia.max():.6f} kPa"
    )

    print(
        f"Diferencia promedio: "
        f"{diferencia.mean():.6f} kPa"
    )

    # --------------------------------------------------------
    # HUMEDAD >100 %
    # --------------------------------------------------------

    print(
        "\n--- REGISTROS CON HUMEDAD >100 % ---"
    )

    print(
        f"Registros hum_in >100 %: "
        f"{(hum > 100).sum():,}"
    )


# ============================================================
# REGISTROS POR DÍA
# ============================================================

if "day" in df_run.columns:

    print(
        "\n--- REGISTROS POR DÍA "
        "DE CULTIVO ---"
    )

    print(
        df_run["day"]
        .value_counts()
        .sort_index()
    )


# ============================================================
# ETAPA DE SECADO
# ============================================================

df_drying = df[
    (df["time"] >= FIN_RUNNING) &
    (df["time"] <= FIN_SECADO)
].copy()

df_drying = (
    df_drying
    .sort_values("time")
    .reset_index(drop=True)
)

print("\n" + "=" * 70)
print("ETAPA DE SECADO")
print("=" * 70)

print(
    f"Registros secado: "
    f"{len(df_drying):,}"
)

if len(df_drying) > 0:

    print(
        f"Inicio secado: "
        f"{df_drying['time'].min()}"
    )

    print(
        f"Fin secado:    "
        f"{df_drying['time'].max()}"
    )

    for variable in [
        "temp_in",
        "hum_in",
        "temp_out",
        "hum_out",
        "roof_fan",
        "side_fan"
    ]:

        if variable not in df_drying.columns:

            continue

        serie = pd.to_numeric(
            df_drying[variable],
            errors="coerce"
        )

        if serie.notna().sum() == 0:

            continue

        print(f"\n{variable}")

        print(
            f"  Mínimo:   "
            f"{serie.min():.3f}"
        )

        print(
            f"  Máximo:   "
            f"{serie.max():.3f}"
        )

        print(
            f"  Promedio: "
            f"{serie.mean():.3f}"
        )

else:

    print(
        "\nAVISO: No se encontraron "
        "registros para la etapa "
        "de secado."
    )


# ============================================================
# VERIFICACIÓN DEL FINAL DEL CICLO
# ============================================================

print("\n" + "=" * 70)
print("VERIFICACIÓN DEL FINAL DEL CICLO")
print("=" * 70)

# Último registro de la etapa running
df_running_periodo = df[
    (df["time"] >= INICIO_CULTIVO) &
    (df["time"] < FIN_RUNNING)
].copy()

ultimo_running = (
    df_running_periodo["time"].max()
    if len(df_running_periodo) > 0
    else pd.NaT
)

# Último registro de la etapa de secado
df_secado = df[
    (df["time"] >= FIN_RUNNING) &
    (df["time"] <= FIN_SECADO)
].copy()

ultimo_secado = (
    df_secado["time"].max()
    if len(df_secado) > 0
    else pd.NaT
)

print(f"Último registro de running: {ultimo_running}")

if pd.notna(ultimo_running):
    diferencia_running = (
        FIN_RUNNING - ultimo_running
    ).total_seconds()

    print(
        "Tiempo entre el último registro de running "
        "y el fin de running: "
        f"{formato_tiempo(diferencia_running)}"
    )

print(f"\nÚltimo registro de secado: {ultimo_secado}")

if pd.notna(ultimo_secado):
    diferencia_secado = (
        FIN_SECADO - ultimo_secado
    ).total_seconds()

    print(
        "Tiempo entre el último registro de secado "
        "y el fin del secado: "
        f"{formato_tiempo(diferencia_secado)}"
    )

if pd.notna(ultimo_running):
    print(
        "\nOK: el período running contiene registros "
        "hasta prácticamente su finalización."
    )

if pd.notna(ultimo_secado):
    print(
        "OK: la etapa de secado contiene registros "
        "hasta prácticamente su finalización."
    )


# ============================================================
# RIEGOS AUTOMÁTICOS PROGRAMADOS
# ============================================================

riego = df_run.copy()

riego["irrigation_active"] = (
    riego["irrigation_active"]
    .astype(str)
    .str.lower()
    .isin([
        "true",
        "1",
        "1.0"
    ])
)

riego["emergency_irrigation_event"] = (
    riego[
        "emergency_irrigation_event"
    ]
    .astype(str)
    .str.lower()
    .isin([
        "true",
        "1",
        "1.0"
    ])
)

# ------------------------------------------------------------
# Excluir riegos de emergencia
# ------------------------------------------------------------

riego = riego[
    ~riego[
        "emergency_irrigation_event"
    ]
].copy()

# ------------------------------------------------------------
# Solo riego activo en modo AUTO
# ------------------------------------------------------------

riego["riego_real"] = (
    riego["irrigation_active"] &
    (
        riego["irrigation_mode"]
        .astype(str)
        .str.lower() == "auto"
    )
)

# ------------------------------------------------------------
# Detectar inicio de cada riego
# ------------------------------------------------------------

riego["inicio_riego"] = (
    riego["riego_real"] &
    ~riego["riego_real"]
    .shift(
        1,
        fill_value=False
    )
)

eventos = riego[
    riego["inicio_riego"]
].copy()

# ------------------------------------------------------------
# Obtener duración programada
# ------------------------------------------------------------

def obtener_duracion(row):

    try:

        duraciones = [
            float(x.strip())
            for x in str(
                row["duration_per_day"]
            ).split(",")
        ]

        dia = int(
            row["day"]
        )

        if (
            1 <= dia <=
            len(duraciones)
        ):

            return duraciones[
                dia - 1
            ]

    except:

        pass

    return np.nan


eventos[
    "duracion_programada_s"
] = eventos.apply(
    obtener_duracion,
    axis=1
)

eventos[
    "fecha_hora"
] = pd.to_datetime(
    eventos["time"]
)

print("=" * 100)
print(
    "RIEGOS AUTOMÁTICOS PROGRAMADOS"
)
print("=" * 100)

print(
    "Total de eventos:",
    len(eventos)
)

print(
    eventos[
        [
            "fecha_hora",
            "day",
            "duracion_programada_s",
            "hum_in",
            "temp_in",
            "roof_fan",
            "side_fan",
            "irrigation_mode"
        ]
    ]
    .head(30)
    .to_string(index=False)
)


# ============================================================
# RESPUESTA DE HUMEDAD Y TEMPERATURA DESPUÉS DE CADA RIEGO
# ============================================================

datos = df_run.copy()

datos["fecha_hora"] = pd.to_datetime(
    datos["time"]
)

datos["hum_in"] = pd.to_numeric(
    datos["hum_in"],
    errors="coerce"
)

datos["temp_in"] = pd.to_numeric(
    datos["temp_in"],
    errors="coerce"
)

resultados_riego = []

for _, evento in eventos.iterrows():

    inicio = evento[
        "fecha_hora"
    ]

    fin = (
        inicio +
        pd.Timedelta(
            minutes=30
        )
    )

    respuesta = datos[
        (datos["fecha_hora"] >= inicio) &
        (datos["fecha_hora"] <= fin)
    ].copy()

    if respuesta.empty:
        continue

    # ========================================================
    # HUMEDAD
    # ========================================================

    respuesta_hum = respuesta[
        respuesta["hum_in"].notna()
    ].copy()

    humedad_inicial = pd.to_numeric(
        evento["hum_in"],
        errors="coerce"
    )

    if respuesta_hum.empty or pd.isna(humedad_inicial):
        continue

    idx_max_hum = respuesta_hum[
        "hum_in"
    ].idxmax()

    humedad_max = respuesta_hum.loc[
        idx_max_hum,
        "hum_in"
    ]

    hora_max_hum = respuesta_hum.loc[
        idx_max_hum,
        "fecha_hora"
    ]

    tiempo_max_hum_s = (
        hora_max_hum -
        inicio
    ).total_seconds()

    incremento_humedad = (
        humedad_max -
        humedad_inicial
    )

    # --------------------------------------------------------
    # RECUPERACIÓN DE HUMEDAD
    # --------------------------------------------------------

    if humedad_max > HUM_MAX:

        posterior_max = respuesta_hum[
            respuesta_hum["fecha_hora"] >
            hora_max_hum
        ].copy()

        recuperacion = posterior_max[
            posterior_max["hum_in"] <= HUM_MAX
        ]

        if not recuperacion.empty:

            idx_rec = recuperacion.index[0]

            hora_rec = recuperacion.loc[
                idx_rec,
                "fecha_hora"
            ]

            humedad_rec = recuperacion.loc[
                idx_rec,
                "hum_in"
            ]

            tiempo_rec_s = (
                hora_rec -
                hora_max_hum
            ).total_seconds()

        else:

            hora_rec = pd.NaT
            humedad_rec = np.nan
            tiempo_rec_s = np.nan

    else:

        hora_rec = pd.NaT
        humedad_rec = np.nan
        tiempo_rec_s = np.nan

    # ========================================================
    # TEMPERATURA
    # ========================================================

    respuesta_temp = respuesta[
        respuesta["temp_in"].notna()
    ].copy()

    temperatura_inicial = pd.to_numeric(
        evento["temp_in"],
        errors="coerce"
    )

    if respuesta_temp.empty or pd.isna(temperatura_inicial):

        temperatura_minima = np.nan
        hora_min_temp = pd.NaT
        descenso_temperatura = np.nan
        tiempo_temp_min_s = np.nan

    else:

        idx_min_temp = respuesta_temp[
            "temp_in"
        ].idxmin()

        temperatura_minima = respuesta_temp.loc[
            idx_min_temp,
            "temp_in"
        ]

        hora_min_temp = respuesta_temp.loc[
            idx_min_temp,
            "fecha_hora"
        ]

        descenso_temperatura = (
            temperatura_inicial -
            temperatura_minima
        )

        tiempo_temp_min_s = (
            hora_min_temp -
            inicio
        ).total_seconds()

    # ========================================================
    # GUARDAR RESULTADO
    # ========================================================

    resultados_riego.append({

        "fecha_hora":
            inicio,

        "day":
            evento["day"],

        "duracion_s":
            evento[
                "duracion_programada_s"
            ],

        # Humedad
        "humedad_inicial":
            humedad_inicial,

        "humedad_maxima":
            humedad_max,

        "incremento_humedad":
            incremento_humedad,

        "tiempo_max_s":
            tiempo_max_hum_s,

        "humedad_recuperacion":
            humedad_rec,

        "tiempo_recuperacion_s":
            tiempo_rec_s,

        # Temperatura
        "temperatura_inicial":
            temperatura_inicial,

        "temperatura_minima":
            temperatura_minima,

        "descenso_temperatura":
            descenso_temperatura,

        "tiempo_temp_min_s":
            tiempo_temp_min_s,

        # Ventilación
        "roof_fan":
            evento[
                "roof_fan"
            ],

        "side_fan":
            evento[
                "side_fan"
            ]
    })


resultados_riego = pd.DataFrame(
    resultados_riego
)


# ============================================================
# RESULTADOS
# ============================================================

print(
    "\n" + "=" * 110
)

print(
    "RESPUESTA DE HUMEDAD Y TEMPERATURA "
    "DESPUÉS DE LOS RIEGOS"
)

print(
    "=" * 110
)

print(
    "Eventos analizados:",
    len(resultados_riego)
)

if len(resultados_riego) > 0:

    print(
        resultados_riego[
            [
                "fecha_hora",
                "day",
                "duracion_s",

                "humedad_inicial",
                "humedad_maxima",
                "incremento_humedad",
                "tiempo_max_s",

                "temperatura_inicial",
                "temperatura_minima",
                "descenso_temperatura",
                "tiempo_temp_min_s",

                "humedad_recuperacion",
                "tiempo_recuperacion_s",

                "roof_fan",
                "side_fan"
            ]
        ]
        .head(20)
        .to_string(index=False)
    )


# ============================================================
# RESUMEN DE RESPUESTA DE TEMPERATURA
# ============================================================

if len(resultados_riego) > 0:

    descensos_temp = (
        resultados_riego[
            "descenso_temperatura"
        ]
        .dropna()
    )

    tiempos_temp = (
        resultados_riego[
            "tiempo_temp_min_s"
        ]
        .dropna()
    )

    print(
        "\n" + "=" * 90
    )

    print(
        "DESCENSO DE TEMPERATURA "
        "DESPUÉS DE LOS RIEGOS"
    )

    print(
        "=" * 90
    )

    print(
        "Eventos analizados:",
        len(descensos_temp)
    )

    if len(descensos_temp) > 0:

        print(
            "Promedio:",
            round(
                descensos_temp.mean(),
                3
            ),
            "°C"
        )

        print(
            "Mínimo:",
            round(
                descensos_temp.min(),
                3
            ),
            "°C"
        )

        print(
            "Máximo:",
            round(
                descensos_temp.max(),
                3
            ),
            "°C"
        )

        print(
            "Percentil 25:",
            round(
                descensos_temp.quantile(0.25),
                3
            ),
            "°C"
        )

        print(
            "Mediana:",
            round(
                descensos_temp.median(),
                3
            ),
            "°C"
        )

        print(
            "Percentil 75:",
            round(
                descensos_temp.quantile(0.75),
                3
            ),
            "°C"
        )

    if len(tiempos_temp) > 0:

        print(
            "\nTiempo hasta temperatura mínima:"
        )

        print(
            "Promedio:",
            round(
                tiempos_temp.mean(),
                1
            ),
            "s"
        )

        print(
            "Mediana:",
            round(
                tiempos_temp.median(),
                1
            ),
            "s"
        )

        print(
            "P25:",
            round(
                tiempos_temp.quantile(0.25),
                1
            ),
            "s"
        )

        print(
            "P75:",
            round(
                tiempos_temp.quantile(0.75),
                1
            ),
            "s"
        )


# ============================================================
# CLASIFICACIÓN DE LOS EVENTOS
# ============================================================

if len(resultados_riego) > 0:

    resultados_riego[
        "recuperacion"
    ] = np.where(

        resultados_riego[
            "humedad_maxima"
        ] <= HUM_MAX,

        "No requirió recuperación",

        np.where(

            resultados_riego[
                "tiempo_recuperacion_s"
            ].notna(),

            "Recuperó ≤85%",

            "No recuperó ≤85% en 30 min"
        )
    )


# ============================================================
# RESUMEN DE RECUPERACIÓN
# ============================================================

if len(resultados_riego) > 0:

    total = len(
        resultados_riego
    )

    no_requiere = resultados_riego[
        resultados_riego[
            "recuperacion"
        ] ==
        "No requirió recuperación"
    ]

    con_recuperacion = resultados_riego[
        resultados_riego[
            "recuperacion"
        ] ==
        "Recuperó ≤85%"
    ]

    sin_recuperacion = resultados_riego[
        resultados_riego[
            "recuperacion"
        ] ==
        "No recuperó ≤85% en 30 min"
    ]

    eventos_superaron_85 = resultados_riego[
        resultados_riego[
            "humedad_maxima"
        ] > HUM_MAX
    ]

    print(
        "\n" + "=" * 90
    )

    print(
        "RESUMEN DE RECUPERACIÓN "
        "DE HUMEDAD"
    )

    print(
        "=" * 90
    )

    print(
        "Total de riegos:",
        total
    )

    print(
        "Eventos que superaron 85%:",
        len(eventos_superaron_85)
    )

    print(
        "Recuperó ≤85%:",
        len(con_recuperacion)
    )

    print(
        "No recuperó ≤85% en 30 min:",
        len(sin_recuperacion)
    )

    print(
        "No requirió recuperación:",
        len(no_requiere)
    )

    if len(eventos_superaron_85) > 0:

        print(
            "Porcentaje que recuperó entre "
            "los que superaron 85%:",
            round(
                len(con_recuperacion) /
                len(eventos_superaron_85) *
                100,
                2
            ),
            "%"
        )

        print(
            "Porcentaje que no recuperó entre "
            "los que superaron 85%:",
            round(
                len(sin_recuperacion) /
                len(eventos_superaron_85) *
                100,
                2
            ),
            "%"
        )

    print(
        "Porcentaje sin necesidad de "
        "recuperación:",
        round(
            len(no_requiere) /
            total *
            100,
            2
        ),
        "%"
    )


# ============================================================
# TIEMPOS DE RECUPERACIÓN
# ============================================================

if len(resultados_riego) > 0:

    tiempos = (
        con_recuperacion[
            "tiempo_recuperacion_s"
        ]
        .dropna()
    )

    print(
        "\n" + "=" * 90
    )

    print(
        "DISTRIBUCIÓN DEL TIEMPO "
        "DE RECUPERACIÓN"
    )

    print(
        "=" * 90
    )

    if len(tiempos) > 0:

        print(
            "Promedio:",
            round(
                tiempos.mean(),
                1
            ),
            "s"
        )

        print(
            "Mínimo:",
            round(
                tiempos.min(),
                1
            ),
            "s"
        )

        print(
            "Máximo:",
            round(
                tiempos.max(),
                1
            ),
            "s"
        )

        print(
            "Percentil 25:",
            round(
                tiempos.quantile(0.25),
                1
            ),
            "s"
        )

        print(
            "Mediana:",
            round(
                tiempos.median(),
                1
            ),
            "s"
        )

        print(
            "Percentil 75:",
            round(
                tiempos.quantile(0.75),
                1
            ),
            "s"
        )

    else:

        print(
            "No existen eventos "
            "con recuperación."
        )


# ============================================================
# INCREMENTO PROMEDIO DE HUMEDAD
# ============================================================

if len(resultados_riego) > 0:

    print(
        "\nIncremento promedio "
        "de humedad:",
        round(
            resultados_riego[
                "incremento_humedad"
            ].mean(),
            2
        ),
        "puntos porcentuales"
    )


# ============================================================
# TIEMPO DE RETORNO A LA HUMEDAD INICIAL
# ============================================================

if len(resultados_riego) > 0:

    resultados_riego[
        "tiempo_retorno_inicial_s"
    ] = np.nan

    resultados_riego[
        "humedad_retorno_inicial"
    ] = np.nan

    for idx, resultado in (
        resultados_riego.iterrows()
    ):

        inicio = resultado[
            "fecha_hora"
        ]

        humedad_inicial = resultado[
            "humedad_inicial"
        ]

        fin = (
            inicio +
            pd.Timedelta(
                minutes=30
            )
        )

        respuesta = datos[
            (datos["fecha_hora"] >= inicio) &
            (datos["fecha_hora"] <= fin)
        ].copy()

        respuesta = respuesta[
            respuesta["hum_in"].notna()
        ]

        if respuesta.empty:

            continue

        idx_max = respuesta[
            "hum_in"
        ].idxmax()

        hora_max = respuesta.loc[
            idx_max,
            "fecha_hora"
        ]

        posterior_max = respuesta[
            respuesta["fecha_hora"] >= hora_max
        ]

        retorno = posterior_max[
            posterior_max["hum_in"] <= humedad_inicial
        ]

        if not retorno.empty:

            idx_ret = retorno.index[0]

            hora_ret = retorno.loc[
                idx_ret,
                "fecha_hora"
            ]

            humedad_ret = retorno.loc[
                idx_ret,
                "hum_in"
            ]

            tiempo_ret = (
                hora_ret -
                inicio
            ).total_seconds()

            resultados_riego.loc[
                idx,
                "tiempo_retorno_inicial_s"
            ] = tiempo_ret

            resultados_riego.loc[
                idx,
                "humedad_retorno_inicial"
            ] = humedad_ret


# ============================================================
# COMPARACIÓN DE INDICADORES
# ============================================================

if len(resultados_riego) > 0:

    print(
        "\n" + "=" * 90
    )

    print(
        "COMPARACIÓN DE TIEMPOS "
        "DE RECUPERACIÓN"
    )

    print(
        "=" * 90
    )

    print(
        "Riegos analizados:",
        len(resultados_riego)
    )

    print(
        "Eventos que superaron 85%:",
        len(eventos_superaron_85)
    )

    print(
        "Retorno a <=85%:",
        len(con_recuperacion)
    )

    print(
        "No recuperó <=85% en 30 min:",
        len(sin_recuperacion)
    )

    print(
        "No requirió recuperación:",
        len(no_requiere)
    )

    print(
        "\n--- Retorno a <=85% ---"
    )

    tiempos_rango = (
        con_recuperacion[
            "tiempo_recuperacion_s"
        ]
        .dropna()
    )

    if len(tiempos_rango) > 0:

        print(
            "Promedio:",
            round(
                tiempos_rango.mean(),
                1
            ),
            "s"
        )

        print(
            "Mediana:",
            round(
                tiempos_rango.median(),
                1
            ),
            "s"
        )

        print(
            "P25:",
            round(
                tiempos_rango.quantile(0.25),
                1
            ),
            "s"
        )

        print(
            "P75:",
            round(
                tiempos_rango.quantile(0.75),
                1
            ),
            "s"
        )

    print(
        "\n--- Retorno a humedad inicial ---"
    )

    tiempos_inicial = (
        resultados_riego[
            "tiempo_retorno_inicial_s"
        ]
        .dropna()
    )

    print(
        "Eventos con retorno:",
        len(tiempos_inicial)
    )

    if len(tiempos_inicial) > 0:

        print(
            "Promedio:",
            round(
                tiempos_inicial.mean(),
                1
            ),
            "s"
        )

        print(
            "Mediana:",
            round(
                tiempos_inicial.median(),
                1
            ),
            "s"
        )

        print(
            "P25:",
            round(
                tiempos_inicial.quantile(0.25),
                1
            ),
            "s"
        )

        print(
            "P75:",
            round(
                tiempos_inicial.quantile(0.75),
                1
            ),
            "s"
        )


# ============================================================
# CONDICIONES EXTERIORES EN CADA RIEGO
# ============================================================

if len(resultados_riego) > 0:

    resultados_ambiente = (
        resultados_riego.copy()
    )

    resultados_ambiente[
        "fecha_hora"
    ] = pd.to_datetime(
        resultados_ambiente[
            "fecha_hora"
        ]
    )

    ambiente = df_run.copy()

    ambiente[
        "fecha_hora"
    ] = pd.to_datetime(
        ambiente["time"]
    )

    datos_exteriores = []

    for _, evento in (
        resultados_ambiente.iterrows()
    ):

        inicio = evento[
            "fecha_hora"
        ]

        anteriores = ambiente[
            ambiente[
                "fecha_hora"
            ] <= inicio
        ]

        if anteriores.empty:

            datos_exteriores.append({

                "humedad_externa_pre":
                    np.nan,

                "temperatura_externa_pre":
                    np.nan

            })

            continue

        anterior = anteriores.iloc[-1]

        datos_exteriores.append({

            "humedad_externa_pre":
                anterior["hum_out"],

            "temperatura_externa_pre":
                anterior["temp_out"]

        })

    datos_exteriores = pd.DataFrame(
        datos_exteriores,
        index=resultados_ambiente.index
    )

    resultados_ambiente[
        [
            "humedad_externa_pre",
            "temperatura_externa_pre"
        ]
    ] = datos_exteriores


    # ========================================================
    # EVENTOS SIN RECUPERACIÓN
    # ========================================================

    sin_recuperacion = (
        resultados_ambiente[
            resultados_ambiente[
                "recuperacion"
            ] ==
            "No recuperó ≤85% en 30 min"
        ]
        .copy()
    )

    print(
        "\n" + "=" * 100
    )

    print(
        "EVENTOS SIN RETORNO A <=85%"
    )

    print(
        "=" * 100
    )

    print(
        sin_recuperacion[
            [
                "fecha_hora",
                "day",
                "duracion_s",
                "humedad_inicial",
                "humedad_maxima",
                "humedad_externa_pre",
                "temperatura_externa_pre",
                "roof_fan",
                "side_fan"
            ]
        ]
        .to_string(index=False)
    )


    # ========================================================
    # COMPARACIÓN
    # ========================================================

    print(
        "\n" + "=" * 100
    )

    print(
        "CONDICIONES AMBIENTALES "
        "SEGÚN RECUPERACIÓN"
    )

    print(
        "=" * 100
    )

    comparacion = (
        resultados_ambiente
        .groupby(
            "recuperacion"
        )[
            [
                "humedad_externa_pre",
                "temperatura_externa_pre",
                "humedad_inicial",
                "humedad_maxima",
                "duracion_s"
            ]
        ]
        .agg([
            "count",
            "mean",
            "median",
            "min",
            "max"
        ])
    )

    print(
        comparacion
        .to_string()
    )


    # ========================================================
    # REVISIÓN DE EVENTOS SIN RECUPERACIÓN
    # ========================================================

    revision_17 = (
        sin_recuperacion[
            [
                "fecha_hora",
                "day",
                "duracion_s",
                "humedad_inicial",
                "humedad_maxima",
                "humedad_externa_pre",
                "temperatura_externa_pre",
                "roof_fan",
                "side_fan"
            ]
        ]
        .copy()
    )

    def clasificar_humedad_exterior(h):

        if pd.isna(h):

            return "Sin dato"

        if h < 70:

            return "Baja (<70%)"

        elif h < 80:

            return "Media (70–80%)"

        else:

            return "Alta (≥80%)"


    revision_17[
        "humedad_exterior_grupo"
    ] = (
        revision_17[
            "humedad_externa_pre"
        ]
        .apply(
            clasificar_humedad_exterior
        )
    )

    revision_17 = (
        revision_17
        .sort_values(
            "fecha_hora"
        )
    )

    print(
        "\n" + "=" * 110
    )

    print(
        "EVENTOS SIN RETORNO A <=85%"
    )

    print(
        "=" * 110
    )

    print(
        revision_17
        .to_string(index=False)
    )


    # ========================================================
    # RESUMEN POR HUMEDAD EXTERIOR
    # ========================================================

    print(
        "\n" + "=" * 110
    )

    print(
        "DISTRIBUCIÓN SEGÚN HUMEDAD EXTERIOR"
    )

    print(
        "=" * 110
    )

    print(
        revision_17[
            "humedad_exterior_grupo"
        ]
        .value_counts()
    )


    # ========================================================
    # POR DÍA
    # ========================================================

    print(
        "\n" + "=" * 110
    )

    print(
        "EVENTOS SIN RECUPERACIÓN "
        "POR DÍA"
    )

    print(
        "=" * 110
    )

    print(
        revision_17[
            [
                "day",
                "fecha_hora",
                "humedad_externa_pre",
                "humedad_inicial",
                "humedad_maxima"
            ]
        ]
        .to_string(index=False)
    )


# ============================================================
# DURACIÓN DE LOS RIEGOS
# ============================================================

if len(resultados_riego) > 0:

    duraciones = (
        resultados_riego[
            "duracion_s"
        ]
        .dropna()
    )

    print(
        "\n" + "=" * 80
    )

    print(
        "DURACIÓN DE LOS RIEGOS "
        "AUTOMÁTICOS"
    )

    print(
        "=" * 80
    )

    if len(duraciones) > 0:

        print(
            "Mínima:",
            round(
                duraciones.min(),
                1
            ),
            "s"
        )

        print(
            "Promedio:",
            round(
                duraciones.mean(),
                1
            ),
            "s"
        )

        print(
            "Máxima:",
            round(
                duraciones.max(),
                1
            ),
            "s"
        )


# ============================================================
# REVISIÓN DE MAYORES DIFERENCIAS DEL VPD - CICLO 2
# ============================================================

df_vpd = df.copy()

temp = pd.to_numeric(df_vpd["temp_in"], errors="coerce")
hum = pd.to_numeric(df_vpd["hum_in"], errors="coerce")
vpd_registrado = pd.to_numeric(df_vpd["vpd_kpa"], errors="coerce")

# Cálculo del VPD usando temperatura interna + humedad interna
es = 0.6108 * np.exp(
    (17.27 * temp) / (temp + 237.3)
)

ea = es * (hum / 100.0)

df_vpd["vpd_recalc"] = es - ea

df_vpd["vpd_diff"] = (
    vpd_registrado - df_vpd["vpd_recalc"]
).abs()

# Mostrar los 20 registros con mayor diferencia
top_vpd = (
    df_vpd[
        vpd_registrado.notna() &
        df_vpd["vpd_recalc"].notna()
    ]
    .sort_values("vpd_diff", ascending=False)
    .head(20)
)

print("\n" + "=" * 80)
print("MAYORES DIFERENCIAS ENTRE VPD REGISTRADO Y RECALCULADO")
print("=" * 80)

print(
    top_vpd[
        [
            "time",
            "temp_in",
            "hum_in",
            "vpd_kpa",
            "vpd_recalc",
            "vpd_diff"
        ]
    ].to_string(index=False)
)


# ============================================================
# TEMPERATURA EQUIVALENTE DEL VPD REGISTRADO - CICLO 2
# ============================================================

def temperatura_equivalente_vpd(vpd, rh):
    """
    Encuentra la temperatura que produciría el VPD registrado
    usando la humedad relativa registrada.
    """
    if pd.isna(vpd) or pd.isna(rh) or rh <= 0:
        return np.nan

    # Presión de vapor real
    # ea = es(T) * RH/100
    # VPD = es(T) - ea
    # VPD = es(T) * (1 - RH/100)

    es_objetivo = vpd / (1 - rh / 100.0)

    # Inversión de la ecuación de presión de vapor de saturación
    ln_ratio = np.log(es_objetivo / 0.6108)

    temperatura = (
        237.3 * ln_ratio
    ) / (
        17.27 - ln_ratio
    )

    return temperatura


top_vpd["temp_equivalente"] = top_vpd.apply(
    lambda fila: temperatura_equivalente_vpd(
        fila["vpd_kpa"],
        fila["hum_in"]
    ),
    axis=1
)

top_vpd["diferencia_temp"] = (
    top_vpd["temp_in"] -
    top_vpd["temp_equivalente"]
).abs()

print("\n" + "=" * 100)
print("TEMPERATURA EQUIVALENTE DEL VPD REGISTRADO")
print("=" * 100)

print(
    top_vpd[
        [
            "time",
            "temp_in",
            "hum_in",
            "vpd_kpa",
            "temp_equivalente",
            "diferencia_temp"
        ]
    ].to_string(index=False)
)


# ============================================================
# FINAL
# ============================================================

print("\n")
print("=" * 70)
print("ANÁLISIS TERMINADO")
print("=" * 70)

print("\nNOTAS:")

print(
    "1. El cumplimiento climático se evalúa "
    "únicamente entre 27/08 16:30 y 08/09 00:00."
)

print(
    "2. La etapa de secado entre 08/09 00:00 "
    "y 02:00 se analiza por separado."
)

print(
    "3. Los intervalos superiores a 10 minutos "
    "no se contabilizan como tiempo evaluable."
)

print(
    "4. Los valores de humedad superiores a "
    "100 % se conservan y se reportan."
)

print(
    "5. Los registros anteriores al inicio real "
    "del cultivo no participan en el análisis climático."
)

print(
    "6. El tiempo de recuperación de humedad se "
    "mide desde el máximo posterior al riego "
    "hasta el primer registro ≤85 %."
)

print(
    "7. La comparación con las condiciones "
    "exteriores es descriptiva y no establece "
    "causalidad."
)