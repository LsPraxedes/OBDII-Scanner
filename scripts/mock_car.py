import time
import random
import json
import ssl
import paho.mqtt.client as mqtt
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.config import MQTT_BROKER, MQTT_PORT, MQTT_MOCK_TOPIC, CA_CERT_PATH

MQTT_TOPIC = MQTT_MOCK_TOPIC

def generate_mock_data():
    """
    Gera dados aleatórios simulando a leitura do motor via OBD-II.
    """
    return {
        "rpm": round(random.uniform(2000, 3000)),
        "temperature": round(random.uniform(85, 105)),
        "speed": round(random.uniform(20, 120))
    }

def main():
    print("Iniciando Mock do Carro (Gerador de Telemetria via MQTTS)...")
    
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.tls_set(ca_certs=CA_CERT_PATH, tls_version=ssl.PROTOCOL_TLSv1_2)
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        print(f"Conectado ao broker MQTT em {MQTT_BROKER}:{MQTT_PORT}")
    except Exception as e:
        print(f"Erro de Conexão: O broker MQTT está rodando? Detalhe: {e}")
        return

    client.loop_start()

    try:
        while True:
            data = generate_mock_data()
            payload = json.dumps(data)
            result = client.publish(MQTT_TOPIC, payload)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"Sucesso ao publicar: {payload}")
            else:
                print(f"Erro ao publicar: Código de retorno {result.rc}")
            
            time.sleep(0.5)  # Envia dados a cada 0.5 segundos
    except KeyboardInterrupt:
        print("Finalizando mock_car.py...")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
