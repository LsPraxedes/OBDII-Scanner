import time
import random
import requests

API_URL = "http://localhost:8000/api/v1/telemetry"

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
    print("Iniciando Mock do Carro (Gerador de Telemetria)...")
    while True:
        data = generate_mock_data()
        try:
            response = requests.post(API_URL, json=data)
            if response.status_code == 200:
                print(f"Sucesso: {data}")
            else:
                print(f"Erro do Servidor: {response.status_code} - {response.text}")
        except requests.exceptions.ConnectionError:
            print("Erro de Conexão: O servidor FastAPI está rodando?")
        
        time.sleep(0.5)  # Envia dados a cada 0.5 segundos

if __name__ == "__main__":
    main()
