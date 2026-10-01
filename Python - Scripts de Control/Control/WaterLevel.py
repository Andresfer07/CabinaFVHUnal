# Control/WaterLevel.py
import RPi.GPIO as GPIO
import sys
from pathlib import Path
import time
import statistics
from datetime import datetime
sys.path.append(str(Path(__file__).resolve().parent.parent))
from Control.Settings import (
    PIN_TRIGGER, PIN_ECHO,
    SAMPLES, TIME_BETWEEN, TIMEOUT,
    MIN_DIST_CM, MAX_DIST_CM, TANK_HEIGHT_CM, 
    MIN_LEVEL_SAFE
)
from Control.statemanager import log_event, update_state, get_state
from Control.Sensors import read_all

GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN_TRIGGER, GPIO.OUT)
GPIO.setup(PIN_ECHO, GPIO.IN)
GPIO.output(PIN_TRIGGER, GPIO.LOW)
# Estado del sensor HC-SR04
_waterlevel_ok = False
_waterlevel_initialized = False

def get_water_level_percent(force=False, sensors=None) -> float:
    global _waterlevel_ok, _waterlevel_initialized

    state = get_state("irrigation")
    # Evitar medir cuando el riego está activo
    cycle_status = get_state("system").get("cycle_status")

    if cycle_status in ["paused", "finished"] and not force:
        return state.get("water_level", -1)

    if state.get("irrigation_active") and not force:
        return state.get("water_level", -1)
    

    try:
        if sensors is None:
            sensors = read_all()

        htu_data = sensors.get("htu21d", {})
        temp = htu_data.get("sda0_temp")

        if not temp:
            temp = 25.0

    except:
        temp = 20.0

    readings = []
    for _ in range(SAMPLES):
        GPIO.output(PIN_TRIGGER, GPIO.LOW)
        time.sleep(0.00005)
        GPIO.output(PIN_TRIGGER, GPIO.HIGH)
        time.sleep(0.00001)
        GPIO.output(PIN_TRIGGER, GPIO.LOW)

        timeout_start = time.time()
        timeout_flag = False
        while GPIO.input(PIN_ECHO) == 0:
            if time.time() - timeout_start > TIMEOUT:
                timeout_flag = True
                break
        if timeout_flag:
            time.sleep(TIME_BETWEEN)
            continue

        pulse_start = time.time()
        while GPIO.input(PIN_ECHO) == 1:
            if time.time() - pulse_start > TIMEOUT:
                timeout_flag = True
                break
            
        if timeout_flag:
            time.sleep(TIME_BETWEEN)
            continue
    
        pulse_end = time.time()
        duration = pulse_end - pulse_start
        distance = duration * (331.3 + 0.606 * temp) * 50

        if MIN_DIST_CM <= distance <= MAX_DIST_CM:
            readings.append(distance)

        time.sleep(TIME_BETWEEN)

    if not readings:
        _waterlevel_ok = False
        if _waterlevel_initialized:
            print("HC-SR04 NIVEL ERROR")
        log_event("waterlevel", "error_no_eco", {})
        update_state("irrigation", "water_level", -1)
        return -1

    if _waterlevel_initialized and not _waterlevel_ok:
        print("HC-SR04 NIVEL RECUPERADO")
    elif not _waterlevel_initialized:
        print("HC-SR04 NIVEL OK")
    _waterlevel_ok = True
    _waterlevel_initialized = True
    median = statistics.median(readings)
    good = [x for x in readings if abs(x - median) <= 0.20 * median]

    if not good:
        avg_dist = median
    else:
        avg_dist = sum(good) / len(good)

    level_percent = max(0, min(100, (TANK_HEIGHT_CM - avg_dist) / TANK_HEIGHT_CM * 100))
    update_state("irrigation", "water_level", round(level_percent, 1))  # ← guarda automáticamente
    return round(level_percent, 1)

def is_safe_to_irrigate(reason=None) -> bool:
    irrigation_state = get_state("irrigation")
    cycle_status = get_state("system").get("cycle_status")
    
    if cycle_status in ["paused", "finished"]:
        return False
    
    if cycle_status == "idle" and reason not in ["manual", "manual_mixer"]:
        return False
    
    percent = get_water_level_percent(force=False)
   
    alarms = irrigation_state.get("alarms", {})

    # 1. ERROR DE SENSOR (Prioridad Máxima)
    if percent == -1:
        fail_count = irrigation_state.get("fail_count", 0) + 1
        update_state("irrigation", "fail_count", fail_count)

        if fail_count > 5:
            log_event("waterlevel", "sensor_falla_critica", {})
        # Si no estaba ya en error, actualizamos
        if not alarms.get("sensor_error", False) or alarms.get("tank_low", True):
            update_state("irrigation", "alarms", {
                **alarms,
                "sensor_error": True,
                "tank_low": False  # <--- IMPORTANTE: Limpiamos tanque bajo si hay error de sensor
            })
            log_event("waterlevel", "error_sensor_desconectado", {})
        return False 

    # 2. NIVEL REAL BAJO
    if percent < MIN_LEVEL_SAFE:
        if not alarms.get("tank_low", False) or alarms.get("sensor_error", True):
            update_state("irrigation", "alarms", {
                **alarms,
                "tank_low": True,
                "sensor_error": False # <--- Limpiamos error de sensor si el dato es válido pero bajo
            })
            log_event("waterlevel", "nivel_bajo", {"nivel_%": percent})
        return False

    # 3. TODO NORMAL
    if alarms.get("tank_low") or alarms.get("sensor_error"):
        update_state("irrigation", "alarms", {
            **alarms,
            "tank_low": False,
            "sensor_error": False
        })
    update_state("irrigation", "fail_count", 0)
    return True
    
def wl_clear():
    """Deja el PIN_TRIGGER en LOW (estado de reposo/inactivo del HC-SR04)."""
    try:
        GPIO.output(PIN_TRIGGER, GPIO.LOW)
    except Exception as e:
        print(f"Advertencia al limpiar PIN_TRIGGER: {e}")

# Para pruebas rápidas
if __name__ == "__main__":
    try:
        while True:
            print(f"Nivel: {get_water_level_percent()}%")
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nPrueba de WaterLevel interrumpida.")
    finally:
        GPIO.cleanup() # <--- ¡Se ejecuta SIEMPRE!