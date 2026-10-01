# Control/flowsensor.py

from gpiozero import DigitalInputDevice
from Control.Settings import PIN_YFS201, CALIBRATION_FACTOR
from Control.statemanager import update_state

# Sensor YFS201C
flow_sensor = DigitalInputDevice(
    PIN_YFS201,
    pull_up=True
)

pulse_count = 0


def _pulse_callback():
    global pulse_count
    pulse_count += 1


flow_sensor.when_activated = _pulse_callback

print("YFS201C OK")


def reset_flow():
    global pulse_count
    pulse_count = 0


def get_flow_pulses():
    return pulse_count


def calculate_flow_rate(pulses, duration):
    """
    Calcula el caudal estimado a partir de los pulsos del YFS201C.
    
    pulses: número de pulsos registrados
    duration: tiempo de medición en segundos
    
    Retorna:
        Caudal en L/min
    """
    if duration <= 0:
        return 0.0

    flow_rate = pulses / (CALIBRATION_FACTOR * duration)

    return round(flow_rate, 2)





def measure_flow(duration=3):
    reset_flow()

    import time
    time.sleep(duration)

    pulses = get_flow_pulses()

    flow_rate = calculate_flow_rate(pulses, duration)

    update_state(
        "irrigation",
        "last_flow_pulses",
        pulses
    )

    update_state(
        "irrigation",
        "flow_rate",
        flow_rate
    )

    return pulses
