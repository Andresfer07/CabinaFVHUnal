# Main.py → VERSIÓN CORREGIDA - CABINA FVH 2025
import time
import json
from datetime import datetime
import paho.mqtt.client as mqtt
import numpy as np
import RPi.GPIO as GPIO
import os
import threading
import sys
import signal


# Controladores
from Control.irrigationController import (
    run_scheduler as irr_run, 
    emergency_irrigation_if_needed,     
    irr_clear,
    get_duration_today,
    setup_irrigation,
    sync_completed_riego,
    manual_on,
    manual_off,
    handle_tank_state,
    manual_mixer_on,
    manual_mixer_off,
    handle_pressurize_mode,
    retry_pressurization
)
from sdnotify import SystemdNotifier
from Control.lightingController import update_lighting
from Control.ventilationController import (
    update_ventilation, clear as vent_clear, disable_all
)
from Control import Sensors
from Control.Sensors import read_all
from Control.WaterLevel import get_water_level_percent, wl_clear
from Control.statemanager import ( 
    get_state, update_state, log_event, 
    log_sensors, get_pattern, get_cycle, 
    update_state_in_memory, get_all_patterns, 
    delete_pattern, set_state, add_pattern, reset_cycle
)
from Control.Settings import LED_BRIGHTNESS

# MQTT Setup
client = mqtt.Client(
     client_id="CabinaFVH_Main",
     callback_api_version=mqtt.CallbackAPIVersion.VERSION1
)

client.connect("localhost", 1883, 60)
client.loop_start()
notifier = SystemdNotifier()

def graceful_shutdown(signum, frame):
    print("\nSIGTERM recibido → cerrando limpio...")

    try:
        update_state("system", "dirty_shutdown", False)

        # FORZAR escritura inmediata
        state = get_state()
        set_state(state)

    except Exception as e:
        print(f"Error guardando shutdown limpio: {e}")

    try:
        irr_clear()
        disable_all()
        wl_clear()

        client.loop_stop()
        client.disconnect()

        GPIO.cleanup()

    except Exception as e:
        print(f"Error cleanup: {e}")

    print("Shutdown limpio completado.")
    os._exit(0)



def calculate_vpd(temp_c, rh_percent):
    es = 0.6108 * np.exp((17.27 * temp_c) / (temp_c + 237.3))
    ea = es * (rh_percent / 100.0)
    return round(es - ea, 3)

def is_time_in_range(start, end, now):
    if start <= end:
        return start <= now <= end
    else:
        return now >= start or now <= end

def publish_all(sensors=None):
    """Lee sensores y envía telemetría completa a Node-RED y ThingsBoard."""
    try:

        sensors = sensors if sensors is not None else read_all()
        state = get_state()
        water = state.get("irrigation", {}).get("water_level", -1)

        irrigation_state = state.get("irrigation", {})
        lighting_state = state.get("lighting", {})
        ventilation_state = state.get("ventilation", {})
        system_state = state.get("system", {})


        irrigation_alarms = irrigation_state.get("alarms", {})
        ventilation_alarms = ventilation_state.get("alarms", {})
        lighting_alarms = lighting_state.get("alarms", {})

        alarms = {
            #Irrigation
            "low_water": irrigation_alarms.get("tank_low", False),
            "pressure_fail": irrigation_alarms.get("pressurize_failed", False),
            "blocked": irrigation_state.get("force_off", False),
            "emergency_irrigation_event": irrigation_alarms.get("emergency_heat", False),
            "restart": irrigation_alarms.get("power_loss", False),
            "water_level_error": irrigation_alarms.get("sensor_error", False),
            "flow_error": irrigation_alarms.get("flow_error", False),

            #Ventilation
            "overheat": ventilation_alarms.get("overheat", False),
            "humidity_critical": ventilation_alarms.get("humidity_critical", False),
            "tempandhumid_error": ventilation_alarms.get("sensor_error", False),

            #VPD
            "temp_vpd_error": not Sensors._ds18b20_ok,

            #Lighting
            "lighting_fail": lighting_alarms.get("fail", False),
            "lighting_pattern_error": lighting_alarms.get("pattern_error", False),
            "lighting_config_error": lighting_alarms.get("config_error", False),

        }

        # Sistema normal irrigation
        irrigation_system_ok = not any([
            alarms["pressure_fail"],
            alarms["low_water"],
            alarms["blocked"],
            alarms["restart"],
            alarms["water_level_error"],
            alarms["flow_error"]
        ])

        # Clima normal ventilation
        
        climate_ok = not any ([
            alarms["overheat"],
            alarms["humidity_critical"],
            alarms["tempandhumid_error"],
        ])

        # Sistema normal Luz

        light_system_ok = not any([
            alarms["lighting_fail"],
            alarms["lighting_pattern_error"],
            alarms["lighting_config_error"],
        ])
  
        # habitat_ok REAL
        habitat_ok = irrigation_system_ok and climate_ok and light_system_ok


        #t_in = (sensors["htu21d"]["sda0_temp"] + sensors["htu21d"]["sda1_temp"]) / 2
        #h_in = (sensors["htu21d"]["sda0_hum"] + sensors["htu21d"]["sda1_hum"]) / 2
        t_in = sensors["htu21d"]["sda1_temp"]
        h_in = sensors["htu21d"]["sda1_hum"]
        t_ds = sensors["ds18b20"]["temperature"]
        t_target = t_ds if Sensors._ds18b20_ok else t_in
        vpd = calculate_vpd(t_target, h_in)

        irrigation_state = state.get("irrigation", {})
        #print(f"[VALVES STATE] {irrigation_state.get('valves')}")
        #print(f"[PUMP STATE] {irrigation_state.get('pump')}")
        #print(f"[IRRIGATION ACTIVE] {irrigation_state.get('irrigation_active')}")
        lighting_state = state.get("lighting", {})
        ventilation_state = state.get("ventilation", {})
        vent_config = ventilation_state.get("config") or {}

        payload = {
            "ts": int(time.time() * 1000),
            "values": {
                "temp_in": round(t_in, 2), 
                #"temp_out": round(sensors["bme280"]["temperature"], 2),
                "temp_out": round(sensors["htu21d"]["sda0_temp"], 2),
                "hum_in": round(h_in, 2), 
                #"hum_out": round(sensors["bme280"]["humidity"], 2),
                "hum_out": round(sensors["htu21d"]["sda0_hum"], 2),
                "vpd_kpa": vpd, 
                "water_level": water, 
                "day": irrigation_state.get("current_day", 1),
                "irrigation_mode": irrigation_state.get("mode", "manual"),
                "pump": irrigation_state.get("pump", 0),         
                "valve_1": irrigation_state.get("valves", [0,0])[0],
                "valve_2": irrigation_state.get("valves", [0,0])[1],
                "lighting_mode": lighting_state.get("mode", "auto"),
                "ventilation_mode": ventilation_state.get("mode", "auto"),
                "roof_fan": ventilation_state.get("roof_duty", 0),
                "side_fan": ventilation_state.get("side_duty", 0),
                "progreso_riego": irrigation_state.get("completed_today", []),
                "duracion_programada": get_duration_today(),
                "last_programmed": irrigation_state.get("last_programmed"),
                "last_emergency": irrigation_state.get("last_emergency"),
                "pressurized_once": irrigation_state.get("pressurized_once", False),
                "lighting_pattern": lighting_state.get("pattern") or "default",
                "remaining_seconds": irrigation_state.get("remaining_seconds", 0),
                "irrigation_active": irrigation_state.get("irrigation_active", False),
                "irrigation_times": str(",".join(irrigation_state.get("irrigation_times", []))),
                "alarm_low_water": alarms["low_water"],
                "alarm_pressure_fail": alarms["pressure_fail"],
                "alarm_blocked": alarms["blocked"],
                "emergency_irrigation_event": alarms["emergency_irrigation_event"],
                "alarm_restart": alarms["restart"],
                "alarm_system_normal": irrigation_system_ok,
                "alarm_water_level_error": alarms["water_level_error"],
                "pressurize_time": irrigation_state.get("config", {}).get("pressurize_time"),
                "temp_emergency": irrigation_state.get("config", {}).get("temp_emergency"),
                "time_irrigation_emergency": irrigation_state.get("config", {}).get("time_irrigation_emergency"),
                "lighting_colors": json.dumps(lighting_state.get("colors") or []),
                "lighting_brightness": lighting_state.get("brightness"),
                "lighting_enabled": lighting_state.get("enabled", False),
                "duration_per_day": ",".join(map(str, irrigation_state.get("duration_per_day", []))),
                "temp_low": vent_config.get("temp_low"),
                "temp_medium": vent_config.get("temp_medium"),
                "temp_high": vent_config.get("temp_high"),
                "humidity_low": vent_config.get("humidity_low"),
                "humidity_medium": vent_config.get("humidity_medium"),
                "humidity_high": vent_config.get("humidity_high"),
                "delta_low_t": vent_config.get("delta_low_t"),
                "delta_high_t": vent_config.get("delta_high_t"),
                "delta_temp": round(sensors["htu21d"]["sda1_temp"] - sensors["htu21d"]["sda0_temp"],2),
                "alarm_overheat": alarms["overheat"],
                "alarm_humidity_critical": alarms["humidity_critical"],
                "alarm_tempandhumid_error": alarms["tempandhumid_error"],
                "alarm_lighting_fail": alarms["lighting_fail"],
                "alarm_lighting_pattern_error": alarms["lighting_pattern_error"],
                "alarm_lighting_config_error": alarms["lighting_config_error"],
                "alarm_climate_ok": climate_ok,
                "alarm_light_ok": light_system_ok,
                "alarms_habitat_ok": habitat_ok,
                "lighting_schedule": json.dumps(lighting_state.get("schedule", {})),
                "flow_error": irrigation_alarms.get("flow_error", False),
                "cycle_status": system_state.get("cycle_status"),
                "mixer": irrigation_state.get("mixer", 0),
                "delta_hum" : round(sensors["htu21d"]["sda1_hum"] - sensors["htu21d"]["sda0_hum"], 2),
                "delta_low_h": vent_config.get("delta_low_h"),
                "delta_high_h": vent_config.get("delta_high_h"),
                "alarm_temp_vpd_error": alarms["temp_vpd_error"],
                "water_manual_liters": irrigation_state.get("water_manual_liters", 0.0),
                "water_pressurization_liters": irrigation_state.get("water_pressurization_liters", 0.0),
                "water_programmed_liters": irrigation_state.get("water_programmed_liters", 0.0),
                "water_emergency_liters": irrigation_state.get("water_emergency_liters", 0.0),
                "water_total_auto_liters": irrigation_state.get("water_total_auto_liters", 0.0),
                "water_cycle_total_liters": irrigation_state.get("water_cycle_total_liters", 0.0),

            }
        }
        #Modificar campos None or null
        payload["values"] = {k: v for k, v in payload["values"].items() if v is not None}

        client.publish("v1/devices/me/telemetry", json.dumps(payload))
        client.publish("cabin/telemetry", json.dumps(payload)) 
        log_sensors(sensors)
    except Exception as e:
        log_event("main", "publish_error", {"error": str(e)})


def on_message(c, u, msg):
    try:
        data = json.loads(msg.payload.decode())
        updates_applied = 0
        state = get_state()
        batch_mode = True

        # -------------------------
        # DELETE PATTERN
        # -------------------------
        if "delete_pattern" in data:

            name = data.get("delete_pattern")
            delete_pattern(name)

            #  LIMPIAR ESTADO SI ELIMINAS EL ACTIVO
            lighting_state = state.get("lighting", {})
            current_pattern = lighting_state.get("pattern")

            if current_pattern == name:
                print(f" Eliminando patrón activo '{name}' → aplicando default")

                default_pattern = get_pattern("default")

                if not default_pattern:

                    default_pattern = {"colors": [[0, 0, 0]],"brightness": 255}

                state = update_state_in_memory(state, "lighting", "pattern", "default")
                state = update_state_in_memory(state, "lighting", "colors", default_pattern.get("colors", []))
                state = update_state_in_memory(state, "lighting", "brightness", default_pattern.get("brightness", 255))
                state = update_state_in_memory(state, "lighting", "save_as", None)
            
            set_state(state)

            patterns = get_all_patterns()
            client.publish("cabin/patterns", json.dumps(patterns))
            print(f" Patrón '{name}' eliminado correctamente")
            return

        # -------------------------
        # GET ALL PATTERNS
        # -------------------------
        if "get_patterns" in data:

            patterns = get_all_patterns()
            client.publish("cabin/patterns", json.dumps(patterns))
            print(f" Enviando {len(patterns)} patrones")
            return

        # -------------------------
        # GET ONE PATTERN
        # -------------------------
        if "get_pattern" in data:

            name = data.get("get_pattern")

            if not name:
                print(" get_pattern recibió None → ignorado")
                return 

            pattern_data = get_pattern(name)

            if pattern_data:
                client.publish("cabin/pattern_data", json.dumps({
                    "name": name,
                    "colors": pattern_data.get("colors", []),
                    "brightness": pattern_data.get("brightness", 255)
                }))
            else:
                print(f" Patrón '{name}' no encontrado")

            return

        # -------------------------
        # PROCESAMIENTO GENERAL
        # -------------------------
        for section, values in data.items():

            if not isinstance(values, dict) or section not in ["irrigation", "lighting", "ventilation", "system"]:
                continue

            # =========================================
            # FINALIZACION DE CICLO Y REINICIO MANUAL
            # =========================================

            if section == "system":

                # APAGADO
                if values.get("shutdown") is True:
                    shutdown_system()
                    return

                if values.get("reset_cycle") is True:
                    print(" RESET DE CICLO SOLICITADO")
                    if reset_cycle():
                        # 1. Limpieza lógica de controladores
                        irr_clear()
                        disable_all()
                        #clear()
                        #2. Forzar actualización física inmediata
                        update_state("irrigation", "irrigation_active", False)
                        update_state("irrigation", "remaining_seconds", 0)
                        update_lighting()
                        update_ventilation()
                        #3. Informar a Node-RED del nuevo estado (idle)
                        publish_all() 
                        print(" >>> RESET EXITOSO: Hardware apagado y telemetría enviada.")
                        
                    return

                # CAMBIO DE ESTADO GLOBAL
                if "cycle_status" in values:
                    new_status = values["cycle_status"]
                    # Usamos update_state para que dispare la lógica de protección/modos
                    update_state("system", "cycle_status", new_status)
                    # Recargamos el state local para que el batch_mode no lo sobrescriba
                    state = get_state() 
                    print(f" cycle_status → {new_status} (Modos reseteados si es STOP)")
                    
            # =========================================
            #  FIX BRILLO (CRÍTICO)
            # =========================================
            if section == "lighting":

                # 1. Aplicar brightness primero SI existe
                if "brightness" in values:
                    state = update_state_in_memory(state, "lighting", "brightness", values["brightness"])
                    updates_applied += 1


                # 2. Luego procesar el resto
                for k, v in values.items():
                    
                    if k == "brightness":
                        continue
                    if v is None:
                        continue

                    if k == "schedule":
                        # LIMPIEZA AUTOMÁTICA
                        for day, cfg in v.items():
                            if cfg.get("enabled") is False:
                                cfg.pop("start", None)
                                cfg.pop("end", None)
                        state = update_state_in_memory(state, "lighting", "schedule", v)
                        print(" Schedule actualizado")
                        continue

                    if k == "enabled":
                        state = update_state_in_memory(state, "lighting", "enabled", v)
                        continue

                    if k == "colors":
                        state = update_state_in_memory(state, "lighting", "colors", v)
                        if "pattern" not in values:
                             state = update_state_in_memory(state, "lighting", "pattern", "colormanual")
                        

                    if k == "pattern":

                        if not v:
                            print(" pattern vacío → usando default")
                            v = "default"
                            
                        pattern_data = get_pattern(v)
                        
                        if not pattern_data:
                            print(f" Patrón '{v}' no existe → usando default")
                            v = "default"
                            pattern_data = get_pattern("default")

                        if not pattern_data:
                            pattern_data = {
                            "colors": [[0, 0, 0]],
                            "brightness": 255
                            }

                        update_state("lighting", "pattern", v)
                        state = get_state()
                        state = update_state_in_memory(state, "lighting", "colors", pattern_data.get("colors", []))
                        state = update_state_in_memory(state, "lighting", "brightness", pattern_data.get("brightness", 255))
                        state = update_state_in_memory(state, "lighting", "save_as", None)


                        continue

                    if k == "save_as":
                        add_pattern(v,state.get("lighting", {}).get("colors"),state.get("lighting", {}).get("brightness", 255))
                        state = update_state_in_memory(state, "lighting", "pattern", v)
                        state = update_state_in_memory(state, "lighting", "save_as", None)
                        patterns = get_all_patterns()
                        client.publish("cabin/patterns", json.dumps(patterns))
                        print(f" Patrón '{v}' guardado correctamente")
                        continue
                

                    updates_applied += 1

                continue  #  NO bajar al bloque general

            # =========================================
            # RESTO: irrigation + ventilation
            # =========================================

            if section == "irrigation":
                #Reintento de presurizacion
                    if "retry_pressurization" in values:
                            if values.get("retry_pressurization") is True:
                                    result = retry_pressurization()
                                    if result:
                                             print(" >>> REINTENTO DE PRESURIZACIÓN ACEPTADO")
                                    else:
                                            print(" >>> REINTENTO DE PRESURIZACIÓN RECHAZADO")
                            continue
                #Irrigation Manual 
                    if "manual_on" in values:
                        seconds = values.get("seconds")
                        #manual_on(seconds)
                        thread_riego = threading.Thread(target=manual_on, args=(seconds,))
                        thread_riego.start()
                        continue

                    if "manual_off" in values:
                        manual_off()
                        state = get_state()  
                        continue

                #Mezclado Manual
                    if "manual_mixer_on" in values:
                        secondsmixer = values.get("secondsmixer")
                        manual_mixer_on(secondsmixer)
                        continue

                    if "manual_mixer_off" in values:
                        manual_mixer_off()
                        continue
            
                    
            for k, v in values.items():

                if v is None:
                    continue

                # ---- IRRIGATION TIMES ----
                if section == "irrigation" and k == "irrigation_times":

                    if isinstance(v, str):
                        v = [t.strip() for t in v.split(",") if t.strip()]

                    if isinstance(v, list):
                        now_dt = datetime.now()
                        #update_state("irrigation", "irrigation_times", v)
                        state = update_state_in_memory(state, "irrigation", "irrigation_times", v)

                        new_completed = []
                        for hora_riego in v:
                            try:
                                hora_dt = datetime.strptime(hora_riego, "%H:%M").replace(
                                    year=now_dt.year,
                                    month=now_dt.month,
                                    day=now_dt.day
                                )
                                new_completed.append(1 if hora_dt < now_dt else 0)
                            except:
                                new_completed.append(0)


                        state = update_state_in_memory(state, "irrigation", "completed_today", new_completed)
                        print(" Horarios actualizados respetando riegos ya ocurridos.")
                    else:
                        print(" Formato inválido para irrigation_times")

                # ---- DURATION PER DAY ----
                elif section == "irrigation" and k == "duration_per_day":

                    if isinstance(v, str):
                        v = [int(x.strip()) for x in v.split(",") if x.strip()]

                    if isinstance(v, list):
                        state = update_state_in_memory(state, "irrigation", "duration_per_day", v)
                        print("Duration_per_day actualizado correctamente.")
                    else:
                        print("Formato inválido para duration_per_day")

                # ---- CONFIG IRRIGATION ----
                elif section == "irrigation" and k in ["pressurize_time", "temp_emergency", "time_irrigation_emergency"]:

                    irrigation_state = state.get("irrigation", {})
                    config = irrigation_state.get("config", {})
                    config[k] = v
                    state = update_state_in_memory(state, "irrigation", "config", config)

                # ---- CONFIG VENTILATION ----
                elif section == "ventilation" and k == "config":

                    vent_state = state.get("ventilation", {})
                    config = vent_state.get("config")

                    if not isinstance(config, dict):
                        config = {}

                    if isinstance(v, dict):
                        config.update(v)
                        state = update_state_in_memory(state, "ventilation", "config", config)
                        print("Ventilation config actualizado.")

                else:
                    if batch_mode:
                        state = update_state_in_memory(state, section, k, v)
                    else:
                        update_state(section, k, v)


                updates_applied += 1

        if batch_mode:
            set_state(state)

        print(f" COMANDO PROCESADO: {updates_applied} actualizaciones.")

    except Exception as e:
        print(f" ERROR MQTT: {e}")
client.on_message = on_message 
client.subscribe("cabin/command")
signal.signal(signal.SIGTERM, graceful_shutdown)
signal.signal(signal.SIGINT, graceful_shutdown)

def shutdown_system():
    print(" APAGANDO RASPBERRY PI...")
    
    try:
        irr_clear()
        disable_all()
        wl_clear()
    except Exception as e:
        print(f" Error en limpieza: {e}")

    time.sleep(2)
    os.system("sudo shutdown -h now")


def main_loop():
    synced_today = False
    last_cycle = None
    
    while True:
        notifier.notify("WATCHDOG=1")
        # 1. ACTUALIZACIÓN DE ESTADO
        state = get_state()
        if state is None: 
            time.sleep(1)
            continue
        
        # CORRECCIÓN 1: Sintaxis correcta para obtener el ciclo
        cycle = state["system"].get("cycle_status", "idle")
        
        # 2. DETECCIÓN DE CAMBIO DE ESTADO
        if cycle != last_cycle:
            print("\n==================================================")
            print(f"CABINA FVH - SISTEMA EN: {cycle.upper()}")
            print("==================================================")

            # Guardar último estado válido para autoresume
            update_state("system", "last_cycle_before_shutdown", cycle)

            if cycle in ["paused", "idle", "finished"]:
                print(" >>> MODO SEGURO: Deteniendo actuadores...")
                disable_all() # Apaga ventilación
                # manual_off() # Si tienes esta función para la bomba, actívala aquí
            
            # CORRECCIÓN 2: Limpieza física al detenerse
            if (last_cycle in ["running", "paused"]) and (cycle in ["idle", "finished"]):
                print(f" >>> STOP/FIN DETECTADO: Apagando hardware...")
                try:
                    irr_clear()
                    disable_all() 
                    wl_clear()
                    # Forzamos actualización visual inmediata de sensores apagados
                    publish_all(sensors)
                except Exception as e:
                    print(f" Aviso en limpieza: {e}")
            
            if cycle == "running" and not synced_today:
                print(" INICIANDO CICLO DE CULTIVO AUTÓNOMO")
                sync_completed_riego()
                synced_today = True
                update_state("irrigation", "pressurized_once", False)
                log_event("irrigation", "sincronizacion_post_reinicio", {})
            
            if cycle in ["idle", "finished"]:
                synced_today = False
            
            last_cycle = cycle
        
        lighting_state = state.get("lighting", {})

        # 3. LÓGICA DE AUTOMATISMO (Mantenemos toda tu lógica original de luces)
        if cycle in ["running"]:
            day = state.get("irrigation", {}).get("current_day", 1)
            max_day = len(state.get("irrigation", {}).get("duration_per_day", []))
            schedule = lighting_state.get("schedule", {})
            now_str = datetime.now().strftime("%H:%M")

            lights_enabled = False
            if schedule:
                # ... (Aquí va toda tu lógica de schedule intacta)
                day_key = str(day)
                if day_key in schedule:
                    config = schedule.get(day_key, {})
                    if config.get("enabled") is False:
                        lights_enabled = False
                    else:
                        start, end = config.get("start"), config.get("end")
                        if start and end:
                            lights_enabled = is_time_in_range(start, end, now_str)
                        else:
                            lights_enabled = True
                elif "default" in schedule:
                    config = schedule.get("default", {})
                    if config.get("enabled") is False:
                        lights_enabled = False
                    else:
                        start, end = config.get("start"), config.get("end")
                        if start and end:
                            lights_enabled = is_time_in_range(start, end, now_str)
                        else:
                            lights_enabled = True
                else:
                    if 4 <= day <= max_day:
                        lights_enabled = is_time_in_range("06:00", "23:59", now_str) if day == 4 else is_time_in_range("00:00", "23:59", now_str)
            else:
                if 4 <= day <= max_day:
                    lights_enabled = is_time_in_range("06:00", "23:59", now_str) if day == 4 else is_time_in_range("00:00", "23:59", now_str)

            if lighting_state.get("mode") == "auto":
                if lighting_state.get("enabled") != lights_enabled:
                    print(f"DEBUG-MAIN: Ajustando luz por horario -> {lights_enabled}")
                    update_state("lighting", "enabled", lights_enabled)

        elif cycle == "idle":
            # 1. Aseguramos que pase a manual si venimos de otro estado
            if lighting_state.get("mode") != "manual":
                update_state("lighting", "mode", "manual")
            # 2. SOLO forzamos el apagado si acabamos de llegar de RUNNING (el Stop)
            # Pero permitimos que el usuario la encienda después manualmente.
            if last_cycle != "idle":
                if lighting_state.get("enabled") is not False:
                    update_state("lighting", "enabled", False)

        # --- CORRECCIÓN CRÍTICA PARA PAUSA ---
        elif cycle == "paused":
            # Si el Dashboard marca ON, lo forzamos a OFF para que coincida con la realidad física
            if lighting_state.get("enabled") is not False:
                print("DEBUG-MAIN: Forzando OFF en Dashboard por PAUSA")
                update_state("lighting", "enabled", False)
        
        sensors = read_all()

        # 4. EJECUCIÓN DE CONTROLADORES
        try:
            irrigation_state = state.get("irrigation")
            system_state = state.get("system")

            if irrigation_state is not None and system_state is not None:
                handle_tank_state(sensors)
                # CORRECCIÓN 3: El scheduler de riego (irr_run) solo debe procesar 
                # si está en running o si hay un riego manual activo.
                irr_run() 

                if cycle == "paused":
                    # Aquí llamar a la función que apaga el pin de la bomba
                    # Ejemplo: GPIO.output(PIN_BOMBA, GPIO.LOW)
                    manual_off()
                    manual_mixer_off()
                    pass

                if cycle == "running" and irrigation_state.get("mode") == "auto":
                    emergency_irrigation_if_needed()
            
            ### FIX RESTART: Esto es lo que faltaba ###
            # Si venimos de PAUSA y ahora estamos en RUNNING, forzamos al 
            # lightingController a que ignore su "memoria" y aplique el patrón de nuevo.
            if last_cycle == "paused" and cycle == "running":
                update_state("lighting", "last_applied_str", "FORCE_RESTART_AFTER_PAUSE")
                if lighting_state.get("mode") == "auto":
                    update_state("lighting", "enabled", True)

            update_lighting()
            update_ventilation(sensors)
            publish_all(sensors)
            #last_cycle = cycle

        except Exception as e:
            import traceback
            print(f" Error detallado en controladores: {e}")
            traceback.print_exc()
            
        time.sleep(1) # Importante para no saturar la CPU

if __name__ == "__main__":
    try:
        print(" INICIANDO SISTEMA...")

        # Detectar apagado brusco previo
        state = get_state()

        if state["system"].get("dirty_shutdown") is True:

            print(" POWER LOSS DETECTED")
            log_event("system", "power_loss_detected", {})

            previous_cycle = state["system"].get("last_cycle_before_shutdown","idle")

            print(f" Último estado antes del corte: {previous_cycle}")

            # SOLO restaurar estados operativos
            if previous_cycle in ["running", "paused"]:

                print(f" AUTO-RESUME → restaurando {previous_cycle}")

                update_state("system","cycle_status", previous_cycle)

        # Marcar sistema como corriendo
        update_state("system", "dirty_shutdown", True)
        update_state("system", "boot_time", datetime.now().isoformat(timespec="seconds"))

        print(" Esperando estabilización I2C...")
        time.sleep(5)

        setup_irrigation()

        # Inicialización y verificación del sensor de nivel
        sensors_init = read_all()
        get_water_level_percent(force=True, sensors=sensors_init)

        notifier.notify("READY=1")
        main_loop() 
        
    except Exception as e:
        print(f" ERROR AL ARRANCAR: {e}")

    except KeyboardInterrupt:
        print("\nApagando por teclado...")

    finally:

        try:
            update_state("system", "dirty_shutdown", False)
        except:
            pass

        GPIO.cleanup()
        vent_clear()
        client.loop_stop()

        print("Sistema liberado correctamente.")
