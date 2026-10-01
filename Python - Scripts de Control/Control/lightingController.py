# control/lightingController.py
from rpi_ws281x import Adafruit_NeoPixel, Color
from Control.statemanager import get_state, get_pattern, update_state
from Control.Settings import (
    LED_COUNT, LED_PIN, LED_FREQ_HZ,
    LED_DMA, LED_BRIGHTNESS, LED_INVERT, LED_CHANNEL
)

# --- Inicialización de la tira LED ---
strip = Adafruit_NeoPixel(
    LED_COUNT, LED_PIN, LED_FREQ_HZ,
    LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL
)
strip.begin()



# --- Funciones auxiliares ---
def apply_pattern(colors, brightness):

    print(f"DEBUG-LIGHTS: >>> EJECUTANDO apply_pattern! Brillo: {brightness} | Cycle: {get_state('system').get('cycle_status')}")

    strip.setBrightness(int(brightness))

    if not colors or not isinstance(colors, (list, tuple)):
        colors = [[255, 255, 255]]

    n = strip.numPixels()

    if not isinstance(colors[0], (list, tuple)):
        colors = [colors]

    for i in range(n):
        r, g, b = colors[i % len(colors)]

        # clamp
        r = max(0, min(255, int(r)))
        g = max(0, min(255, int(g)))
        b = max(0, min(255, int(b)))

        strip.setPixelColor(i, Color(r, g, b))

    strip.show()


def clear():

    print("DEBUG-LIGHTS: --- EJECUTANDO clear() (Apagado físico) ---")

    strip.setBrightness(0)
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0,0,0))
    strip.show()


# --- Control principal ---
def update_lighting():
    state = get_state("lighting")
    cycle_status = get_state("system").get("cycle_status")
    last = state.get("last_cycle_status")
    brightness = int(state.get("brightness", LED_BRIGHTNESS))

    # --- 1. TRANSICIÓN CRÍTICA: EL BOTÓN STOP ---
    # Si acabamos de entrar en IDLE (venimos de Running, Paused o Finished)
    if cycle_status == "idle" and last != "idle":
        clear()
        update_state("lighting", "mode", "manual")   # <--- Aquí forzamos el modo manual
        update_state("lighting", "enabled", False)  # <--- Apagamos el interruptor virtual
        update_state("lighting", "last_applied", "STOP_RESET")
        update_state("lighting", "last_cycle_status", "idle")
        return # Salimos para que el apagado sea efectivo

    # --- 2. EL MURO DE PAUSA (Con rebote de switch) ---
    #if cycle_status == "paused":
    #    # Si el switch está en ON, lo forzamos a OFF (el rebote que mencionas)
    #    if state.get("enabled") is True:
    #        update_state("lighting", "enabled", False)
    #    
    #    if state.get("last_applied") != "PAUSE_OFF":
    #        clear()
    #        update_state("lighting", "last_applied", "PAUSE_OFF")
    #    
    #    update_state("lighting", "last_cycle_status", "paused")
    #    return # Bloqueo total

    # --- 2 y 3. GESTIÓN DE PAUSA (BLOQUEO TOTAL) ---
    if cycle_status == "paused":
        if last != "paused":
            print("DEBUG-LIGHTS: PAUSA DETECTADA -> APAGANDO")
            clear()
            # FIX: Apagamos el dashboard manualmente aquí
            update_state("lighting", "enabled", False)
            update_state("lighting", "last_applied", "PAUSE_OFF")
        
        update_state("lighting", "last_cycle_status", "paused")
        return

    # --- 4. BLOQUEO FINISHED (Muro de seguridad) ---
    if cycle_status == "finished":
        clear()
        update_state("lighting", "last_applied", "FINISHED_OFF")
        update_state("lighting", "last_cycle_status", "finished")
        return

    # --- 5. DETERMINAR MODO Y AUTO-CORRECCIÓN (Modificado) ---
    if cycle_status == "running":
        mode = "auto"
        # Aquí NO forzamos el enabled=True. 
        # La lógica de "qué hora es" ya la hace el Main.py y actualiza el estado.
        if state.get("mode") != "auto":
            update_state("lighting", "mode", "auto")
            state = get_state("lighting")
    elif cycle_status == "idle":
        mode = "manual"
    else:
        mode = "auto"

    # --- 6. EL INTERRUPTOR + BLOQUEO DE SEGURIDAD ---
    is_enabled = state.get("enabled", False)
    
    # Caso especial: Permitir luz en IDLE solo si es MANUAL y el switch está ON
    is_manual_idle = (cycle_status == "idle" and mode == "manual")

    # EL MURO (Si está OFF o el ciclo no es válido, apagamos y SALIMOS)
    if not is_enabled or (cycle_status not in ["running", "idle"]):
        if not is_manual_idle or not is_enabled:
            if state.get("last_applied_str") != "HARDWARE_OFF":
                clear()
                update_state("lighting", "last_applied_str", "HARDWARE_OFF")
            
            update_state("lighting", "last_cycle_status", cycle_status)
            return # <--- ESTE RETURN ES VITAL para que no llegue al apply_pattern
    
    # --- 7. EJECUCIÓN FÍSICA (Universal para Edición/Auto/Manual) ---
    if mode == "manual":
        colors = state.get("colors") or [[255, 255, 255]]
    else:
        if cycle_status == "drying":
            pattern_colors = [[255, 255, 255]]
        else:
            pattern_name = state.get("pattern") or "default"
            pattern = get_pattern(pattern_name)
            if not pattern:
                if pattern_name == "colormanual":
                    pattern = {"colors": state.get("colors") or [[255, 255, 255]]}
                else:
                    pattern = get_pattern("default") or {"colors": [[255, 255, 255]]}
            pattern_colors = pattern.get("colors", [[255, 0, 255]])
        colors = pattern_colors

    # --- EL FIX DEL BRILLO Y RESTART ---
    actual_state_str = f"{colors}_{brightness}_{state.get('enabled')}"

    # REBOTE POST-PAUSA: Si el sistema está en running y venimos de un bloqueo de pausa/hardware,
    # forzamos que actual_state_str se vea como "distinto" una sola vez.
    last_applied = state.get("last_applied")
    force_update = (cycle_status == "running" and last_applied in ["PAUSE_OFF", "HARDWARE_OFF", "STOP_RESET"])

    if actual_state_str != state.get("last_applied_str") or force_update:
        # Solo si el estado cambió O si venimos de un apagado del sistema, mandamos a los LEDs
        apply_pattern(colors, brightness)
        
        # Guardamos el nuevo estado
        update_state("lighting", "last_applied_str", actual_state_str)
        
        # Si forzamos el encendido, limpiamos el 'last_applied' para no entrar en bucle
        if force_update:
            update_state("lighting", "last_applied", "RUNNING_ON")

    # Guardamos siempre el ciclo actual para la próxima vuelta
    update_state("lighting", "last_cycle_status", cycle_status)