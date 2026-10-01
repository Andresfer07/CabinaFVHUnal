#irrigationController.py
import time
from datetime import datetime, timedelta
from Control.statemanager import update_state, get_state, log_event, set_cycle_internal
from Control.WaterLevel import is_safe_to_irrigate, get_water_level_percent
from Control.flowsensor import reset_flow, get_flow_pulses, calculate_flow_rate
from Control.Settings import (
    PIN_PUMP, PIN_EVALVE1, PIN_EVALVE2, MIN_LEVEL_SAFE, MIN_FLOW_PULSES, FLOW_CHECK_DELAY, PIN_MIXER
)
import RPi.GPIO as GPIO

# --- VARIABLES PARA LÓGICA ASÍNCRONA ---
_irrigation_end_time = 0
_flow_check_time = 0
_flow_checked = False
_low_level_count = 0
_last_level_check = 0
#_mixer_start_time = None
#_mixer_end_time = None
_mixer_schedule_index = None
_mixer_manual_end_time = 0
_mixer_manual_active = False
_irrigation_active_start = 0
_irrigation_elapsed_seconds = 0
_pressurization_start_time = 0

# --- Configuración de Hardware ---
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN_PUMP, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(PIN_EVALVE1, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(PIN_EVALVE2, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(PIN_MIXER, GPIO.OUT, initial=GPIO.LOW)
#GPIO.output(PIN_PUMP, 1)
#GPIO.output(PIN_EVALVE1, 1)
#GPIO.output(PIN_EVALVE2, 1)
#GPIO.output(PIN_MIXER, 1)
GPIO.output(PIN_PUMP, 0)
GPIO.output(PIN_EVALVE1, 0)
GPIO.output(PIN_EVALVE2, 0)
GPIO.output(PIN_MIXER, 0)

def sync_completed_riego():
    """Sincroniza riegos tras reinicio."""
    try:
        state = get_state("irrigation")
        irrigation_times = state.get("irrigation_times", [])
        completed = state.get("completed_today", [0] * len(irrigation_times))
        cambio = False
        now_dt = datetime.now()

        for i, hora_riego in enumerate(irrigation_times):
            hora_dt = datetime.strptime(hora_riego, "%H:%M").replace(
                year=now_dt.year, month=now_dt.month, day=now_dt.day
            )

            if hora_dt < now_dt and completed[i] == 0:
                completed[i] = 1
                cambio = True
                log_event("irrigation", "riego_omitido_reinicio", {"hora": hora_riego})
            elif hora_dt >= now_dt and completed[i] == 1:
                completed[i] = 0
                cambio = True

        if cambio:
            update_state("irrigation", "completed_today", completed)
            update_state("irrigation", "last_midnight", now_dt.strftime("%Y-%m-%d")
        )
    except Exception as e:
        print(f"Error sincronizando riegos: {e}")

def sync_day_progress():
    """
    Recupera los días perdidos si la cabina estuvo apagada
    durante el cambio de fecha.
    """
    state = get_state("irrigation")

    last_midnight = state.get("last_midnight")

    if not last_midnight:
        update_state(
            "irrigation",
            "last_midnight",
            datetime.now().strftime("%Y-%m-%d")
        )
        return

    try:
        last_date = datetime.fromisoformat(last_midnight).date()
    except Exception:
        return

    today = datetime.now().date()

    days_passed = (today - last_date).days

    if days_passed <= 0:
        return

    current_day = state.get("current_day", 1)
    max_day = len(state.get("duration_per_day", []))

    new_day = min(current_day + days_passed, max_day)

    update_state("irrigation", "current_day", new_day)

    update_state(
        "irrigation",
        "last_midnight",
        today.isoformat()
    )

    update_state(
        "irrigation",
        "completed_today",
        [0] * len(state.get("irrigation_times", []))
    )

    log_event(
        "irrigation",
        "day_recovered_after_shutdown",
        {
            "old_day": current_day,
            "new_day": new_day,
            "days_passed": days_passed
        }
    )

def setup_irrigation():
    """Inicialización al arrancar el sistema."""
    state = get_state("irrigation")
    if "completed_today" not in state:
        times = state.get("irrigation_times", [])
        update_state("irrigation", "completed_today", [0] * len(times))
    
    sync_completed_riego()
    sync_day_progress()
    _turn_off()

    state = get_state("irrigation")
    if state.get("irrigation_active", False):
        remaining = state.get("remaining_seconds", 0)
        was_paused = state.get("irrigation_paused", False)
        if remaining > 0 and not was_paused and is_safe_to_irrigate():
            log_event("irrigation", "reanudar_riego_post_corte", {"segundos": remaining})
            alarms = state.get("alarms", {})
            update_state("irrigation", "alarms", {**alarms, "power_loss": True})
            update_state("system", "last_restart_during_irrigation", True)
            irrigate_seconds(remaining, state.get("irrigation_reason", "reanudado"))
        else:
            update_state("system", "last_restart_during_irrigation", False)
            update_state("irrigation", "irrigation_active", False)
    else:
        update_state("system", "last_restart_during_irrigation", False)

# --- Funciones de Control Físico ---

def _turn_on(reason=None):
    print(f">>> BOMBA ON | reason={reason} | mode={get_state('irrigation').get('mode')} | active={get_state('irrigation').get('irrigation_active')} | pressurized_once={get_state('irrigation').get('pressurized_once')}")
    if not is_safe_to_irrigate(reason):
        return False
    #GPIO.output(PIN_PUMP, 0)
    #GPIO.output(PIN_EVALVE1, 0)
    #GPIO.output(PIN_EVALVE2, 0)
    GPIO.output(PIN_PUMP, 1)
    GPIO.output(PIN_EVALVE1, 1)
    GPIO.output(PIN_EVALVE2, 1)
    update_state("irrigation", "pump", 1)
    update_state("irrigation", "valves", [1, 1])
    #update_state("irrigation", "pump", 0)
    #update_state("irrigation", "valves", [0, 0])
    return True

def _turn_off():
    global _irrigation_end_time, _flow_checked
    print("<<< BOMBA OFF")
    #GPIO.output(PIN_PUMP, 1)
    #GPIO.output(PIN_EVALVE1, 1)
    #GPIO.output(PIN_EVALVE2, 1)
    GPIO.output(PIN_PUMP, 0)
    GPIO.output(PIN_EVALVE1, 0)
    GPIO.output(PIN_EVALVE2, 0)
    update_state("irrigation", "pump", 0)
    update_state("irrigation", "valves", [0, 0])
    #update_state("irrigation", "pump", 1)
    #update_state("irrigation", "valves", [1, 1])
    _irrigation_end_time = 0
    _flow_checked = False

def _register_irrigation_volume():
    global _irrigation_active_start, _irrigation_elapsed_seconds

    state = get_state("irrigation")
    flow_rate = state.get("flow_rate", 0)

    if _irrigation_active_start > 0:
        _irrigation_elapsed_seconds += time.time() - _irrigation_active_start
        _irrigation_active_start = 0

    elapsed_seconds = _irrigation_elapsed_seconds
    _irrigation_elapsed_seconds = 0

    volume_liters = flow_rate * elapsed_seconds / 60

    print(f"Tiempo real de riego: {elapsed_seconds:.2f} s")
    print(f"Volumen aplicado: {volume_liters:.2f} L")

    update_state(
        "irrigation",
        "volume_liters",
        round(volume_liters, 2)
    )

    reason = state.get("irrigation_reason")

    manual_total = state.get("water_manual_liters", 0.0)
    pressurization_total = state.get("water_pressurization_liters", 0.0)
    programmed_total = state.get("water_programmed_liters", 0.0)
    emergency_total = state.get("water_emergency_liters", 0.0)

    if reason == "manual":
        manual_total += volume_liters

    elif reason == "pressurize":
        pressurization_total += volume_liters

    elif reason == "programado":
        programmed_total += volume_liters

    elif reason == "emergencia_calor":
        emergency_total += volume_liters

    # Total consumido únicamente durante AUTO
    total_auto = programmed_total + emergency_total

    # Total consumido durante todo el ciclo AUTO
    total_cycle = (
        pressurization_total
        + programmed_total
        + emergency_total
    )

    update_state(
        "irrigation",
        "water_manual_liters",
        round(manual_total, 2)
    )

    update_state(
        "irrigation",
        "water_pressurization_liters",
        round(pressurization_total, 2)
    )

    update_state(
        "irrigation",
        "water_programmed_liters",
        round(programmed_total, 2)
    )

    update_state(
        "irrigation",
        "water_emergency_liters",
        round(emergency_total, 2)
    )

    update_state(
        "irrigation",
        "water_total_auto_liters",
        round(total_auto, 2)
    )

    update_state(
        "irrigation",
        "water_cycle_total_liters",
        round(total_cycle, 2)
    )


# --- Lógica de Riego Asíncrona ---

def handle_pressurize_mode():
    global _irrigation_end_time
    global _pressurization_start_time
    global _flow_check_time
    global _flow_checked
    global _last_level_check
    global _low_level_count

    state = get_state("irrigation")
    cycle_status = get_state("system").get("cycle_status")
    now = time.time()

    # ==========================================================
    # SOLO FUNCIONA DURANTE RUNNING + MODO PRESURIZACIÓN
    # ==========================================================
    if cycle_status != "running" or state.get("mode") != "pressurize":
        return

    # Ya fue realizada
    if state.get("pressurized_once", False):
        return

    # ==========================================================
    # INICIO DE PRESURIZACIÓN
    # ==========================================================
    if _irrigation_end_time == 0:

        config = state.get("config", {})
        pressurize_time = config.get("pressurize_time", 10)

        print(">>> INTENTO PRESURIZACIÓN")

        if not _turn_on("pressurize"):

            _pressurization_start_time = 0

            alarms = state.get("alarms", {})

            update_state(
                "irrigation",
                "alarms",
                {
                    **alarms,
                    "pressurize_failed": True
                }
            )

            update_state(
                "irrigation",
                "pressurized_once",
                False
            )

            update_state(
                "irrigation",
                "irrigation_active",
                False
            )

            update_state(
                "irrigation",
                "remaining_seconds",
                0
            )

            set_cycle_internal("paused")
            return

        # Reiniciar medición de flujo
        reset_flow()

        # Temporizador de presurización
        _irrigation_end_time = now + pressurize_time

        # Inicio real de consumo
        _pressurization_start_time = now

        # Preparar comprobación de flujo
        _flow_check_time = now + FLOW_CHECK_DELAY
        _flow_checked = False

        # Preparar comprobación de nivel
        _last_level_check = now
        _low_level_count = 0

        update_state(
            "irrigation",
            "irrigation_active",
            True
        )

        update_state(
            "irrigation",
            "remaining_seconds",
            pressurize_time
        )

        return

    # ==========================================================
    # VERIFICACIÓN DE FLUJO DURANTE PRESURIZACIÓN
    # ==========================================================
    if not _flow_checked and now >= _flow_check_time:

        pulses = get_flow_pulses()

        print(f"YFS201C PRESURIZACIÓN: {pulses} pulsos")

        flow_rate = calculate_flow_rate(
            pulses,
            FLOW_CHECK_DELAY
        )

        print(
            f"Caudal presurización: "
            f"{flow_rate} L/min"
        )

        update_state(
            "irrigation",
            "flow_rate",
            flow_rate
        )

        if pulses < MIN_FLOW_PULSES:

            print("!!! FALLA DE FLUJO EN PRESURIZACIÓN")

            _turn_off()

            _irrigation_end_time = 0

            _pressurization_start_time = 0

            update_state(
                "irrigation",
                "irrigation_active",
                False
            )

            update_state(
                "irrigation",
                "remaining_seconds",
                0
            )

            alarms = get_state("irrigation").get(
                "alarms",
                {}
            )

            update_state(
                "irrigation",
                "alarms",
                {
                    **alarms,
                    "pressurize_failed": True,
                    "flow_error": True
                }
            )

            update_state(
                "irrigation",
                "pressurized_once",
                False
            )

            set_cycle_internal("paused")

            log_event(
                "irrigation",
                "fallo_presurizacion_sin_flujo",
                {
                    "pulsos": pulses
                }
            )

            return

        _flow_checked = True

        alarms = get_state("irrigation").get(
            "alarms",
            {}
        )

        if alarms.get("flow_error"):
            update_state(
                "irrigation",
                "alarms",
                {
                    **alarms,
                    "flow_error": False
                }
            )

    # ==========================================================
    # VERIFICACIÓN DE NIVEL DURANTE PRESURIZACIÓN
    # ==========================================================
    if now - _last_level_check >= 10:

        level = get_water_level_percent(force=True)

        if level != -1 and level < MIN_LEVEL_SAFE:
            _low_level_count += 1
        else:
            _low_level_count = 0

        if _low_level_count >= 2:

            print("!!! TANQUE BAJO DURANTE PRESURIZACIÓN")

            _turn_off()

            _irrigation_end_time = 0
            _pressurization_start_time = 0

            update_state(
                "irrigation",
                "irrigation_active",
                False
            )

            update_state(
                "irrigation",
                "remaining_seconds",
                0
            )

            alarms = get_state("irrigation").get(
                "alarms",
                {}
            )

            update_state(
                "irrigation",
                "alarms",
                {
                    **alarms,
                    "tank_low": True,
                    "pressurize_failed": True
                }
            )

            update_state(
                "irrigation",
                "pressurized_once",
                False
            )

            set_cycle_internal("paused")

            log_event(
                "irrigation",
                "presurizacion_cancelada_tanque_bajo",
                {
                    "nivel": level
                }
            )

            return

        _last_level_check = now

    # ==========================================================
    # ACTUALIZAR TIEMPO RESTANTE
    # ==========================================================
    remaining = int(_irrigation_end_time - now)

    if remaining > 0:

        update_state(
            "irrigation",
            "remaining_seconds",
            remaining
        )

        return

    # ==========================================================
    # FIN NORMAL DE PRESURIZACIÓN
    # ==========================================================
    elapsed_seconds = 0
    volume_liters = 0.0

    if _pressurization_start_time > 0:

        elapsed_seconds = (
            now - _pressurization_start_time
        )

        flow_rate = get_state("irrigation").get(
            "flow_rate",
            0
        )

        volume_liters = (
            flow_rate * elapsed_seconds / 60
        )

        pressurization_total = (
            get_state("irrigation").get(
                "water_pressurization_liters",
                0.0
            )
            + volume_liters
        )

        programmed_total = (
            get_state("irrigation").get(
                "water_programmed_liters",
                0.0
            )
        )

        emergency_total = (
            get_state("irrigation").get(
                "water_emergency_liters",
                0.0
            )
        )

        total_auto = (
            programmed_total +
            emergency_total
        )

        total_cycle = (
            pressurization_total +
            programmed_total +
            emergency_total
        )

        update_state(
            "irrigation",
            "water_pressurization_liters",
            round(pressurization_total, 2)
        )

        update_state(
            "irrigation",
            "water_total_auto_liters",
            round(total_auto, 2)
        )

        update_state(
            "irrigation",
            "water_cycle_total_liters",
            round(total_cycle, 2)
        )

        print(
            f"Tiempo real de presurización: "
            f"{elapsed_seconds:.2f} s"
        )

        print(
            f"Volumen de presurización: "
            f"{volume_liters:.2f} L"
        )

    # ==========================================================
    # FINALIZAR
    # ==========================================================
    _pressurization_start_time = 0

    print("<<< FIN PRESURIZACIÓN")

    _turn_off()

    _irrigation_end_time = 0
    _flow_checked = False

    update_state(
        "irrigation",
        "irrigation_active",
        False
    )

    update_state(
        "irrigation",
        "remaining_seconds",
        0
    )

    update_state(
        "irrigation",
        "pressurized_once",
        True
    )

    update_state(
        "irrigation",
        "mode",
        "auto"
    )

    alarms = get_state("irrigation").get(
        "alarms",
        {}
    )

    update_state(
        "irrigation",
        "alarms",
        {
            **alarms,
            "pressurize_failed": False
        }
    )

    log_event(
        "irrigation",
        "fin_presurizacion",
        {
            "duracion": round(elapsed_seconds, 2),
            "volumen": round(volume_liters, 2)
        }
    )

def retry_pressurization():
    """
    Reintenta la presurización automática después de una falla.

    El ciclo continúa desde PAUSED, no se reinicia.
    """

    global _irrigation_end_time, _flow_checked

    state = get_state("irrigation")
    system = get_state("system")

    # ==========================================================
    # 1. VALIDACIONES
    # ==========================================================

    if system.get("cycle_status") != "paused":
        return False

    alarms = state.get("alarms", {})

    if not alarms.get("pressurize_failed", False):
        return False

    if state.get("irrigation_active", False):
        return False

    # ==========================================================
    # 2. LIMPIAR ESTADO DEL INTENTO ANTERIOR
    # ==========================================================

    _irrigation_end_time = 0
    _flow_checked = False

    update_state(
        "irrigation",
        "irrigation_active",
        False
    )

    update_state(
        "irrigation",
        "remaining_seconds",
        0
    )

    update_state(
        "irrigation",
        "pressurized_once",
        False
    )

    # ==========================================================
    # 3. LIMPIAR SOLAMENTE LA ALARMA DE PRESURIZACIÓN
    # ==========================================================

    update_state(
        "irrigation",
        "alarms",
        {
            **alarms,
            "pressurize_failed": False
        }
    )

    # ==========================================================
    # 4. VOLVER A RUNNING
    # ==========================================================
    #
    # IMPORTANTE:
    # statemanager pone automáticamente irrigation.mode = "auto"
    # cuando cycle_status pasa a running.
    #
    set_cycle_internal("running")

    # ==========================================================
    # 5. DESPUÉS DE RUNNING → PREPARAR PRESURIZACIÓN
    # ==========================================================

    update_state(
        "irrigation",
        "mode",
        "pressurize"
    )

    log_event(
        "irrigation",
        "retry_presurizacion",
        {
            "origen": "falla_presurizacion"
        }
    )

    return True


def irrigate_seconds(seconds: int, reason: str = "programado"):
    global _irrigation_end_time, _flow_check_time, _flow_checked, _irrigation_active_start, _irrigation_elapsed_seconds
    state = get_state("irrigation")
    
    if state.get("force_off", False) and reason != "manual":
        return False
    print(f">>> INTENTO RIEGO | reason={reason} | seconds={seconds}")
    if _turn_on(reason):
        reset_flow()
        _irrigation_end_time = time.time() + seconds
        _irrigation_active_start = time.time()
        _irrigation_elapsed_seconds = 0
        _flow_check_time = time.time() + FLOW_CHECK_DELAY
        _flow_checked = False
        
        update_state("irrigation", "irrigation_active", True)
        update_state("irrigation", "remaining_seconds", seconds)
        update_state("irrigation", "irrigation_duration", seconds)
        update_state("irrigation", "irrigation_reason", reason)
        
        if reason == "emergencia_calor":
            alarms = state.get("alarms", {})
            update_state("irrigation", "alarms", {**alarms, "emergency_heat": True})
        
        log_event("irrigation", "inicio_riego", {"duracion": seconds, "razon": reason})
        return True
    
    log_event("irrigation", "riego_cancelado_tanque_vacio", {})
    return False

def _pause_irrigation():
    global _irrigation_end_time, _flow_checked, _irrigation_active_start, _irrigation_elapsed_seconds

    if _irrigation_end_time == 0:
        return

    remaining = max(0, int(_irrigation_end_time - time.time()))

    if _irrigation_active_start > 0:
        _irrigation_elapsed_seconds += time.time() - _irrigation_active_start
        _irrigation_active_start = 0

    #GPIO.output(PIN_PUMP, 1)
    #GPIO.output(PIN_EVALVE1, 1)
    #GPIO.output(PIN_EVALVE2, 1)
    GPIO.output(PIN_PUMP, 0)
    GPIO.output(PIN_EVALVE1, 0)
    GPIO.output(PIN_EVALVE2, 0)

    update_state("irrigation", "pump", 0)
    update_state("irrigation", "valves", [0, 0])
    #update_state("irrigation", "pump", 1)
    #update_state("irrigation", "valves", [1, 1])
    update_state("irrigation", "remaining_seconds", remaining)
    update_state("irrigation", "irrigation_paused", True)

    _irrigation_end_time = 0
    _flow_checked = False

def _resume_paused_irrigation():
    global _irrigation_end_time, _flow_check_time, _flow_checked, _irrigation_active_start

    state = get_state("irrigation")

    remaining = state.get("remaining_seconds", 0)

    if not state.get("irrigation_active"):
        return False

    if remaining <= 0:
        return False

    reason = state.get("irrigation_reason", "reanudar")

    if not _turn_on(reason):
        log_event(
            "irrigation",
            "reanudacion_fallida",
            {"segundos": remaining}
        )
        return False

    _irrigation_end_time = time.time() + remaining
    _flow_check_time = time.time() + FLOW_CHECK_DELAY
    _irrigation_active_start = time.time()
    _flow_checked = False

    update_state("irrigation", "irrigation_paused", False)

    log_event(
        "irrigation",
        "riego_reanudado",
        {"segundos": remaining}
    )

    return True

def update_active_irrigation():
    """Se encarga de monitorear el riego en curso sin bloquear."""
    global _irrigation_end_time
    global _flow_check_time
    global _flow_checked
    global _low_level_count
    global _last_level_check
    global _irrigation_active_start
    global _irrigation_elapsed_seconds

    state = get_state("irrigation")
    cycle_status = get_state("system").get("cycle_status")
    now = time.time()

    # ==========================================================
    # LA PRESURIZACIÓN TIENE SU PROPIO CONTROLADOR
    # ==========================================================
    if state.get("mode") == "pressurize":
        return

    # ==========================================================
    # 1. REANUDAR RIEGO DESPUÉS DE PAUSA
    # ==========================================================
    if cycle_status == "running" and _irrigation_end_time == 0:

        if (
            state.get("irrigation_active")
            and state.get("remaining_seconds", 0) > 0
        ):
            _resume_paused_irrigation()
            return

    # ==========================================================
    # 2. SI NO HAY RIEGO, NO HACER NADA
    # ==========================================================
    if (
        not state.get("irrigation_active")
        or _irrigation_end_time == 0
    ):
        return

    # ==========================================================
    # 3. PAUSA
    # ==========================================================
    if cycle_status == "paused":

        _pause_irrigation()

        log_event(
            "irrigation",
            "paused_during_irrigation",
            {}
        )

        return

    # ==========================================================
    # 4. VERIFICACIÓN DE FLUJO
    # ==========================================================
    if not _flow_checked and now >= _flow_check_time:

        pulses = get_flow_pulses()

        print(f"YFS201C: {pulses} pulsos")

        flow_rate = calculate_flow_rate(
            pulses,
            FLOW_CHECK_DELAY
        )

        print(
            f"Caudal estimado: "
            f"{flow_rate} L/min"
        )

        update_state(
            "irrigation",
            "flow_rate",
            flow_rate
        )

        if pulses < MIN_FLOW_PULSES:

            _register_irrigation_volume()

            _turn_off()

            update_state(
                "irrigation",
                "irrigation_active",
                False
            )

            alarms = get_state("irrigation").get(
                "alarms",
                {}
            )

            update_state(
                "irrigation",
                "alarms",
                {
                    **alarms,
                    "flow_error": True
                }
            )

            log_event(
                "irrigation",
                "fallo_sin_flujo",
                {
                    "pulsos": pulses
                }
            )

            return

        else:

            _flow_checked = True

            alarms = get_state("irrigation").get(
                "alarms",
                {}
            )

            if alarms.get("flow_error"):

                update_state(
                    "irrigation",
                    "alarms",
                    {
                        **alarms,
                        "flow_error": False
                    }
                )

    # ==========================================================
    # 5. VERIFICACIÓN DE NIVEL CRÍTICO
    # ==========================================================
    if now - _last_level_check > 10:

        level = get_water_level_percent(force=True)

        if level != -1 and level < MIN_LEVEL_SAFE:
            _low_level_count += 1
        else:
            _low_level_count = 0

        if _low_level_count >= 2:

            _register_irrigation_volume()

            _turn_off()

            update_state(
                "irrigation",
                "irrigation_active",
                False
            )

            log_event(
                "irrigation",
                "corte_por_tanque_vacio_durante_riego",
                {
                    "nivel": level
                }
            )

            return

        _last_level_check = now

    # ==========================================================
    # 6. FINALIZACIÓN DEL RIEGO NORMAL
    # ==========================================================
    remaining = int(
        _irrigation_end_time - now
    )

    if remaining <= 0:

        _finish_irrigation()

    else:

        update_state(
            "irrigation",
            "remaining_seconds",
            remaining
        )

def _finish_irrigation():
    global _irrigation_active_start, _irrigation_elapsed_seconds
    state = get_state("irrigation")
    _register_irrigation_volume()
    _turn_off()
    update_state("irrigation", "irrigation_active", False)
    update_state("irrigation", "remaining_seconds", 0)
    update_state("irrigation", "irrigation_paused", False)

    update_state("system", "last_restart_during_irrigation", False)
    
    state = get_state("irrigation")
    log_event("irrigation", "fin_riego", {"razon": state.get("irrigation_reason")})
    
    alarms = state.get("alarms", {})
    new_alarms = {**alarms}
    new_alarms["emergency_heat"] = False
    new_alarms["power_loss"] = False
    update_state("irrigation", "alarms", new_alarms)
    update_state("irrigation", "irrigation_reason", None)

def get_duration_today() -> int:
    irrigation = get_state("irrigation")
    day = irrigation.get("current_day", 1)
    durations = irrigation.get("duration_per_day", [8])
    return durations[min(day - 1, len(durations) - 1)]

def emergency_irrigation_if_needed():
    state = get_state("irrigation")
    cycle_status = get_state("system").get("cycle_status")
    
    if cycle_status != "running" or state.get("force_off") or state.get("irrigation_active"):
        return

    if not state.get("pressurized_once", False):
        return
    
    last = state.get("last_emergency")
    if last and (datetime.now() - datetime.fromisoformat(last)) < timedelta(hours=1, minutes=30):
        return
    
    # Bloqueo si hubo riego reciente
    last_prog = state.get("last_programmed")
    if last_prog:
        try:
            if datetime.now() - datetime.fromisoformat(last_prog) < timedelta(minutes=15):
                return
        except: pass

    from Control.Sensors import read_all
    data = read_all()
    temp_in = (data["htu21d"]["sda1_temp"])
    #temp_in = (data["htu21d"]["sda0_temp"] + data["htu21d"]["sda1_temp"]) / 2
    config = state["config"]

    if temp_in >= config["temp_emergency"]:
        duration = get_duration_today()
        irrigate_seconds(min(config["time_irrigation_emergency"], duration), "emergencia_calor")
        update_state("irrigation", "last_emergency", datetime.now().isoformat())


def update_mixer():
    global _mixer_schedule_index, _mixer_manual_end_time, _mixer_manual_active#, _mixer_start_time, _mixer_end_time,

    state = get_state("irrigation")
    cycle_status = get_state("system").get("cycle_status")

    # ==========================================================
    # 1. MEZCLADOR MANUAL
    # ==========================================================
    if _mixer_manual_active:

        if time.time() >= _mixer_manual_end_time:
            #GPIO.output(PIN_MIXER, 1)
            GPIO.output(PIN_MIXER, 0)
            update_state("irrigation", "mixer", 0)
            _mixer_manual_active = False
            _mixer_manual_end_time = 0

            log_event(
                "irrigation",
                "mezclador_manual_fin",
                {}
            )
            
        else:
            # Mantener mezclador encendido
            #GPIO.output(PIN_MIXER, 0)
            GPIO.output(PIN_MIXER, 1)
            update_state("irrigation", "mixer", 1)
        return
    
    # ==========================================================
    # 2. BLOQUEOS GENERALES
    # ==========================================================

    if cycle_status != "running" or state.get("force_off"):
        #GPIO.output(PIN_MIXER, 1)
        GPIO.output(PIN_MIXER, 0)
        update_state("irrigation", "mixer", 0)
        #_mixer_start_time = None
        #_mixer_end_time = None
        _mixer_schedule_index = None
        return

    # ==========================================================
    # 3. MEZCLADO AUTOMÁTICO ANTES DEL RIEGO
    # ==========================================================

    now = datetime.now()
    irrigation_times = state.get("irrigation_times", [])

    for idx, scheduled in enumerate(irrigation_times):
        try:
            scheduled_dt = datetime.strptime(scheduled, "%H:%M").replace(
                year=now.year,
                month=now.month,
                day=now.day
            )
        except Exception:
            continue

        mixer_start = scheduled_dt - timedelta(minutes=8)
        mixer_end = mixer_start + timedelta(minutes=7.2)

        if mixer_start <= now < mixer_end:
            if _mixer_schedule_index != idx:
                print(f" MEZCLADOR ON → riego {scheduled}")
                _mixer_schedule_index = idx

            #GPIO.output(PIN_MIXER, 0)
            GPIO.output(PIN_MIXER, 1)
            update_state("irrigation", "mixer", 1)
            return
    # ==========================================================
    # Fuera de cualquier ventana de mezclado
    # ==========================================================

    #GPIO.output(PIN_MIXER, 1)
    GPIO.output(PIN_MIXER, 0)
    update_state("irrigation", "mixer", 0)
    #_mixer_start_time = None
    #_mixer_end_time = None

def run_scheduler():
    system_state = get_state("system")
    cycle_status = system_state.get("cycle_status")
    
    # Procesar tareas asíncronas
    handle_pressurize_mode()
    update_active_irrigation()
    update_mixer()
    
    state = get_state("irrigation")

    if cycle_status == "running" and not state.get("pressurized_once", False):
        update_state("irrigation", "mode", "pressurize")
        return

    if cycle_status == "paused":
        _turn_off()
        return

    if cycle_status == "drying":
        start = system_state.get("drying_start")
        if start:
            elapsed = datetime.now() - datetime.fromisoformat(start)
            if elapsed.total_seconds() > 2 * 3600:
                set_cycle_internal("finished")
                log_event("irrigation", "drying_completed", {})
        return

    if cycle_status != "running" or state.get("mode") != "auto" or state.get("force_off"):
        return

    # Lógica de tiempos programados
    now_dt = datetime.now()
    irrigation_times = state.get("irrigation_times", [])
    completed_today = state.get("completed_today", [0] * len(irrigation_times))

    for idx, scheduled in enumerate(irrigation_times):
        scheduled_dt = datetime.strptime(scheduled, "%H:%M").replace(
            year=now_dt.year, month=now_dt.month, day=now_dt.day
        )
        if abs((now_dt - scheduled_dt).total_seconds()) < 30 and completed_today[idx] == 0:
            if irrigate_seconds(get_duration_today(), "programado"):
                completed_today[idx] = 1
                update_state("irrigation", "completed_today", completed_today)
                update_state("irrigation", "last_programmed", now_dt.isoformat())

    # Reset de media noche
    today_str = now_dt.strftime("%Y-%m-%d")
    last_midnight = state.get("last_midnight")
    #if now_dt.hour >= 12 and last_midnight != today_str:
    if last_midnight != today_str:
        current_day = state.get("current_day", 1)
        max_day = len(state.get("duration_per_day", []))

        if current_day < max_day:
            update_state("irrigation", "current_day", current_day + 1)
            log_event("irrigation", "day_advanced",{"from": current_day, "to": current_day + 1})

        else:
            set_cycle_internal("drying")
            update_state("system", "drying_start", now_dt.isoformat())
            update_state("irrigation", "force_off", True)
            irr_clear()
        
        update_state("irrigation", "last_midnight", today_str)
        update_state("irrigation", "completed_today", [0] * len(irrigation_times))

# --- APIs Manuales ---

def manual_on(seconds: int = None):
    state = get_state("irrigation")
    if get_state("system").get("cycle_status") != "idle" or state.get("mode") != "manual":
        return False
    
    if state.get("irrigation_active") or state.get("force_off"):
        return False

    if _mixer_manual_active:
        return False

    config = state.get("config", {})
    seconds = max(1, min(int(seconds or config.get("manual_default_time", 15)), config.get("manual_max_time", 60)))
    
    log_event("irrigation", "manual_trigger", {"seconds": seconds})
    return irrigate_seconds(seconds, "manual")

def manual_off():
    global _irrigation_end_time, _flow_checked
    state = get_state("irrigation")
    if get_state("system").get("cycle_status") != "idle" or state.get("mode") != "manual":
        return False
    _turn_off()
    update_state("irrigation", "irrigation_active", False)
    update_state("irrigation", "remaining_seconds", 0)
    print("DEBUG MANUAL OFF:")
    print("  irrigation_active =", get_state("irrigation").get("irrigation_active"))
    print("  remaining_seconds =", get_state("irrigation").get("remaining_seconds"))
    print("  pump =", get_state("irrigation").get("pump"))
    print("  valves =", get_state("irrigation").get("valves"))
    print("  _irrigation_end_time =", _irrigation_end_time)
    log_event("irrigation", "apagado_manual", {})
    return True

def manual_mixer_on(secondsmixer: int = None):
    global _mixer_manual_end_time, _mixer_manual_active

    state = get_state("irrigation")
    system = get_state("system")

    # Solo permitido con sistema detenido
    if system.get("cycle_status") != "idle":
        return False

    # Solo permitido en modo manual
    if state.get("mode") != "manual":
        return False

    # Bloqueo general
    if state.get("force_off"):
        return False

    # No permitir iniciar otro mezclado si ya está activo
    if _mixer_manual_active:
        return False

    # No permitir mezclador manual mientras hay riego
    if state.get("irrigation_active"):
        return False

    # Verificar nivel del tanque
    if not is_safe_to_irrigate("manual_mixer"):
        log_event(
            "irrigation",
            "mezclador_manual_cancelado_tanque",
            {}
        )
        return False

    config = state.get("config", {})

    secondsmixer = max(
        1,
        min(
            int(secondsmixer or config.get("mixer_manual_default_time", 30)),
            config.get("mixer_manual_max_time", 300)
        )
    )

    # Activar físicamente
    #GPIO.output(PIN_MIXER, 0)
    GPIO.output(PIN_MIXER, 1)
    # Registrar estado temporal
    _mixer_manual_active = True
    _mixer_manual_end_time = time.time() + secondsmixer

    update_state("irrigation", "mixer", 1)

    log_event(
        "irrigation",
        "mezclador_manual_inicio",
        {
            "secondsmixer": secondsmixer
        }
    )

    return True

def manual_mixer_off():
    global _mixer_manual_end_time, _mixer_manual_active

    state = get_state("irrigation")
    system = get_state("system")

    if system.get("cycle_status") != "idle":
        return False

    if state.get("mode") != "manual":
        return False

    #GPIO.output(PIN_MIXER, 1)
    GPIO.output(PIN_MIXER, 0)

    _mixer_manual_active = False
    _mixer_manual_end_time = 0

    update_state("irrigation", "mixer", 0)

    log_event(
        "irrigation",
        "mezclador_manual_apagado",
        {}
    )

    return True

def force_off(enable: bool = True):
    update_state("irrigation", "force_off", enable)
    if enable: _turn_off()

def trigger_pressurize():
    update_state("irrigation", "pressurized_once", False)
    update_state("irrigation", "mode", "pressurize")

def irr_clear():
    global _mixer_manual_active, _mixer_manual_end_time
    try:
        _turn_off()
        #GPIO.output(PIN_MIXER, 1)
        GPIO.output(PIN_MIXER, 0)

        _mixer_manual_active = False
        _mixer_manual_end_time = 0
        update_state("irrigation", "mixer", 0)
    except Exception as e:
        log_event("irrigation", "clear_error", {"error": str(e)})


_last_tank_check = 0

def handle_tank_state(sensors=None):
    global _last_tank_check
    now = time.monotonic()
    if now - _last_tank_check < 10:
        return
    _last_tank_check = now
    level = get_water_level_percent(force=True, sensors=sensors)
    state = get_state("irrigation")
    cycle_status = get_state("system").get("cycle_status")
    alarms = state.get("alarms", {})

    if cycle_status == "paused":
        return

    new_alarms = {**alarms}
    if level == -1:
        new_alarms["sensor_error"] = True
    else:
        new_alarms["sensor_error"] = False
        new_alarms["tank_low"] = (level < MIN_LEVEL_SAFE)

    update_state("irrigation", "alarms", new_alarms)


if __name__ == "__main__":
    try:
        while True:
            handle_tank_state()
            run_scheduler()
            emergency_irrigation_if_needed()
            time.sleep(1) # Un solo sleep central
    except KeyboardInterrupt:
        pass
    finally:
        irr_clear()
        GPIO.cleanup()
