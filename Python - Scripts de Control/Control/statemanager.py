#statemanager.py
import json
import os
from pathlib import Path
from datetime import datetime
from threading import Lock

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = BASE_DIR / "Data" / "State.json"
PATTERN_FILE = BASE_DIR / "Data" / "Patterns.json"
HISTORY_FILE = BASE_DIR / "Data" / "History.json"

# ------------------ ESTADO INICIAL COMPLETO ------------------
INITIAL_STATE = {
    "lighting": {
        "mode": "auto",
        "colors": [[255, 0, 0], [255, 0, 0], [255, 255, 255], [0, 0, 255], [0, 0, 255]],
        "brightness": 255,
        "pattern": "default",
        "save_as": None,
        "enabled": False,
        "schedule": {str(i): {"enabled": True if i > 4 else False} for i in range(1, 13)}
    },
    "ventilation": {
        "mode": "auto",
        "roof_duty": 0,
        "side_duty": 0,
        "current_temp": 25.0,
        "config": {
            "temp_low": 24, "temp_medium": 27, "temp_high": 30,
            "humidity_low": 70, "humidity_medium": 78, "humidity_high": 85,
            "delta_low_t": 1, "delta_high_t": 3, "delta_low_h": 5, "delta_high_h": 9
        }
    },
    "irrigation": {
        "mode": "manual",
        "pressurized_once": False,
        #"pressurize_origin": None,
        "force_off": False,
        "last_emergency": None,
        "current_day": 1,
        "water_level": 0,
        "last_programmed": None,
        "last_midnight": None,
        "remaining_seconds": 0,
        "irrigation_active": False,
        "irrigation_paused": False,
        "pump": 0,
        "valves": [0, 0],
        "mixer": 0,
        "irrigation_times": ["06:00", "07:45", "09:30", "11:15","13:00", "14:45", "16:30", "18:15"],
        "completed_today": [0] * 8,
        "duration_per_day": [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 32, 32],
        "no_flow_detected": False,
        "config": {"pressurize_time": 8.0, "temp_emergency": 30.0, "hum_emergency": 75, "time_irrigation_emergency": 8},
        "alarms": {"emergency_heat": False, "tank_low": False, "pressurize_failed": False, "power_loss": False, "sensor_error": False, "flow_error": False}
    },
    "sensors": {"last_read": datetime.now().isoformat(timespec="seconds")},
    "system": {"cycle_status": "idle", "drying_start": None, "_internal": False, "last_cycle_before_shutdown": "idle", "dirty_shutdown": False, "boot_time": None}
}

state_lock = Lock()

# ------------------ PERSISTENCIA ------------------
def save_state(state):
    with state_lock:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4, ensure_ascii=False)

def load_state():
    if not STATE_FILE.exists(): return INITIAL_STATE
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
        # Asegurar campos mínimos (Migración rápida)
        for sec in INITIAL_STATE:
            if sec not in state: state[sec] = INITIAL_STATE[sec]
            elif isinstance(INITIAL_STATE[sec], dict):
                for k, v in INITIAL_STATE[sec].items():
                    state[sec].setdefault(k, v)

        # Validación de tamaño de arrays de riego
        irr = state["irrigation"]
        if "irrigation_times" not in irr:
            irr["irrigation_times"] = INITIAL_STATE["irrigation"]["irrigation_times"]
        
        if len(irr.get("completed_today", [])) != len(irr["irrigation_times"]):
            irr["completed_today"] = [0] * len(irr["irrigation_times"])
            
        # Validación de rango de días
        max_day = len(irr.get("duration_per_day", []))
        if irr.get("current_day", 1) > max_day:
            irr["current_day"] = max_day

        # --- AÑADE ESTO ANTES DEL RETURN ---
        if not PATTERN_FILE.exists():
            load_patterns() # Forzamos la creación del Patterns.json si no existe
            
        return state
    except Exception: return INITIAL_STATE

# ------------------ CORE LOGIC (EL MOTOR) ------------------
def update_state(section, key, value):
    state = load_state()
    if section not in state: state[section] = {}
    current_val = state[section].get(key)

    # --- 1. LÓGICA DE SISTEMA (START / STOP) ---
    if section == "system" and key == "cycle_status":
        old_status = state["system"].get("cycle_status")
        
        # TRANSICIÓN A RUNNING (START)
        if value == "running":
            state["lighting"]["mode"] = "auto"
            state["ventilation"]["mode"] = "auto"
            state["irrigation"]["mode"] = "auto"
            print(">>> SISTEMA: Ciclo Iniciado. Controladores en AUTO.")

        # TRANSICIÓN A IDLE (STOP)
        if value == "idle":
            state["lighting"]["mode"] = "manual"
            state["ventilation"]["mode"] = "manual"
            state["irrigation"]["mode"] = "manual"
            _apply_safe_state(state) # Apaga hardware físicamente
            print(">>> SISTEMA: Stop Manual. Controladores en MANUAL y Hardware OFF.")

        # Validación de transición
        valid = {"idle":["running"],"running":["paused","idle", "drying"],"paused":["running","idle"],"drying":["finished", "idle"],"finished":["idle"]}
        if not state["system"].get("_internal") and value != old_status and value not in valid.get(old_status, []):
            print(f" [!] Transición inválida: {old_status} -> {value}")
            return
        state["system"]["_internal"] = False

    # --- 2. GUARDIÁN DE MODOS ---
    if key == "mode" and section in ["lighting", "ventilation", "irrigation"]:
            pass

    # --- 3. EVITAR PROCESAMIENTO REPETIDO ---
    if section != "system" and current_val == value: return

    # --- 4. ACTUALIZACIÓN ESPECÍFICA POR SECCIÓN ---
    state[section][key] = value

    if section == "lighting":
        if key == "pattern" and value:
            p = get_pattern(value)
            if p:
                state["lighting"]["colors"] = p["colors"]
                state["lighting"]["brightness"] = p.get("brightness", 255)
        elif key == "save_as" and value:
            add_pattern(value, state["lighting"].get("colors"), state["lighting"].get("brightness"))
            state["lighting"]["pattern"], state["lighting"]["save_as"] = value, None

    if section == "irrigation" and key == "irrigation_times":
        state["irrigation"]["completed_today"] = [0] * len(value)

    # --- 5. GUARDADO Y LOG ---
    save_state(state)
    log_event(section, f"update_{key}", {"new_value": value})

# ------------------ UTILIDADES ------------------
def get_state(section=None):
    s = load_state()
    return s.get(section, {}) if section else s

def _apply_safe_state(state):
    state["irrigation"].update({"pump": 0, "mixer":0, "valves": [0,0], "irrigation_active": False, "mode": "manual"})
    state["ventilation"].update({
        "roof_duty": 0, 
        "side_duty": 0, 
        "mode": "manual",
        "last_r": 0,
        "last_s": 0
    })
    state["lighting"].update({
        "enabled": False, 
        "mode": "manual",
        "last_applied": "STOP_FORCE_OFF"
    })

# ------------------ PATRONES / HISTORIAL ------------------
def get_pattern(name="default"):
    if not PATTERN_FILE.exists(): return INITIAL_STATE["lighting"]["pattern"]
    with open(PATTERN_FILE, "r") as f: return json.load(f).get(name)

def add_pattern(name, colors, brightness=255):
    p = {}
    if PATTERN_FILE.exists():
        with open(PATTERN_FILE, "r") as f: p = json.load(f)
    p[name] = {"name": name, "colors": colors, "brightness": brightness}
    with open(PATTERN_FILE, "w") as f: json.dump(p, f, indent=4)

def log_event(section, event, details=None):
    entry = {"timestamp": datetime.now().isoformat(), "section": section, "event": event, "details": details or {}}
    history = []
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r") as f: history = json.load(f)
        except: history = []
    
    if history and history[-1]["event"] == event and history[-1]["details"] == entry["details"]: return
    history.append(entry)
    with open(HISTORY_FILE, "w") as f: json.dump(history[-500:], f, indent=4)

def log_sensors(sensor_data: dict):
    """Guarda lecturas de sensores con límite de 1000 entradas."""
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "section": "sensors",
        "event": "reading",
        "details": sensor_data
    }
    try:
        history = []
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, "r") as f:
                content = f.read().strip()
                if content: history = json.loads(content)
        history.append(entry)
        with open(HISTORY_FILE, "w") as f:
            json.dump(history[-1000:], f, indent=4)
    except Exception as e:
        print(f"Error log_sensors: {e}")

def set_cycle(value):
    """Cambio de ciclo estándar."""
    update_state("system", "cycle_status", value)

def set_cycle_internal(value):
    """
    Cambio de ciclo forzado internamente (ej. de running a drying).
    Activa el flag _internal para saltar la validación de transiciones.
    """
    state = load_state()
    state["system"]["_internal"] = True
    save_state(state)
    update_state("system", "cycle_status", value)
    # ------------------ FUNCIONES DE COMPATIBILIDAD (NO BORRAR) ------------------

def get_cycle():
    """Retorna el estado actual del ciclo (usado en main2.py)."""
    return load_state().get("system", {}).get("cycle_status", "idle")

def set_cycle(value):
    """Cambio de ciclo estándar."""
    update_state("system", "cycle_status", value)

def set_cycle_internal(value):
    """Cambio de ciclo forzado internamente (ej. paso automático a drying)."""
    state = load_state()
    state["system"]["_internal"] = True
    save_state(state)
    update_state("system", "cycle_status", value)

def update_state_in_memory(state, section, key, value):
    """Actualiza un objeto state en memoria sin guardar en disco (usado en procesos rápidos)."""
    if section not in state:
        state[section] = {}
    state[section][key] = value
    return state

def update_state_batch(section, updates):
    """
    Actualiza varias claves de una sección con una sola lectura/escritura
    de State.json y un solo procesamiento del historial.
    """
    state = load_state()

    if section not in state:
        state[section] = {}

    changed = {}

    for key, value in updates.items():
        current_val = state[section].get(key)

        if current_val != value:
            state[section][key] = value
            changed[key] = value

    if not changed:
        return False

    save_state(state)

    # Registrar los cambios en memoria del historial y escribir una sola vez.
    try:
        history = []

        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                history = []

        timestamp = datetime.now().isoformat()

        for key, value in changed.items():
            entry = {
                "timestamp": timestamp,
                "section": section,
                "event": f"update_{key}",
                "details": {"new_value": value}
            }

            if (
                history
                and history[-1]["event"] == entry["event"]
                and history[-1]["details"] == entry["details"]
            ):
                continue

            history.append(entry)

        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history[-500:], f, indent=4)

    except Exception as e:
        print(f"Error guardando historial batch: {e}")

    return True

def set_state(new_state):
    """Sobrescribe el estado completo (usado para resets de sistema)."""
    save_state(new_state)

def load_patterns():
    """Carga todos los patrones disponibles. Crea uno por defecto si no existe."""
    if PATTERN_FILE.exists():
        try:
            with open(PATTERN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f" Error al leer Patterns.json: {e}")
            return {}
    else:
        # Si no existe, creamos el patrón por defecto que tenías
        default_pattern = {
            "default": {
                "name": "default",
                "colors": [[255, 0, 0], [255, 0, 0], [255, 255, 255], [0, 0, 255], [0, 0, 255]],
                "brightness": 255
            }
        }
        save_patterns(default_pattern)
        return default_pattern

def save_patterns(patterns):
    """Guarda todos los patrones en el archivo JSON."""
    PATTERN_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PATTERN_FILE, "w", encoding="utf-8") as f:
        json.dump(patterns, f, indent=4)

def list_patterns(detail=False):
    """Lista los patrones disponibles."""
    patterns = load_patterns()
    if detail:
        return {
            name: {
                "colors": d.get("colors", []), 
                "brightness": d.get("brightness", 255)
            } for name, d in patterns.items()
        }
    return list(patterns.keys())

def get_all_patterns():
    """Retorna el diccionario completo de patrones."""
    return load_patterns()

def delete_pattern(name):
    """Elimina un patrón y vuelve al default si estaba activo."""
    patterns = load_patterns()
    if name in patterns:
        del patterns[name]
        save_patterns(patterns)
        state = load_state()
        if state["lighting"].get("pattern") == name:
            state["lighting"]["pattern"] = "default"
            save_state(state)
        return True
    return False

def edit_pattern(name, colors, brightness=255):
    """Actualiza o crea un patrón."""
    patterns = load_patterns()
    patterns[name] = {"name": name, "colors": colors, "brightness": brightness}
    save_patterns(patterns)
    return True

def reset_cycle():
    state = load_state()

    current_status = state["system"].get("cycle_status")
    if current_status not in ["finished", "idle"]:
        print(f" [!] RESET BLOQUEADO: El sistema está en {current_status}")
        return False

    # --- RESET IRRIGATION ---
    default_times = INITIAL_STATE["irrigation"]["irrigation_times"]
    default_secondsirrig = INITIAL_STATE["irrigation"]["duration_per_day"]

    state["irrigation"].update({
        "current_day": 1,
        "completed_today": list(default_times),
        "duration_per_day": list(default_secondsirrig),
        "completed_today": [0] * len(default_times),
        "last_programmed": None,
        "last_midnight": datetime.now().strftime("%Y-%m-%d"),
        "last_emergency": None,
        "remaining_seconds": 0,
        "irrigation_active": False,
        "pressurized_once": False,
        "water_manual_liters": 0.0,
        "water_pressurization_liters": 0.0,
        "water_programmed_liters": 0.0,
        "water_emergency_liters": 0.0,
        "water_total_liters": 0.0,
        "water_cycle_total_liters": 0.0,  
        "force_off": False,
        "mode": "manual",
        "pump": 0,
        "valves": [0, 0],
        "mixer": 0,
        "alarms": {k: False for k in INITIAL_STATE["irrigation"]["alarms"]}
    })

    # --- RESET SYSTEM ---
    state["system"].update({
        "cycle_status": "idle",
        "drying_start": None,
        "_internal": False
    })

    # --- RESET LIGHTING ---
    state["lighting"].update({
        "mode": "manual",
        "enabled": False,
        "pattern": "default",
        "colors": INITIAL_STATE["lighting"]["colors"],
        "brightness": INITIAL_STATE["lighting"]["brightness"]
    })

    # --- RESET VENTILATION ---
    state["ventilation"].update({
        "mode": "manual",
        "roof_duty": 0,
        "side_duty": 0
    })

    _apply_safe_state(state)
    save_state(state)

    print("RESET GLOBAL COMPLETO")
    return True
