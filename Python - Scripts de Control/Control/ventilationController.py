#ventilationController.py
import time
from gpiozero import PWMOutputDevice, OutputDevice
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Control.statemanager import (
    get_state,
    update_state,
    update_state_batch,
    log_event
)
from Control import Sensors
from Control.Sensors import read_all
from Control.Settings import (
    PIN_FAN1, PIN_FAN2, PIN_ENABLE,
    PWM_FREQ, MAX_DUTY, MIN_DUTY
)

# === Configuración de pines ===
VENTILATION_PINS = {
    "roof": {"pwm": PIN_FAN2},  # Asumido como Extractor (flujo: FUERA)
    "side": {"pwm": PIN_FAN1}   # Asumido como Inyector (flujo: DENTRO)
}

# === Inicialización de Dispositivos gpiozero ===
enable_device = None
fan1_device = None
fan2_device = None

try:
    enable_device = OutputDevice(PIN_ENABLE, initial_value=False)
    fan1_device = PWMOutputDevice(PIN_FAN1, frequency=PWM_FREQ, initial_value=0.0)
    fan2_device = PWMOutputDevice(PIN_FAN2, frequency=PWM_FREQ, initial_value=0.0)
    CHIP = True
except Exception as e:
    print(f" Error al abrir gpiochip: {e}")
    CHIP = None


# Función auxiliar para hardware de PWM inverso (movida fuera de la función)
def hw_duty(d):
    """Lógica Directa (Active HIGH): 0 es 0% y MAX_DUTY es 100%."""
    return float(max(0.0, min(float(d), float(MAX_DUTY))))


# === Setup inicial ===
def setup():
    """Configura los pines PWM y el enable general."""
    global enable_device, fan1_device, fan2_device, CHIP

    if CHIP is None:
        try:
            enable_device = OutputDevice(PIN_ENABLE, initial_value=False)
            fan1_device = PWMOutputDevice(PIN_FAN1, frequency=PWM_FREQ, initial_value=0.0)
            fan2_device = PWMOutputDevice(PIN_FAN2, frequency=PWM_FREQ, initial_value=0.0)
            CHIP = True
        except Exception as e:
            print(f" No se pudo inicializar GPIO, abortando setup: {e}")
            return

    try:
        enable_device.off()
        fan1_device.value = hw_duty(0) / 100.0
        fan2_device.value = hw_duty(0) / 100.0
    except Exception as e:
        print(f" Error configurando estados iniciales: {e}")

    log_event("ventilation", "setup", "Sistema de ventilación inicializado en modo auto")
    print(" Sistema de ventilación inicializado (modo auto).")

    state = get_state("ventilation")
    if not state.get("mode"):
        update_state("ventilation", "mode", "auto")
        update_state("ventilation", "roof_duty", 0)
        update_state("ventilation", "side_duty", 0)
        update_state("ventilation", "last_r", -1)
        update_state("ventilation", "last_s", -1)

    if "alarms" not in state:
        update_state("ventilation", "alarms", {
            "sensor_error": False,
            "overheat": False,
            "humidity_critical": False
        })


def apply_pwm_batch(targets, step=5, delay=0.05):
    """Aplica la modulación PWM a los dispositivos de gpiozero para Roof (FAN2) y Side (FAN1)."""
    global enable_device, fan1_device, fan2_device, CHIP

    if CHIP is None or fan1_device is None or fan2_device is None or enable_device is None:
        print(" CHIP no inicializado.")
        return

    # 1. Obtener valores target para ambos ventiladores (0 a 100)
    roof_duty = float(hw_duty(targets.get('roof', 0)))
    side_duty = float(hw_duty(targets.get('side', 0)))

    # 2. Habilitar PIN_ENABLE si al menos uno requiere potencia
    if roof_duty > 0.0 or side_duty > 0.0:
        enable_device.on()
        time.sleep(0.05)
        # 3. Aplicar PWM a cada GPIO correspondiente (gpiozero requiere rango 0.0 a 1.0)
        fan1_device.value = side_duty / 100.0  # GPIO 13 (Side/Inyector)
        fan2_device.value = roof_duty / 100.0  # GPIO 12 (Roof/Extractor)
    else:
        fan1_device.value = 0.0
        fan2_device.value = 0.0
        time.sleep(0.05)
        enable_device.off()

    # 4. Pausa de desacople: evita que el ciclo de I2C lea durante el ruido inductivo residual
    time.sleep(0.1)

    # 5. Actualizar persistencia de estado para telemetría y control de cambios
    int_roof = int(roof_duty)
    int_side = int(side_duty)

    update_state("ventilation", "roof_duty", int_roof)
    update_state("ventilation", "side_duty", int_side)
    update_state("ventilation", "last_r", int_roof)
    update_state("ventilation", "last_s", int_side)

    log_event("ventilation", "pwm_batch", f"Roof: {int_roof}%, Side: {int_side}%")
    print(f" PWM Aplicado -> Side (GPIO 13): {int_side}% | Roof (GPIO 12): {int_roof}%")


def disable_all():
    """Apaga ventiladores y actuadores blindando el handle de lgpio ante errores de conexión."""
    try:
        # 1. Verificación de seguridad del Handle
        if 'CHIP' in globals() and CHIP is not None:
            # 2. Apagado individual de PWMs con try-except interno
            for name, cfg in VENTILATION_PINS.items():
                try:
                    # Intentamos enviar el pulso de apagado (0% duty)
                    if cfg["pwm"] == PIN_FAN1 and fan1_device is not None:
                        fan1_device.value = hw_duty(0) / 100.0
                    elif cfg["pwm"] == PIN_FAN2 and fan2_device is not None:
                        fan2_device.value = hw_duty(0) / 100.0
                except Exception as e:
                    print(f" Error gpiozero en {name}: {e}")

            # 3. Intento de apagar el pin ENABLE
            try:
                if enable_device is not None:
                    enable_device.off()
            except:
                pass  # Si el handle murió, el pin quedará en su estado físico actual
        else:
            print(" CHIP no inicializado o handle cerrado. No se puede ejecutar limpieza física.")

    except Exception as e:
        print(f" Error inesperado en disable_all: {e}")

    finally:
        # 4. ACTUALIZACIÓN DE DATOS (Siempre se ejecuta para que el Dashboard no mienta)
        update_state("ventilation", "roof_duty", 0)
        update_state("ventilation", "side_duty", 0)
        update_state("ventilation", "last_r", 0)
        update_state("ventilation", "last_s", 0)
        log_event("ventilation", "disabled", "Ventilación apagada por seguridad")
        print(" Ventilación apagada por seguridad.")


# === Control automático ===
def control_auto(sensors=None):
    """
    Versión Estable y Directa: Controla la ventilación basándose en sensores.
    Solo aplica cambios físicos al hardware cuando la potencia calculada difiere del estado actual.
    """
    vent_state = get_state("ventilation")
    config = vent_state.get("config", {})
    alarms = vent_state.get("alarms", {})
    cycle_status = get_state("system").get("cycle_status", "running")

    # Recuperación del estado físico previo
    last_r = vent_state.get("last_r", -1)
    last_s = vent_state.get("last_s", -1)

    temp_low = config.get("temp_low", 24)
    temp_medium = config.get("temp_medium", 27)
    temp_high = config.get("temp_high", 30)

    hum_low = config.get("humidity_low", 70)
    hum_medium = config.get("humidity_medium", 78)
    hum_high = config.get("humidity_high", 85)

    delta_low_h = config.get("delta_low_h", 5)
    delta_high_h = config.get("delta_high_h", 9)

    delta_low_t = config.get("delta_low_t", 1)
    delta_high_t = config.get("delta_high_t", 3)

    try:
        data = sensors if sensors is not None else read_all()

        t_ext = data["htu21d"]["sda0_temp"]
        h_ext = data["htu21d"]["sda0_hum"]
        t_in = data["htu21d"]["sda1_temp"]
        h_in = data["htu21d"]["sda1_hum"]

        delta_t = t_in - t_ext
        delta_h = h_in - h_ext

        # ===============================================================
        # ALARMAS CRÍTICAS
        # ===============================================================

        # Tipo de condición que mantiene activa cada alarma
        temp_critical_type = vent_state.get("temp_critical_type", None)
        humidity_critical_type = vent_state.get("humidity_critical_type", None)

        alarm_changed = False

        # ===============================================================
        # RECUPERACIÓN TEMPERATURA
        # ===============================================================

        if alarms.get("overheat", False):

            # Crítica por temperatura ALTA
            if temp_critical_type == "high":
                if t_in < temp_high - 2:
                    alarms["overheat"] = False
                    temp_critical_type = None
                    alarm_changed = True

                    log_event(
                        "ventilation",
                        "overheat_restored",
                        f"Temperatura normalizada: {t_in:.1f}°C"
                    )

            # Crítica por temperatura BAJA
            elif temp_critical_type == "low":
                if t_in > temp_low:
                    alarms["overheat"] = False
                    temp_critical_type = None
                    alarm_changed = True

                    log_event(
                        "ventilation",
                        "temperature_restored",
                        f"Temperatura normalizada: {t_in:.1f}°C"
                    )

        # ===============================================================
        # RECUPERACIÓN HUMEDAD
        # ===============================================================

        if alarms.get("humidity_critical", False):

            # Crítica por humedad ALTA
            if humidity_critical_type == "high":
                if h_in < hum_high + 4:
                    alarms["humidity_critical"] = False
                    humidity_critical_type = None
                    alarm_changed = True

                    log_event(
                        "ventilation",
                        "humidity_restored",
                        f"Humedad normalizada: {h_in:.1f}%"
                    )

            # Crítica por humedad BAJA
            elif humidity_critical_type == "low":
                if h_in > hum_low +2:
                    alarms["humidity_critical"] = False
                    humidity_critical_type = None
                    alarm_changed = True

                    log_event(
                        "ventilation",
                        "humidity_restored",
                        f"Humedad normalizada: {h_in:.1f}%"
                    )

        # Guardar cambios
        if alarm_changed:
            update_state("ventilation", "alarms", alarms)
            update_state(
                "ventilation",
                "temp_critical_type",
                temp_critical_type
            )
            update_state(
                "ventilation",
                "humidity_critical_type",
                humidity_critical_type
            )

        # ===============================================================
        # DETECCIÓN DE CRÍTICOS
        # ===============================================================

        critical_high = False
        critical_low = False

        # ---------------------------------------------------------------
        # TEMPERATURA ALTA
        # > 30 °C
        # ---------------------------------------------------------------

        if t_in > temp_high:
            critical_high = True

            if not alarms.get("overheat", False):
                alarms["overheat"] = True
                temp_critical_type = "high"

                update_state("ventilation", "alarms", alarms)
                update_state(
                    "ventilation",
                    "temp_critical_type",
                    "high"
                )

                log_event(
                    "ventilation",
                    "overheat",
                    f"Temperatura crítica alta: {t_in:.1f}°C"
                )

            print(f" !!! ALERTA TEMPERATURA ALTA: {t_in:.1f}°C !!!")

        # ---------------------------------------------------------------
        # TEMPERATURA BAJA
        # < 22 °C
        # ---------------------------------------------------------------

        elif t_in < temp_low - 2:
            critical_low = True

            if not alarms.get("overheat", False):
                alarms["overheat"] = True
                temp_critical_type = "low"

                update_state("ventilation", "alarms", alarms)
                update_state(
                    "ventilation",
                    "temp_critical_type",
                    "low"
                )

                log_event(
                    "ventilation",
                    "temperature_low",
                    f"Temperatura crítica baja: {t_in:.1f}°C"
                )

            print(f" !!! ALERTA TEMPERATURA BAJA: {t_in:.1f}°C !!!")

        # ---------------------------------------------------------------
        # HUMEDAD ALTA
        # > 92 %
        # ---------------------------------------------------------------

        if h_in > hum_high + 7:
            critical_high = True

            if not alarms.get("humidity_critical", False):
                alarms["humidity_critical"] = True
                humidity_critical_type = "high"

                update_state("ventilation", "alarms", alarms)
                update_state(
                    "ventilation",
                    "humidity_critical_type",
                    "high"
                )

                log_event(
                    "ventilation",
                    "humidity_critical",
                    f"Humedad crítica alta: {h_in:.1f}%"
                )

            print(f" !!! ALERTA HUMEDAD ALTA: {h_in:.1f}% !!!")

        # ---------------------------------------------------------------
        # HUMEDAD BAJA
        # < 70 %
        # ---------------------------------------------------------------

        elif h_in < hum_low:
            critical_low = True

            if not alarms.get("humidity_critical", False):
                alarms["humidity_critical"] = True
                humidity_critical_type = "low"

                update_state("ventilation", "alarms", alarms)
                update_state(
                    "ventilation",
                    "humidity_critical_type",
                    "low"
                )

                log_event(
                    "ventilation",
                    "humidity_low",
                    f"Humedad crítica baja: {h_in:.1f}%"
                )

            print(f" !!! ALERTA HUMEDAD BAJA: {h_in:.1f}% !!!")

        # ===============================================================
        # RESPUESTA CRÍTICA
        # ===============================================================

        # CRÍTICO ALTO:
        # Sacar humedad/calor rápidamente.
        if critical_high:
            if last_r != 100 or last_s != 100:
                apply_pwm_batch({
                    "roof": 100,
                    "side": 100
                })

            update_state_batch("ventilation", {
                "gradiente": round(delta_t, 2),
                "delta_h": round(delta_h, 2),
                "temp_in": round(t_in, 2),
                "hum_in": round(h_in, 2)
            })
            return

        # CRÍTICO BAJO:
        # Proteger humedad de las bandejas y evitar enfriamiento.
        if critical_low:
            if last_r != 40 or last_s != 0:
                apply_pwm_batch({
                    "roof": 40,
                    "side": 0
                })

            update_state_batch("ventilation", {
                "gradiente": round(delta_t, 2),
                "delta_h": round(delta_h, 2),
                "temp_in": round(t_in, 2),
                "hum_in": round(h_in, 2)
            })
            return

        # Lógica de ventilación (Cálculo de Roof y Side)
        roof = 0
        side = 0

        # ---------------------------------------------------------------
        # Ventilador de Techo (Roof)
        # Humedad
        if h_in > hum_high: roof = 100
        elif h_in > hum_medium: roof = 95
        elif h_in > hum_low: roof = 85
        else: roof = 40

        # 2. EXTRACTOR (ROOF) - Ajuste por Gradiente de Humedad (Delta H)
        if delta_h >= delta_high_h:
            roof = max(roof, 100)
        elif delta_h >= delta_low_h:
            roof = max(roof, 85)

        # Temperatura
        if t_in > temp_high:
            roof = 100
        elif t_in > temp_medium:
            roof = max(roof, 90)
        elif t_in > temp_low:
            roof = max(roof, 80)

        # Diferencia de temperatura entre sensores
        if delta_t > delta_high_t:
            roof = 100
        elif delta_t > delta_low_t:
            roof = max(roof, 80)
        # -----------------------------------------------------------------

        # -----------------------------------------------------------------
        # Ventiladores laterales (Side)
        if t_in > temp_high:
            #side = 80
            side = 35
        elif t_in > temp_medium:
            #side = 60
            side = 25
        elif t_in > temp_low:
            #side = 40
            side = 20
        else:
            side = 20

        # Humedad alta: aumentar lateral solamente un poco
        if h_in > hum_high + 2:
            side = max(side, 40)
        elif h_in > hum_medium or delta_h >= delta_low_h:
            side = max(side, 25)

        # 5. PROTECCIÓN POR HUMEDAD EXTERIOR ALTA (Días lluviosos)
        if h_ext > 85:
            side = min(side, 20)  # Limita la inyección para no saturar con aire húmedo exterior
        # --------------------------------------------------------------------

        roof, side = min(100, max(0, roof)), min(100, max(0, side))

        # FILTRO DE CAMBIOS: Solo aplica PWM si el valor objetivo cambia
        if roof != last_r or side != last_s:
            apply_pwm_batch({"roof": roof, "side": side})
            print(f" AUTO [CAMBIO] | T={t_in:.1f}°C H={h_in:.1f}% | R={roof}% S={side}% | Status: {cycle_status}")
        else:
            print(f" AUTO [ESTABLE] | T={t_in:.1f}°C H={h_in:.1f}% | R={roof}% S={side}% | Status: {cycle_status}")

        # Telemetría para el Dashboard
        update_state_batch("ventilation", {
            "gradiente": round(delta_t, 2),
            "delta_h": round(delta_h, 2),
            "temp_in": round(t_in, 2),
            "hum_in": round(h_in, 2)
        })


    except Exception as e:
        print(f" Error en control_auto: {e}")
        if last_r != 80 or last_s != 20:
            apply_pwm_batch({"roof": 80, "side": 20})


# === Actualizador general ===
def update_ventilation(sensors=None):
    state = get_state("ventilation")
    cycle_status = get_state("system").get("cycle_status", "idle")
    mode = state.get("mode")
    # === ESTADO DE SENSORES HTU21D ===
    htu0_ok = Sensors._htu0_ok
    htu1_ok = Sensors._htu1_ok
    sensor_error = not (htu0_ok and htu1_ok)

    alarms = state.get("alarms", {})
    if sensor_error:
        if not alarms.get("sensor_error", False):
            alarms["sensor_error"] = True
            update_state(
                "ventilation",
                "alarms",
                alarms
            )
            log_event(
                "ventilation",
                "sensor_error",
                f"Fallo HTU21D | SDA0={'OK' if htu0_ok else 'ERROR'} | SDA1={'OK' if htu1_ok else 'ERROR'}"
            )
    else:
        if alarms.get("sensor_error", False):
            alarms["sensor_error"] = False
            update_state(
                "ventilation",
                "alarms",
                alarms
            )
            log_event(
                "ventilation",
                "sensor_restored",
                "HTU21D SDA0 y SDA1 recuperados"
            )

    # Valores objetivo (Sliders o Config)
    target_roof = state.get("roof_duty", 0)
    target_side = state.get("side_duty", 0)

    # Valores reales aplicados al hardware
    last_applied_r = state.get("last_r", -1)
    last_applied_s = state.get("last_s", -1)

    # 1. ESTADO: RUNNING (Prioridad: Control Automático)
    if cycle_status == "running":
        if mode != "auto":
            update_state("ventilation", "mode", "auto")
        control_auto(sensors)
        update_state("ventilation", "last_cycle_status", cycle_status)
        return

    # 2. ESTADO: DRYING (Prioridad: Secado Fijo)
    if cycle_status == "drying":
        if last_applied_r != 100 or last_applied_s != 30:
            apply_pwm_batch({"roof": 100, "side": 30})
        update_state("ventilation", "last_cycle_status", cycle_status)
        return

    # 3. ESTADOS DE PARADA O PAUSA: IDLE, FINISHED, PAUSED
    if cycle_status in ["idle", "finished", "paused"]:
        if mode == "auto":
            # Si recién sale de un ciclo automático a pausa/idle, apaga ventiladores por seguridad
            if last_applied_r != 0 or last_applied_s != 0:
                disable_all()
            update_state("ventilation", "mode", "manual")
        elif mode == "manual":
            # Obedece a los sliders de Node-RED solo si cambiaron respecto al valor real
            if target_roof != last_applied_r or target_side != last_applied_s:
                apply_pwm_batch({"roof": target_roof, "side": target_side})

        update_state("ventilation", "last_cycle_status", cycle_status)
        return

    # Guardar estado para la siguiente vuelta
    update_state("ventilation", "last_cycle_status", cycle_status)


# === Limpieza ===
def clear():
    """Apaga todos los ventiladores y libera el chip GPIO."""
    global CHIP, enable_device, fan1_device, fan2_device

    try:
        disable_all()
    except Exception as e:
        log_event("ventilation", "warning", f"Limpieza parcial: {e}")
        print(f" Aviso: Limpieza parcial: {e}")

    # Cerrar chip solo si sigue abierto
    try:
        if CHIP is not None:
            if fan1_device is not None:
                fan1_device.close()
                fan1_device = None
            if fan2_device is not None:
                fan2_device.close()
                fan2_device = None
            if enable_device is not None:
                enable_device.close()
                enable_device = None

            log_event("ventilation", "gpio_close", "GPIO chip cerrado correctamente")
            print(" GPIO chip cerrado correctamente.")
            CHIP = None
    except Exception:
        log_event("ventilation", "warning", "Intento de cerrar CHIP ya cerrado")
        print(" CHIP ya estaba cerrado. Ignorando.")

    log_event("ventilation", "shutdown", "Ventilación detenida correctamente")
    print(" Ventilación detenida correctamente.")