# settings.py
from pathlib import Path

# --- Rutas base ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "Data"

STATE_FILE   = DATA_DIR / "State.json"
PATTERNS_FILE = DATA_DIR / "Patterns.json"

# --- LISTADO DE PINES GPIO (NUMERACIÓN BCM) ---
LED_PIN       = 18
PIN_YFS201    = 9
PIN_FAN1      = 13
PIN_FAN2      = 12
PIN_ENABLE    = 14
I2C_SCL       = 'board.SCL'
I2C_SDA       = 'board.SDA'
PIN_DS18B20   = 4
PIN_ECHO      = 10
PIN_ECHO2     = 27
PIN_TRIGGER   = 22
PIN_TRIGGER2  = 17
PIN_EVALVE1   = 25
PIN_EVALVE2   = 16
PIN_PUMP      = 15
PIN_MIXER     = 24

# --- SENSORES ---
#BME280_ADDRESS      = 0x76
#BMELEVELPRESSURE    = 1015.0  # presión a nivel del mar de Florencia - Caquetá (Colombia)

# HC-SR04
SAMPLES        = 7         # número de mediciones por ciclo (impar para mediana)
TIME_BETWEEN   = 0.06      # tiempo entre ciclos
TIMEOUT        = 0.03      # timeout para flancos (segundos)
MIN_DIST_CM    = 2.0       # distancia mínima fiable
MAX_DIST_CM    = 400.0     # distancia máxima teórica
TANK_HEIGHT_CM = 38      # altura máxima del tanque
MIN_LEVEL_SAFE = 20        # bajo este % bloqueamos riego (seguridad bomba)


# YFS201 (sensor de flujo)
CALIBRATION_FACTOR = 7.5   # 7.5 pulsos/s ≈ 1 L/min
MIN_FLOW_PULSES = 5  # ajustar empírico
FLOW_CHECK_DELAY = 3 

# --- ACTUADORES ---

# Ventiladores
PWM_FREQ = 60  # PWM Hz
MAX_DUTY = 100    # porcentaje máximo
MIN_DUTY = 30    # porcentaje mínimo

# LEDs (NeoPixel WS2812B)
LED_COUNT      = 150    # Número total de LEDs
LED_FREQ_HZ    = 800000 # Frecuencia de la señal LED en Hz (normalmente 800 kHz)
LED_DMA        = 10     # Canal DMA para generar señal
LED_BRIGHTNESS = 255    # Brillo inicial por defecto (0-255)
LED_INVERT     = False  # True si usas un transistor NPN
LED_CHANNEL    = 0      # 1 si se usan GPIO 13, 19, 41, 45 o 53