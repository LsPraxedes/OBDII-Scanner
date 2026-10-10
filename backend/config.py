from pathlib import Path

# Obtém o diretório raiz do projeto (uma pasta acima do backend/)
BASE_DIR = Path(__file__).resolve().parent.parent

# Configurações do MQTT
MQTT_BROKER = "test.mosquitto.org"
MQTT_PORT = 8883
MQTT_TOPIC = "ls-praxedes/scanner-obd2/+"
MQTT_MOCK_TOPIC = "ls-praxedes/scanner-obd2/qsr5c99" # Tópico que o mock usará para envio
CA_CERT_PATH = str(BASE_DIR / "mosquitto.org.crt")

# Configurações da API
API_URL = "http://localhost:8000/api/v1/telemetry"

# Configurações de Banco de Dados
DATABASE_URL = f"sqlite:///{BASE_DIR / 'vehicle_data.db'}"
TEST_DATABASE_URL = f"sqlite:///{BASE_DIR / 'test.db'}"
