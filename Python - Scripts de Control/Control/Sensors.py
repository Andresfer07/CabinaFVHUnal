import time
import os
import glob
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#from Control.Settings import BMELEVELPRESSURE

# === VARIABLES GLOBALES ===
_sensors_ready = False
_last_good_data = None
_last_success_time = 0.0
MAX_ERROR_TIME = 5.0

# Cache DS18B20
_last_ds18b20_temp = 0.0
_last_ds18b20_read = 0.0
DS18B20_INTERVAL = 5.0
_ds18b20_ok = False
_ds18b20_initialized = False

# Estado individual de HTU21D
_htu0_ok = False
_htu1_ok = False
_htu0_last_good = None
_htu1_last_good = None

_htu0_initialized = False
_htu1_initialized = False

i2c = None
#bme280 = None
tca = None
htu_sda0 = htu_sda1 = None
device_file = None


def _init_sensors():
    """Inicializa físicamente los sensores y gestiona el bus I2C."""
    global _sensors_ready, i2c, tca, htu_sda0, htu_sda1, device_file

    if _sensors_ready:
        return

    import board
    import busio
    #import adafruit_bme280.advanced as adafruit_bme280
    import adafruit_tca9548a
    import adafruit_htu21d

    try:
        # 1. Limpiar el bus anterior si existía
        if i2c is not None:
            try:
                i2c.deinit()
            except:
                pass

        print("Inicializando bus I2C...")
        time.sleep(2)

        # 2. Crear nueva conexión I2C
        i2c = busio.I2C(board.SCL, board.SDA)

        # 3. BME280 (Sensor Externo) DESHABILITADO
        #try:
        #    bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x76)
        #    bme280.sea_level_pressure = BMELEVELPRESSURE
        #    print("BME280 OK")
        #except Exception as e:
        #    print(f"BME280 FAIL: {e}")
        #    bme280 = None

        # 4. TCA9548A + HTU21D
        try:
            tca = adafruit_tca9548a.TCA9548A(i2c)
            print("TCA9548A OK")
            print("Escaneando canales TCA...")

            for i in range(2):
                try:
                    if tca[i].try_lock():
                        print(f"Canal {i} activo")
                        print([hex(x) for x in tca[i].scan()])
                        tca[i].unlock()
                except Exception as e:
                    print(f"Error canal {i}: {e}")

            time.sleep(2)

            # Inicializar cada HTU21D de forma independiente
            htu_sda0 = None
            htu_sda1 = None

            try:
                htu_sda0 = adafruit_htu21d.HTU21D(tca[0])
                print("HTU21D SDA0 OK")
            except Exception as e:
                print(f"HTU21D SDA0 FAIL: {e}")

            time.sleep(1)

            try:
                htu_sda1 = adafruit_htu21d.HTU21D(tca[1])
                print("HTU21D SDA1 OK")
            except Exception as e:
                print(f"HTU21D SDA1 FAIL: {e}")

            if htu_sda0 is None and htu_sda1 is None:
                print("HTU21D FAIL: ambos sensores no disponibles")
            else:
                print("HTU21D inicialización individual completada")

        except Exception as e:
            print(f"HTU21D FAIL: {e}")
            htu_sda0 = htu_sda1 = None

        # 5. DS18B20
        try:
            base_dir = '/sys/bus/w1/devices/'
            folders = glob.glob(base_dir + '28*')
            device_file = folders[0] + '/w1_slave' if folders else None
        except Exception:
            device_file = None

        _sensors_ready = True

    except Exception as e:
        _sensors_ready = False
        print(f" Error físico persistente: {e}")


def read_temp_ds18b20():
    global _last_ds18b20_temp, _last_ds18b20_read
    global _ds18b20_ok, _ds18b20_initialized

    if device_file is None:
        _ds18b20_ok = False
        return None

    now = time.monotonic()

    if now - _last_ds18b20_read < DS18B20_INTERVAL:
        return _last_ds18b20_temp if _last_ds18b20_temp > 0.0 else None

    try:
        with open(device_file, 'r') as f:
            lines = f.readlines()

        if lines[0].strip().endswith('YES'):
            temp_pos = lines[1].find('t=')

            if temp_pos != -1:
                temp = float(lines[1][temp_pos+2:]) / 1000.0

                if _ds18b20_initialized and not _ds18b20_ok:
                    print("DS18B20 RECUPERADO")
                elif not _ds18b20_initialized:
                    print("DS18B20 OK")

                _last_ds18b20_temp = temp
                _last_ds18b20_read = now

                _ds18b20_ok = True
                _ds18b20_initialized = True

                return temp

        _ds18b20_ok = False

    except Exception as e:
        _ds18b20_ok = False
        print(f"DS18B20 ERROR: {e}")

    return _last_ds18b20_temp if _last_ds18b20_temp > 0.0 else None


def read_all():
    """Lee todos los sensores con recuperación individual de HTU21D."""
    global _sensors_ready, _last_good_data, _last_success_time
    global _htu0_ok, _htu1_ok
    global _htu0_last_good, _htu1_last_good
    global _htu0_initialized, _htu1_initialized
    global htu_sda0, htu_sda1

    # Si el bus está caído, intentar levantarlo
    if not _sensors_ready:
        _init_sensors()

    empty_data = {
        "htu21d": {
            "sda0_temp": 0.0,
            "sda0_hum": 0.0,
            "sda1_temp": 0.0,
            "sda1_hum": 0.0
        },
        "ds18b20": {
            "temperature": 0.0
        }
    }

    if not _sensors_ready:
        return empty_data

    try:

        # ============================================================
        # HTU21D SDA0
        # ============================================================
        sda0_temp = 0.0
        sda0_hum = 0.0

        try:
            if htu_sda0:
                sda0_temp = round(htu_sda0.temperature, 2)
                sda0_hum = round(htu_sda0.relative_humidity, 2)

                _htu0_last_good = {
                    "temperature": sda0_temp,
                    "humidity": sda0_hum
                }

                if _htu0_initialized and not _htu0_ok:
                    print("HTU21D SDA0 RECUPERADO")
                #elif not _htu0_initialized:
                #    print("HTU21D SDA0 OK")

                _htu0_ok = True
                _htu0_initialized = True

            else:
                raise Exception("sensor no inicializado")

        except Exception as e:

            _htu0_ok = False
            print(f"HTU21D SDA0 ERROR: {e}")

            # Intentar recuperar SOLO SDA0
            try:
                import adafruit_htu21d

                print("Intentando recuperar HTU21D SDA0...")
                htu_sda0 = adafruit_htu21d.HTU21D(tca[0])

                sda0_temp = round(htu_sda0.temperature, 2)
                sda0_hum = round(htu_sda0.relative_humidity, 2)

                _htu0_last_good = {
                    "temperature": sda0_temp,
                    "humidity": sda0_hum
                }

                _htu0_ok = True
                _htu0_initialized = True

                print("HTU21D SDA0 RECUPERADO")

            except Exception as recovery_error:
                _htu0_ok = False
                print(f"HTU21D SDA0 RECUPERACIÓN FALLIDA: {recovery_error}")

        # ============================================================
        # HTU21D SDA1
        # ============================================================
        sda1_temp = 0.0
        sda1_hum = 0.0

        try:
            if htu_sda1:
                sda1_temp = round(htu_sda1.temperature, 2)
                sda1_hum = round(htu_sda1.relative_humidity, 2)

                _htu1_last_good = {
                    "temperature": sda1_temp,
                    "humidity": sda1_hum
                }

                if _htu1_initialized and not _htu1_ok:
                    print("HTU21D SDA1 RECUPERADO")
                #elif not _htu1_initialized:
                #    print("HTU21D SDA1 OK")

                _htu1_ok = True
                _htu1_initialized = True

            else:
                raise Exception("sensor no inicializado")

        except Exception as e:

            _htu1_ok = False
            print(f"HTU21D SDA1 ERROR: {e}")

            # Intentar recuperar SOLO SDA1
            try:
                import adafruit_htu21d

                print("Intentando recuperar HTU21D SDA1...")
                htu_sda1 = adafruit_htu21d.HTU21D(tca[1])

                sda1_temp = round(htu_sda1.temperature, 2)
                sda1_hum = round(htu_sda1.relative_humidity, 2)

                _htu1_last_good = {
                    "temperature": sda1_temp,
                    "humidity": sda1_hum
                }

                _htu1_ok = True
                _htu1_initialized = True

                print("HTU21D SDA1 RECUPERADO")

            except Exception as recovery_error:
                _htu1_ok = False
                print(f"HTU21D SDA1 RECUPERACIÓN FALLIDA: {recovery_error}")

        # ============================================================
        # Construcción de datos
        # ============================================================
        data = {
            "htu21d": {
                "sda0_temp": sda0_temp,
                "sda0_hum": sda0_hum,
                "sda1_temp": sda1_temp,
                "sda1_hum": sda1_hum,
            },
            "ds18b20": {
                "temperature": round(read_temp_ds18b20(), 2)
                if device_file else 0.0
            }
        }

        # ============================================================
        # Validación independiente
        # ============================================================
        if _htu0_ok or _htu1_ok:
            _last_good_data = data
            _last_success_time = time.time()
            return data
        else:
            raise Exception("Ambos HTU21D sin lectura válida")

    except Exception as e:

        print(
            f"Conflicto de hardware detectado ({e}). "
            f"Liberando bus para re-intento..."
        )

        _sensors_ready = False

        time_since_last_ok = time.time() - _last_success_time

        if _last_good_data is not None and time_since_last_ok <= MAX_ERROR_TIME:

            print(
                f" Conflicto temporal ({e}). "
                f"Usando memoria "
                f"({int(time_since_last_ok)}s / {int(MAX_ERROR_TIME)}s)"
            )

            return _last_good_data

        else:

            print(
                f" Sensor desconectado por más de "
                f"{MAX_ERROR_TIME}s. Retornando 0.0..."
            )

            _last_good_data = None
            return empty_data


# Prueba directa
if __name__ == "__main__":
    while True:
        print(read_all())
        time.sleep(2)