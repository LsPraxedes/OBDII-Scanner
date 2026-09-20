import streamlit as st
import pandas as pd
import requests
import time

API_URL = "http://localhost:8000/api/v1/telemetry"

st.set_page_config(
    page_title="Central de Análise Veicular Preditiva",
    page_icon="🚗",
    layout="wide"
)

st.title("Central de Análise Veicular Preditiva")
st.write("Visualização em tempo real dos dados do motor (Mock-First).")

def fetch_telemetry():
    """
    Busca os dados do backend.
    """
    try:
        response = requests.get(API_URL)
        if response.status_code == 200:
            return response.json()
    except requests.exceptions.ConnectionError:
        pass
    return []

def render_dashboard(data):
    if data:
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        st.subheader("Últimas Leituras")
        cols = st.columns(3)
        latest = df.iloc[0]
        cols[0].metric("Conta-giros", value=f"{int(latest['rpm'])} RPM", delta=f"{int(latest['rpm'] - df.iloc[1]['rpm'])} RPM")
        cols[1].metric("Temperatura", value=f"{int(latest['temperature'])} °C", delta=f"{int(latest['temperature'] - df.iloc[1]['temperature'])} °C")
        cols[2].metric("Velocidade", value=f"{int(latest['speed'])} km/h", delta=f"{int(latest['speed'] - df.iloc[1]['speed'])} km/h")
        
        st.subheader("Histórico Recente")
        
        # Gráficos separados para resolver a distorção de escala
        st.write("**Engine RPM**")
        st.line_chart(df.set_index('timestamp')['rpm'], color="#FF4B4B")
        
        st.write("**Temperatura (°C)**")
        st.line_chart(df.set_index('timestamp')['temperature'], color="#FFAA00")
        
        st.write("**Velocidade (km/h)**")
        st.line_chart(df.set_index('timestamp')['speed'], color="#0068C9")
        
        with st.expander("Ver Dados Tabulares"):
            st.dataframe(df.head(10))
    else:
        st.info("Nenhum dado recebido ainda. Ligue o mock_car.py ou verifique o FastAPI.")

st.sidebar.header("Controles")
auto_refresh = st.sidebar.checkbox("Auto-Refresh", value=True)

# Criamos um container vazio (placeholder) onde a UI será renderizada.
# Isso evita o recarregamento total da página ("flicker" e lag de 4s).
placeholder = st.empty()

if auto_refresh:
    # Usamos um loop infinito para atualizar apenas o conteúdo do container
    while True:
        data = fetch_telemetry()
        with placeholder.container():
            render_dashboard(data)
        time.sleep(0.5)  # Atualiza a cada 0.5s para bater com o gerador
else:
    data = fetch_telemetry()
    with placeholder.container():
        render_dashboard(data)
    if st.button("Atualizar Manualmente"):
        st.rerun()
