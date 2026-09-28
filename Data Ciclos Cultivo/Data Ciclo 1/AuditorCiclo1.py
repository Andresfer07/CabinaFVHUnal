import pandas as pd
import numpy as np

# ============================================================
# CONFIGURACIÓN
# ============================================================

ARCHIVO = "cultivo_completo_2026-06-23_a_2026-07-04.csv"

# ============================================================
# PERÍODOS REALES DEL CICLO 1
# ============================================================

INICIO_CULTIVO = pd.Timestamp("2026-06-23 09:40:57")
FIN_RUNNING    = pd.Timestamp("2026-07-04 00:00:00")
FIN_SECADO     = pd.Timestamp("2026-07-04 02:00:00")

# ============================================================
# PARÁMETROS DE REFERENCIA
# ============================================================

TEMP_MIN = 24.0
TEMP_MAX = 30.0

HUM_MIN = 70.0
HUM_MAX = 85.0

# Intervalos superiores a 10 minutos
# no se consideran tiempo evaluable.
MAX_INTERVALO = 600


# ============================================================
# CARGAR DATOS
# ============================================================

df = pd.read_csv(
    ARCHIVO,
    low_memory=False
)

print("=" * 80)
print("AUDITORÍA DEL CULTIVO 1")
print("=" * 80)


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
    f"Inicio del archivo: {df['time'].min()}"
)

print(
    f"Fin del archivo:    {df['time'].max()}"
)

print(
    f"Fechas diferentes:  "
    f"{df['time'].dt.date.nunique()}"
)

duplicados_time = df["time"].duplicated().sum()

print(
    f"Timestamps duplicados: "
    f"{duplicados_time:,}"
)


# ============================================================
# SELECCIONAR PERÍODO COMPLETO DEL CICLO
# ============================================================

df_cultivo = df[
    (df["time"] >= INICIO_CULTIVO) &
    (df["time"] <= FIN_SECADO)
].copy()

df_cultivo = df_cultivo.sort_values(
    "time"
).reset_index(drop=True)

print("\n" + "=" * 80)
print("PERÍODO DEFINIDO PARA EL CICLO")
print("=" * 80)

print(
    f"Inicio del cultivo: {INICIO_CULTIVO}"
)

print(
    f"Fin de running:     {FIN_RUNNING}"
)

print(
    f"Fin del secado:     {FIN_SECADO}"
)

print(
    f"\nRegistros dentro del período: "
    f"{len(df_cultivo):,}"
)


# ============================================================
# FUNCIÓN DE FORMATO DE TIEMPO
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
# DISTRIBUCIÓN DE ESTADOS
# ============================================================

print("\n--- ESTADOS DEL SISTEMA ---")

if "cycle_status" in df_cultivo.columns:

    print(
        df_cultivo["cycle_status"]
        .value_counts(dropna=False)
    )


# ============================================================
# DURACIÓN SEGÚN ESTADO
# ============================================================

print("\n" + "=" * 80)
print("DURACIÓN REGISTRADA SEGÚN ESTADO")
print("=" * 80)

if "cycle_status" in df_cultivo.columns:

    estado_df = df_cultivo[
        ["time", "cycle_status"]
    ].copy()

    estado_df["duracion_s"] = (
        estado_df["time"].shift(-1)
        - estado_df["time"]
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
# BALANCE TEMPORAL COMPLETO DEL CICLO
# ============================================================

print("\n" + "=" * 80)
print("BALANCE TEMPORAL COMPLETO DEL CICLO")
print("=" * 80)

# ------------------------------------------------------------
# Periodo real de RUNNING definido
# ------------------------------------------------------------

duracion_periodo = (
    FIN_RUNNING - INICIO_CULTIVO
).total_seconds()

print("\nDEBUG FECHAS REALES:")
print("INICIO_CULTIVO:", INICIO_CULTIVO)
print("FIN_RUNNING:", FIN_RUNNING)
print("FIN_SECADO:", FIN_SECADO)
print("Diferencia directa:", FIN_RUNNING - INICIO_CULTIVO)

duracion_periodo = (
    FIN_RUNNING - INICIO_CULTIVO
).total_seconds()

# ------------------------------------------------------------
# Registros dentro del periodo de RUNNING
# ------------------------------------------------------------

df_balance = df_cultivo[
    (df_cultivo["time"] >= INICIO_CULTIVO) &
    (df_cultivo["time"] < FIN_RUNNING)
].copy()

df_balance = df_balance.sort_values(
    "time"
).reset_index(drop=True)

# ------------------------------------------------------------
# Tiempo inicial sin registro
# ------------------------------------------------------------

if len(df_balance) > 0:

    primer_registro = df_balance["time"].iloc[0]

    tiempo_inicial_sin_registro = max(
        0,
        (
            primer_registro -
            INICIO_CULTIVO
        ).total_seconds()
    )

else:

    tiempo_inicial_sin_registro = (
        duracion_periodo
    )

# ------------------------------------------------------------
# Intervalos entre registros
# ------------------------------------------------------------

df_balance["intervalo_s"] = (
    df_balance["time"].shift(-1)
    - df_balance["time"]
).dt.total_seconds()

# ------------------------------------------------------------
# Tiempo continuo registrado
# Se considera válido hasta 10 minutos
# ------------------------------------------------------------

intervalos_continuos = df_balance[
    (df_balance["intervalo_s"] > 0) &
    (df_balance["intervalo_s"] <= MAX_INTERVALO)
]["intervalo_s"]

tiempo_continuo = (
    intervalos_continuos.sum()
)

# ------------------------------------------------------------
# Interrupciones mayores de 10 minutos
# ------------------------------------------------------------

intervalos_largos = df_balance[
    df_balance["intervalo_s"] > MAX_INTERVALO
]["intervalo_s"]

tiempo_interrupciones = (
    intervalos_largos.sum()
)

# ------------------------------------------------------------
# Tiempo final sin registro
# ------------------------------------------------------------

if len(df_balance) > 0:

    ultimo_registro = df_balance["time"].iloc[-1]

    tiempo_final_sin_registro = max(
        0,
        (
            FIN_RUNNING -
            ultimo_registro
        ).total_seconds()
    )

else:

    tiempo_final_sin_registro = 0

# ------------------------------------------------------------
# Tiempo total sin registros
# ------------------------------------------------------------

tiempo_sin_registros = (
    tiempo_inicial_sin_registro +
    tiempo_interrupciones +
    tiempo_final_sin_registro
)

# ------------------------------------------------------------
# Comprobación matemática
# ------------------------------------------------------------

tiempo_balanceado = (
    tiempo_continuo +
    tiempo_sin_registros
)

diferencia_balance = (
    duracion_periodo -
    tiempo_balanceado
)

# ------------------------------------------------------------
# RESULTADOS
# ------------------------------------------------------------

print(
    f"Periodo total definido:          "
    f"{formato_tiempo(duracion_periodo)}"
)

print(
    f"Tiempo con registros continuos:  "
    f"{formato_tiempo(tiempo_continuo)}"
)

print(
    f"Tiempo sin registros:             "
    f"{formato_tiempo(tiempo_sin_registros)}"
)

print(
    f"  Inicio del periodo:             "
    f"{formato_tiempo(tiempo_inicial_sin_registro)}"
)

print(
    f"  Interrupciones >10 min:         "
    f"{formato_tiempo(tiempo_interrupciones)}"
)

print(
    f"  Final del periodo:              "
    f"{formato_tiempo(tiempo_final_sin_registro)}"
)

print(
    f"\nTiempo balanceado:                "
    f"{formato_tiempo(tiempo_balanceado)}"
)

print(
    f"Diferencia de comprobación:       "
    f"{formato_tiempo(abs(diferencia_balance))}"
)

if abs(diferencia_balance) < 1:

    print(
        "\nOK: el balance temporal cierra "
        "correctamente."
    )

else:

    print(
        "\nADVERTENCIA: el balance temporal "
        "no cierra."
    )


# ============================================================
# ANÁLISIS DE CONTINUIDAD Y PÉRDIDA DE REGISTROS
# ============================================================

print("\n" + "=" * 80)
print("CONTINUIDAD Y PÉRDIDA DE REGISTROS")
print("=" * 80)

continuidad = df_cultivo[
    ["time"]
].copy()

continuidad["duracion_s"] = (
    continuidad["time"].shift(-1)
    - continuidad["time"]
).dt.total_seconds()

# Saltos internos superiores a 10 minutos
interrupciones = continuidad[
    continuidad["duracion_s"] > MAX_INTERVALO
].copy()

print(
    f"Interrupciones internas > 10 min: "
    f"{len(interrupciones):,}"
)

if len(interrupciones) > 0:

    tiempo_interrupciones = (
        interrupciones["duracion_s"]
        .sum()
    )

    mayor_interrupcion = (
        interrupciones["duracion_s"]
        .max()
    )

    print(
        "Tiempo acumulado en interrupciones: "
        f"{formato_tiempo(tiempo_interrupciones)}"
    )

    print(
        "Mayor interrupción registrada: "
        f"{formato_tiempo(mayor_interrupcion)}"
    )

    print("\nPrincipales interrupciones:")

    principales = interrupciones.sort_values(
        "duracion_s",
        ascending=False
    ).head(10)

    for _, fila in principales.iterrows():

        inicio = fila["time"]
        duracion = fila["duracion_s"]

        siguiente = (
            inicio +
            pd.Timedelta(seconds=duracion)
        )

        print(
            f"  {inicio} -> {siguiente} | "
            f"{formato_tiempo(duracion)}"
        )

else:

    print(
        "No se detectaron interrupciones "
        "internas superiores a 10 minutos."
    )


# ============================================================
# TIEMPO SIN REGISTROS AL FINAL DEL PERÍODO
# ============================================================

ultimo_registro = df_cultivo["time"].max()

if not pd.isna(ultimo_registro):

    if ultimo_registro < FIN_RUNNING:

        tiempo_hasta_fin_running = (
            FIN_RUNNING -
            ultimo_registro
        ).total_seconds()

        print(
            "\nTiempo desde el último registro "
            "hasta el final de running: "
            f"{formato_tiempo(tiempo_hasta_fin_running)}"
        )

        print(
            "NOTA: este intervalo corresponde al "
            "tiempo restante hasta el final definido "
            "del estado running."
        )

    else:
        print(
            "\nEl archivo contiene registros "
            "hasta el final del período running definido."
        )

# ============================================================
# FILTRAR RUNNING REAL
# ============================================================

if "cycle_status" not in df.columns:

    print(
        "\nERROR: No existe la columna cycle_status."
    )

    raise SystemExit

df_run = df[
    (df["time"] >= INICIO_CULTIVO) &
    (df["time"] < FIN_RUNNING) &
    (
        df["cycle_status"]
        .astype(str)
        .str.lower() == "running"
    )
].copy()

df_run = df_run.sort_values(
    "time"
).reset_index(drop=True)

print("\n" + "=" * 80)
print("ANÁLISIS DEL CULTIVO — RUNNING")
print("=" * 80)

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
    df_run["time"].shift(-1)
    - df_run["time"]
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
        f"Intervalo mínimo: "
        f"{intervalos_validos.min():.1f} s"
    )

    print(
        f"Intervalo máximo válido: "
        f"{intervalos_validos.max():.1f} s"
    )

    print(
        f"Intervalo medio: "
        f"{intervalos_validos.mean():.1f} s"
    )

    print(
        f"Intervalo mediano: "
        f"{intervalos_validos.median():.1f} s"
    )

print(
    f"Saltos > 10 min durante running: "
    f"{len(saltos_running):,}"
)

if len(saltos_running) > 0:

    tiempo_saltos_running = (
        saltos_running["duracion_s"]
        .sum()
    )

    print(
        "Tiempo acumulado de estos saltos: "
        f"{formato_tiempo(tiempo_saltos_running)}"
    )

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
# LIMPIEZA DE DATOS DE SENSORES
# ============================================================
#
# IMPORTANTE:
# Los valores inválidos NO se eliminan del archivo original.
# Se contabilizan y luego se convierten a NaN únicamente
# para evitar que entren en las estadísticas.
# ============================================================

print("\n" + "=" * 80)
print("CALIDAD DE LOS DATOS DE SENSORES")
print("=" * 80)

variables_sensor = [
    "temp_in",
    "temp_out",
    "hum_in",
    "hum_out"
]

# Copia de los valores originales para contabilizar
# los valores inválidos antes de limpiarlos.

conteo_invalidos = {}

for variable in variables_sensor:

    if variable not in df_run.columns:
        continue

    serie_original = pd.to_numeric(
        df_run[variable],
        errors="coerce"
    )

    ceros = (
        serie_original == 0
    ).sum()

    faltantes = (
        serie_original.isna()
    ).sum()

    conteo_invalidos[variable] = {
        "ceros": int(ceros),
        "faltantes": int(faltantes)
    }

    print(f"\n{variable}")

    print(
        f"  Valores 0: "
        f"{ceros:,}"
    )

    print(
        f"  Valores no numéricos/NaN: "
        f"{faltantes:,}"
    )

    # Los ceros no representan una medición válida
    df_run[variable] = serie_original

    df_run.loc[
        df_run[variable] == 0,
        variable
    ] = np.nan


# ============================================================
# LIMPIEZA DEL NIVEL DEL TANQUE
# ============================================================

if "water_level" in df_run.columns:

    nivel_original = pd.to_numeric(
        df_run["water_level"],
        errors="coerce"
    )

    invalidos_nivel = (
        nivel_original <= 0
    ).sum()

    nivel_nan = (
        nivel_original.isna()
    ).sum()

    print("\nwater_level")

    print(
        f"  Valores -1 o 0: "
        f"{invalidos_nivel:,}"
    )

    print(
        f"  Valores no numéricos/NaN: "
        f"{nivel_nan:,}"
    )

    df_run["water_level"] = nivel_original

    # Para estadísticas solo se consideran
    # niveles mayores que cero.
    df_run.loc[
        df_run["water_level"] <= 0,
        "water_level"
    ] = np.nan


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

    # Solo intervalos válidos
    temp.loc[
        (temp["duracion_s"] <= 0) |
        (temp["duracion_s"] > MAX_INTERVALO),
        "duracion_s"
    ] = np.nan

    valido = (
        temp[variable].notna() &
        temp["duracion_s"].notna()
    )

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

print("\n" + "=" * 80)
print("CUMPLIMIENTO DE PARÁMETROS DURANTE RUNNING")
print("=" * 80)

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
# ESTADÍSTICAS DE VARIABLES
# ============================================================

print("\n" + "=" * 80)
print("ESTADÍSTICAS DURANTE RUNNING")
print("=" * 80)

variables = [
    "temp_in",
    "temp_out",
    "hum_in",
    "hum_out",
    "vpd_kpa",
    "water_level",
    "roof_fan",
    "side_fan"
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
# NIVEL DEL TANQUE
# ============================================================

if "water_level" in df_run.columns:

    print("\n" + "=" * 80)
    print("NIVEL DEL TANQUE DURANTE RUNNING")
    print("=" * 80)

    nivel = pd.to_numeric(
        df_run["water_level"],
        errors="coerce"
    )

    # Se utiliza el dato original para contabilizar
    # los valores inválidos.
    nivel_original = pd.to_numeric(
        pd.read_csv(
            ARCHIVO,
            low_memory=False
        )["water_level"],
        errors="coerce"
    )

    valores_menos_uno = (
        nivel_original == -1
    ).sum()

    valores_cero = (
        nivel_original == 0
    ).sum()

    print(
        f"Valores -1 en archivo: "
        f"{valores_menos_uno:,}"
    )

    print(
        f"Valores 0 en archivo:  "
        f"{valores_cero:,}"
    )

    nivel_valido = nivel[
        nivel > 0
    ]

    print(
        f"Valores válidos durante running: "
        f"{len(nivel_valido):,}"
    )

    if len(nivel_valido) > 0:

        print(
            f"Mínimo:   "
            f"{nivel_valido.min():.3f}"
        )

        print(
            f"Máximo:   "
            f"{nivel_valido.max():.3f}"
        )

        print(
            f"Promedio: "
            f"{nivel_valido.mean():.3f}"
        )

        print(
            f"Mediana:  "
            f"{nivel_valido.median():.3f}"
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

print("\n" + "=" * 80)
print("AUDITORÍA DEL VPD")
print("=" * 80)

def calculate_vpd_auditoria(temp_c, rh_percent):
    es = 0.6108 * np.exp(
        (17.27 * temp_c) /
        (temp_c + 237.3)
    )
    ea = es * (rh_percent / 100.0)
    return es - ea


if all(
    c in df_run.columns
    for c in [
        "vpd_kpa",
        "hum_in",
        "temp_in"
    ]
):

    vpd_original = pd.to_numeric(
        df_run["vpd_kpa"],
        errors="coerce"
    )

    hum = pd.to_numeric(
        df_run["hum_in"],
        errors="coerce"
    )

    temp = pd.to_numeric(
        df_run["temp_in"],
        errors="coerce"
    )

    # --------------------------------------------------------
    # VPD registrado por el sistema
    # --------------------------------------------------------

    print("\n--- VPD REGISTRADO ---")

    print(
        f"Válidos:   "
        f"{vpd_original.notna().sum():,}"
    )

    print(
        f"Mínimo:    "
        f"{vpd_original.min():.3f} kPa"
    )

    print(
        f"Máximo:    "
        f"{vpd_original.max():.3f} kPa"
    )

    print(
        f"Promedio:  "
        f"{vpd_original.mean():.3f} kPa"
    )

    print(
        f"Mediana:   "
        f"{vpd_original.median():.3f} kPa"
    )

    # --------------------------------------------------------
    # VPD recalculado usando temp_in + hum_in
    # --------------------------------------------------------

    valido = (
        temp.notna() &
        hum.notna()
    )

    vpd_recalculado = pd.Series(
        np.nan,
        index=df_run.index
    )

    vpd_recalculado.loc[valido] = (
        calculate_vpd_auditoria(
            temp.loc[valido],
            hum.loc[valido]
        )
    )

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
    # VPD excluyendo RH >100 %
    # --------------------------------------------------------

    valido_fisico = (
        valido &
        (hum >= 0) &
        (hum <= 100)
    )

    vpd_fisico = vpd_recalculado[
        valido_fisico
    ]

    print(
        "\n--- VPD CON HUMEDAD <=100 % ---"
    )

    print(
        f"Válidos:   "
        f"{vpd_fisico.notna().sum():,}"
    )

    print(
        f"Mínimo:    "
        f"{vpd_fisico.min():.3f} kPa"
    )

    print(
        f"Máximo:    "
        f"{vpd_fisico.max():.3f} kPa"
    )

    print(
        f"Promedio:  "
        f"{vpd_fisico.mean():.3f} kPa"
    )

    print(
        f"Mediana:   "
        f"{vpd_fisico.median():.3f} kPa"
    )

    # --------------------------------------------------------
    # Diferencia entre VPD registrado y recalculado
    # --------------------------------------------------------

    diferencia = (
        vpd_original -
        vpd_recalculado
    ).abs()

    print(
        "\n--- DIFERENCIA ENTRE VPD REGISTRADO "
        "Y RECALCULADO ---"
    )

    print(
        f"Máxima diferencia: "
        f"{diferencia.max():.6f} kPa"
    )

    print(
        f"Diferencia promedio: "
        f"{diferencia.mean():.6f} kPa"
    )

else:

    print(
        "\nNo se encuentran todas las columnas "
        "necesarias para auditar el VPD."
    )


# ============================================================
# DÍAS DEL CULTIVO
# ============================================================

if "day" in df_run.columns:

    print(
        "\n--- REGISTROS POR DÍA DE CULTIVO ---"
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

df_drying = df_drying.sort_values(
    "time"
).reset_index(drop=True)

print("\n" + "=" * 80)
print("ETAPA DE SECADO")
print("=" * 80)

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

else:

    print(
        "\nNo se encontraron registros "
        "de la etapa de secado."
    )


# ============================================================
# VERIFICACIÓN DEL FINAL DEL CICLO
# ============================================================

print("\n" + "=" * 80)
print("VERIFICACIÓN DEL FINAL DEL CICLO")
print("=" * 80)

print(
    f"Último registro del archivo: "
    f"{df['time'].max()}"
)

print(
    f"Fin de running definido:     "
    f"{FIN_RUNNING}"
)

print(
    f"Fin del secado definido:      "
    f"{FIN_SECADO}"
)

if df["time"].max() < FIN_RUNNING:

    diferencia = (
        FIN_RUNNING -
        df["time"].max()
    ).total_seconds()

    print(
        "\nAVISO: el archivo no contiene "
        "registros hasta el final definido "
        "del estado running."
    )

    print(
        "Tiempo sin registros hasta "
        "el final de running: "
        f"{formato_tiempo(diferencia)}"
    )

else:

    print(
        "\nOK: existen registros hasta "
        "el final del período running."
    )


# ============================================================
# RIEGOS AUTOMÁTICOS PROGRAMADOS
# ============================================================

riego = df_run.copy()

# Convertir estados booleanos
if "irrigation_active" in riego.columns:

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

if "emergency_irrigation_event" in riego.columns:

    riego["emergency_irrigation_event"] = (
        riego["emergency_irrigation_event"]
        .astype(str)
        .str.lower()
        .isin([
            "true",
            "1",
            "1.0"
        ])
    )

# ------------------------------------------------------------
# Excluir emergencia
# ------------------------------------------------------------

if "emergency_irrigation_event" in riego.columns:

    riego = riego[
        ~riego["emergency_irrigation_event"]
    ].copy()

# ------------------------------------------------------------
# Solo riego automático real
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


# ============================================================
# OBTENER DURACIÓN PROGRAMADA
# ============================================================

def obtener_duracion(row):

    try:

        duraciones = [
            float(x.strip())
            for x in str(
                row["duration_per_day"]
            ).split(",")
        ]

        dia = int(row["day"])

        if (
            1 <= dia <= len(duraciones)
        ):

            return duraciones[
                dia - 1
            ]

    except Exception:

        pass

    return np.nan


eventos["duracion_programada_s"] = (
    eventos.apply(
        obtener_duracion,
        axis=1
    )
)

eventos["fecha_hora"] = pd.to_datetime(
    eventos["time"]
)


# ============================================================
# MOSTRAR RIEGOS
# ============================================================

print("\n" + "=" * 100)
print("RIEGOS AUTOMÁTICOS PROGRAMADOS")
print("=" * 100)

print(
    "Total de eventos:",
    len(eventos)
)

columnas_mostrar = [
    "fecha_hora",
    "day",
    "duracion_programada_s",
    "hum_in",
    "temp_in",
    "roof_fan",
    "side_fan",
    "irrigation_mode"
]

columnas_mostrar = [
    c for c in columnas_mostrar
    if c in eventos.columns
]

if len(eventos) > 0:

    print(
        eventos[
            columnas_mostrar
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

resultados_riego = []

for _, evento in eventos.iterrows():

    inicio = evento["fecha_hora"]

    # Ventana de análisis: 30 minutos
    fin = (
        inicio +
        pd.Timedelta(minutes=30)
    )

    respuesta = datos[
        (datos["fecha_hora"] >= inicio) &
        (datos["fecha_hora"] <= fin)
    ].copy()

    if respuesta.empty:
        continue

    # --------------------------------------------------------
    # LIMPIEZA DE VARIABLES
    # --------------------------------------------------------

    respuesta["hum_in"] = pd.to_numeric(
        respuesta["hum_in"],
        errors="coerce"
    )

    respuesta["temp_in"] = pd.to_numeric(
        respuesta["temp_in"],
        errors="coerce"
    )

    # --------------------------------------------------------
    # HUMEDAD
    # --------------------------------------------------------

    respuesta_hum = respuesta[
        respuesta["hum_in"].notna()
    ].copy()

    if respuesta_hum.empty:
        continue

    humedad_inicial = pd.to_numeric(
        evento["hum_in"],
        errors="coerce"
    )

    if pd.isna(humedad_inicial):
        continue

    # Máximo posterior de humedad
    idx_max = respuesta_hum[
        "hum_in"
    ].idxmax()

    humedad_max = respuesta_hum.loc[
        idx_max,
        "hum_in"
    ]

    hora_max = respuesta_hum.loc[
        idx_max,
        "fecha_hora"
    ]

    tiempo_max_s = (
        hora_max -
        inicio
    ).total_seconds()

    incremento_humedad = (
        humedad_max -
        humedad_inicial
    )

    # --------------------------------------------------------
    # TEMPERATURA
    # --------------------------------------------------------

    respuesta_temp = respuesta[
        respuesta["temp_in"].notna()
    ].copy()

    temperatura_inicial = pd.to_numeric(
        evento["temp_in"],
        errors="coerce"
    )

    if not respuesta_temp.empty and not pd.isna(
        temperatura_inicial
    ):

        # Mínima temperatura dentro de los 30 min
        idx_temp_min = respuesta_temp[
            "temp_in"
        ].idxmin()

        temperatura_minima = respuesta_temp.loc[
            idx_temp_min,
            "temp_in"
        ]

        hora_temp_min = respuesta_temp.loc[
            idx_temp_min,
            "fecha_hora"
        ]

        tiempo_temp_min_s = (
            hora_temp_min -
            inicio
        ).total_seconds()

        descenso_temperatura = (
            temperatura_inicial -
            temperatura_minima
        )

    else:

        temperatura_minima = np.nan
        hora_temp_min = pd.NaT
        tiempo_temp_min_s = np.nan
        descenso_temperatura = np.nan

    # --------------------------------------------------------
    # RECUPERACIÓN <=85 %
    # --------------------------------------------------------

    if humedad_max > 85:

        posterior_max = respuesta_hum[
            respuesta_hum["fecha_hora"] > hora_max
        ]

        recuperacion = posterior_max[
            posterior_max["hum_in"] <= 85
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
                hora_max
            ).total_seconds()

        else:

            hora_rec = pd.NaT
            humedad_rec = np.nan
            tiempo_rec_s = np.nan

    else:

        hora_rec = pd.NaT
        humedad_rec = np.nan
        tiempo_rec_s = np.nan

    # --------------------------------------------------------
    # GUARDAR RESULTADOS DEL RIEGO
    # --------------------------------------------------------

    resultados_riego.append({

        "fecha_hora": inicio,

        "day": evento["day"],

        "duracion_s":
            evento[
                "duracion_programada_s"
            ],

        # HUMEDAD
        "humedad_inicial":
            humedad_inicial,

        "humedad_maxima":
            humedad_max,

        "incremento_humedad":
            incremento_humedad,

        "tiempo_max_s":
            tiempo_max_s,

        "humedad_recuperacion":
            humedad_rec,

        "tiempo_recuperacion_s":
            tiempo_rec_s,

        # TEMPERATURA
        "temperatura_inicial":
            temperatura_inicial,

        "temperatura_minima":
            temperatura_minima,

        "descenso_temperatura":
            descenso_temperatura,

        "tiempo_temp_min_s":
            tiempo_temp_min_s,

        # VENTILACIÓN
        "roof_fan":
            evento.get(
                "roof_fan",
                np.nan
            ),

        "side_fan":
            evento.get(
                "side_fan",
                np.nan
            )
    })


# ============================================================
# TABLA FINAL
# ============================================================

resultados_riego = pd.DataFrame(
    resultados_riego
)

print("\n" + "=" * 110)
print(
    "RESPUESTA DE HUMEDAD Y TEMPERATURA "
    "DESPUÉS DE LOS RIEGOS"
)
print("=" * 110)

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
# TABLA FINAL
# ============================================================

resultados_riego = pd.DataFrame(
    resultados_riego
)

print("\n" + "=" * 110)
print("RESPUESTA DE HUMEDAD DESPUÉS DE LOS RIEGOS")
print("=" * 110)

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
# RESUMEN DE RECUPERACIÓN
# ============================================================

total = len(
    resultados_riego
)

if total > 0:

    # Eventos que superaron el umbral de 85 %
    eventos_superaron_85 = resultados_riego[
        resultados_riego[
            "humedad_maxima"
        ] > 85
    ]

    # Eventos que superaron 85 % y posteriormente
    # retornaron a <=85 %
    con_recuperacion = resultados_riego[
        resultados_riego[
            "tiempo_recuperacion_s"
        ].notna()
    ]

    # Eventos que superaron 85 % pero no retornaron
    # a <=85 % dentro de los 30 minutos
    sin_recuperacion = eventos_superaron_85[
        eventos_superaron_85[
            "tiempo_recuperacion_s"
        ].isna()
    ]

    # Eventos cuya humedad máxima no superó 85 %
    no_requirio_recuperacion = resultados_riego[
        resultados_riego[
            "humedad_maxima"
        ] <= 85
    ]

else:

    con_recuperacion = pd.DataFrame()
    sin_recuperacion = pd.DataFrame()
    no_requirio_recuperacion = pd.DataFrame()


print("\n" + "=" * 80)
print("RESUMEN DE RECUPERACIÓN DE HUMEDAD")
print("=" * 80)

print(
    "Total de riegos:",
    total
)

print(
    "Eventos que superaron 85%:",
    len(eventos_superaron_85)
    if total > 0 else 0
)

print(
    "Con recuperación <=85%:",
    len(con_recuperacion)
)

print(
    "Sin recuperación <=85% en 30 min:",
    len(sin_recuperacion)
)

print(
    "No requirieron recuperación:",
    len(no_requirio_recuperacion)
)


if total > 0:

    print(
        "Porcentaje con recuperación:",
        round(
            len(con_recuperacion)
            / total * 100,
            2
        ),
        "%"
    )

    print(
        "Porcentaje sin recuperación:",
        round(
            len(sin_recuperacion)
            / total * 100,
            2
        ),
        "%"
    )

    print(
        "Porcentaje sin superar 85%:",
        round(
            len(no_requirio_recuperacion)
            / total * 100,
            2
        ),
        "%"
    )


if len(con_recuperacion) > 0:

    print(
        "Tiempo promedio de recuperación:",
        round(
            con_recuperacion[
                "tiempo_recuperacion_s"
            ].mean(),
            1
        ),
        "s"
    )

    print(
        "Tiempo mínimo:",
        round(
            con_recuperacion[
                "tiempo_recuperacion_s"
            ].min(),
            1
        ),
        "s"
    )

    print(
        "Tiempo máximo:",
        round(
            con_recuperacion[
                "tiempo_recuperacion_s"
            ].max(),
            1
        ),
        "s"
    )

    print(
        "Incremento promedio de humedad:",
        round(
            resultados_riego[
                "incremento_humedad"
            ].mean(),
            2
        ),
        "puntos porcentuales"
    )

# ============================================================
# DISTRIBUCIÓN DEL TIEMPO DE RECUPERACIÓN
# ============================================================

if len(con_recuperacion) > 0:

    tiempos = (
        con_recuperacion[
            "tiempo_recuperacion_s"
        ]
        .dropna()
    )

    print("\n" + "=" * 80)
    print("DISTRIBUCIÓN DEL TIEMPO DE RECUPERACIÓN")
    print("=" * 80)

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


# ============================================================
# RETORNO A HUMEDAD INICIAL
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
            pd.Timedelta(minutes=30)
        )

        respuesta = datos[
            (datos["fecha_hora"] >= inicio) &
            (datos["fecha_hora"] <= fin)
        ].copy()

        respuesta["hum_in"] = pd.to_numeric(
            respuesta["hum_in"],
            errors="coerce"
        )

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
            posterior_max["hum_in"]
            <= humedad_inicial
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
# RESUMEN DE LOS DOS INDICADORES
# ============================================================

print("\n" + "=" * 90)
print("COMPARACIÓN DE TIEMPOS DE RECUPERACIÓN")
print("=" * 90)

print(
    "Riegos analizados:",
    len(resultados_riego)
)

if len(resultados_riego) > 0:

    print(
        "Retorno a <=85%:",
        resultados_riego[
            "tiempo_recuperacion_s"
        ].notna().sum()
    )

    print(
        "Retorno a humedad inicial:",
        resultados_riego[
            "tiempo_retorno_inicial_s"
        ].notna().sum()
    )


    print("\n--- Retorno a <=85% ---")

    tiempos_rango = (
        resultados_riego[
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


    print("\n--- Retorno a humedad inicial ---")

    tiempos_inicial = (
        resultados_riego[
            "tiempo_retorno_inicial_s"
        ]
        .dropna()
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
# CONDICIONES EXTERIORES
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

    ambiente["fecha_hora"] = pd.to_datetime(
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
            ambiente["fecha_hora"] <= inicio
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
                anterior.get(
                    "hum_out",
                    np.nan
                ),

            "temperatura_externa_pre":
                anterior.get(
                    "temp_out",
                    np.nan
                )
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
    # CLASIFICAR RECUPERACIÓN
    # ========================================================

    resultados_ambiente[
        "recuperacion"
    ] = np.where(

        resultados_ambiente[
            "humedad_maxima"
        ] <= 85,

        "No requirió recuperación",

        np.where(

            resultados_ambiente[
                "tiempo_recuperacion_s"
            ].notna(),

            "Recuperó ≤85%",

            "No recuperó ≤85% en 30 min"
        )
    )


    # ========================================================
    # CLASIFICAR TIEMPO DE RECUPERACIÓN
    # ========================================================

    def clasificar_tiempo(t):

        if pd.isna(t):

            return "Sin recuperación"

        if t <= 60:

            return "≤ 1 min"

        elif t <= 300:

            return "1–5 min"

        elif t <= 600:

            return "5–10 min"

        else:

            return "> 10 min"


    resultados_ambiente[
        "grupo_tiempo"
    ] = (
        resultados_ambiente[
            "tiempo_recuperacion_s"
        ]
        .apply(
            clasificar_tiempo
        )
    )


    # ========================================================
    # EVENTOS SIN RECUPERACIÓN
    # ========================================================
    sin_recuperacion = resultados_ambiente[
        (resultados_ambiente["humedad_maxima"] > 85)
        & (resultados_ambiente["tiempo_recuperacion_s"].isna())
    ].copy()

    n_sin = len(
        sin_recuperacion
    )

    print("\n" + "=" * 100)
    print(
        f"{n_sin} EVENTOS SIN RETORNO A <=85% EN 30 MIN"
    )
    print("=" * 100)

    if n_sin > 0:
        columnas_sin = [
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

        columnas_sin = [
            c for c in columnas_sin
            if c in sin_recuperacion.columns
        ]  

        print(
        sin_recuperacion[
            columnas_sin
             ]
        .to_string(index=False)
        ) 
    # ========================================================
    # COMPARACIÓN DE LAS TRES CONDICIONES
    # ========================================================

    print("\n" + "=" * 100)
    print(
        "CONDICIONES AMBIENTALES SEGÚN RESPUESTA DE HUMEDAD"
    )
    print("=" * 100)

    columnas_comparacion = [
        "humedad_externa_pre",
        "temperatura_externa_pre",
        "humedad_inicial",
        "humedad_maxima",
        "duracion_s"
    ]

    columnas_comparacion = [
        c for c in columnas_comparacion
        if c in resultados_ambiente.columns
    ]

    comparacion = (
        resultados_ambiente
        .groupby("recuperacion")[
            columnas_comparacion
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
        comparacion.to_string()
    )


    # ========================================================
    # REVISIÓN DE EVENTOS SIN RECUPERACIÓN
    # ========================================================

    columnas_revision = [
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

    columnas_revision = [
        c for c in columnas_revision
        if c in sin_recuperacion.columns
    ]

    revision = (
        sin_recuperacion[
            columnas_revision
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


    if len(revision) > 0:

        revision[
            "humedad_exterior_grupo"
        ] = (
            revision[
                "humedad_externa_pre"
            ]
            .apply(
                clasificar_humedad_exterior
            )
        )

        revision = revision.sort_values(
            "fecha_hora"
        )


    print("\n" + "=" * 110)
    print(
        f"{n_sin} EVENTOS SIN RETORNO A <=85% EN 30 MIN"
    )
    print("=" * 110)

    if len(revision) > 0:

        print(
            revision.to_string(
                index=False
            )
        )


    # ========================================================
    # DISTRIBUCIÓN HUMEDAD EXTERIOR
    # ========================================================

    print("\n" + "=" * 110)
    print(
        "DISTRIBUCIÓN DE LOS EVENTOS SIN RECUPERACIÓN"
        " SEGÚN HUMEDAD EXTERIOR"
    )
    print("=" * 110)

    if len(revision) > 0:

        print(
            revision[
                "humedad_exterior_grupo"
            ]
            .value_counts()
        )


    # ========================================================
    # EVENTOS POR DÍA
    # ========================================================

    print("\n" + "=" * 110)
    print(
        "EVENTOS SIN RECUPERACIÓN POR DÍA"
    )
    print("=" * 110)

    if len(revision) > 0:

        print(
            revision[
                [
                    "day",
                    "fecha_hora",
                    "humedad_externa_pre",
                    "humedad_inicial",
                    "humedad_maxima"
                ]
            ]
            .to_string(
                index=False
            )
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

    print("\n" + "=" * 80)
    print(
        "DURACIÓN DE LOS RIEGOS AUTOMÁTICOS"
    )
    print("=" * 80)

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
# DESCENSO DE TEMPERATURA POR RIEGO
# ============================================================

if len(resultados_riego) > 0:

    descensos = (
        resultados_riego[
            "descenso_temperatura"
        ]
        .dropna()
    )

    print("\n" + "=" * 80)
    print(
        "DESCENSO DE TEMPERATURA DESPUÉS DE LOS RIEGOS"
    )
    print("=" * 80)

    print(
        "Riegos analizados:",
        len(descensos)
    )

    if len(descensos) > 0:

        print(
            "Descenso promedio:",
            round(
                descensos.mean(),
                3
            ),
            "°C"
        )

        print(
            "Mediana:",
            round(
                descensos.median(),
                3
            ),
            "°C"
        )

        print(
            "Mínimo:",
            round(
                descensos.min(),
                3
            ),
            "°C"
        )

        print(
            "Máximo:",
            round(
                descensos.max(),
                3
            ),
            "°C"
        )

        print(
            "Percentil 25:",
            round(
                descensos.quantile(0.25),
                3
            ),
            "°C"
        )

        print(
            "Percentil 75:",
            round(
                descensos.quantile(0.75),
                3
            ),
            "°C"
        )

        tiempos_temp = (
            resultados_riego[
                "tiempo_temp_min_s"
            ]
            .dropna()
        )

        if len(tiempos_temp) > 0:

            print(
                "Tiempo promedio hasta "
                "temperatura mínima:",
                round(
                    tiempos_temp.mean(),
                    1
                ),
                "s"
            )

            print(
                "Tiempo mediano hasta "
                "temperatura mínima:",
                round(
                    tiempos_temp.median(),
                    1
                ),
                "s"
            )



# ============================================================
# RESUMEN FINAL DE PÉRDIDA DE DATOS
# ============================================================

print("\n" + "=" * 80)
print("RESUMEN DE CONTINUIDAD DEL CICLO")
print("=" * 80)

print(
    f"Inicio definido: "
    f"{INICIO_CULTIVO}"
)

print(
    f"Fin de running definido: "
    f"{FIN_RUNNING}"
)

print(
    f"Fin de secado definido: "
    f"{FIN_SECADO}"
)

print(
    f"Último registro disponible: "
    f"{df['time'].max()}"
)

print(
    f"Interrupciones internas >10 min: "
    f"{len(interrupciones):,}"
)

if len(interrupciones) > 0:

    print(
        "Tiempo acumulado de interrupciones: "
        f"{formato_tiempo(interrupciones['duracion_s'].sum())}"
    )

    print(
        "Mayor interrupción: "
        f"{formato_tiempo(interrupciones['duracion_s'].max())}"
    )


# ============================================================
# FINAL
# ============================================================

print("\n")
print("=" * 80)
print("ANÁLISIS TERMINADO")
print("=" * 80)

print("\nNOTAS:")

print(
    "1. El cumplimiento climático se evalúa "
    "únicamente durante los registros en estado "
    "running y utilizando intervalos de hasta "
    "10 minutos."
)

print(
    "2. Los intervalos superiores a 10 minutos "
    "se reportan como interrupciones y no se "
    "contabilizan como tiempo ambiental evaluable."
)

print(
    "3. Los valores 0 de temperatura y humedad "
    "se consideran datos inválidos para las "
    "estadísticas, pero se contabilizan como "
    "pérdida de información."
)

print(
    "4. Los valores -1 y 0 del nivel del tanque "
    "se consideran inválidos y se excluyen de "
    "las estadísticas del nivel."
)

print(
    "5. Los valores de humedad superiores a "
    "100 % se conservan y se reportan."
)

print(
    "6. Los registros anteriores al inicio "
    "definido del cultivo no participan en "
    "el análisis."
)

print(
    "7. La ausencia de registros no se atribuye "
    "automáticamente a una causa específica; "
    "las causas de las interrupciones se "
    "interpretan únicamente cuando existe "
    "evidencia adicional del evento."
)

print(
    "8. La respuesta de humedad posterior a "
    "cada riego se analiza mediante una ventana "
    "de observación de 30 minutos."
)

print(
    "9. Los eventos de emergencia y presurización "
    "no se consideran riegos automáticos "
    "programados."
)