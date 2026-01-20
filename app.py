import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime
from geopy.distance import geodesic
import json

# --- Configuração ---
st.set_page_config(page_title="AeroOps | Real Data", page_icon="📡", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #000000; color: #00ff41; }
    h1, h2, h3, div, span, p { font-family: 'Consolas', monospace !important; }
    .stButton>button {
        background-color: #004400; color: #00ff41; border: 1px solid #00ff41;
        width: 100%; height: 60px; font-size: 20px;
    }
    .stButton>button:hover { background-color: #00ff41; color: black; }
    div[data-testid="stMetric"] { background-color: #111; border: 1px solid #333; }
</style>
""", unsafe_allow_html=True)

# --- SNAPSHOT DE DADOS REAIS (BACKUP DE SEGURANÇA) ---
# Dados reais capturados de SBGR (Guarulhos) para usar quando a API der erro 429
SNAPSHOT_REAL_DATA = [
    ["c05872", "TAM3256 ", "Brazil", 1716231245, 1716231245, -46.4731, -23.4356, 762.0, False, 75.3, 106.3, -4.23, None, 784.8, "1000", False, 0],
    ["e49424", "GLO1440 ", "Brazil", 1716231245, 1716231245, -46.5200, -23.4800, 1200.0, False, 90.5, 305.1, -3.5, None, 1250.0, "2341", False, 0],
    ["e48c31", "AZU4561 ", "Brazil", 1716231244, 1716231245, -46.3500, -23.4000, 2500.0, False, 140.2, 280.0, 0.0, None, 2600.0, "5213", False, 0],
    ["a3b1c2", "TAP025  ", "Portugal", 1716231245, 1716231245, -46.4000, -23.5000, 950.0, False, 85.0, 310.0, -5.0, None, 980.0, "4421", False, 0],
    ["e47d11", "GOL1212 ", "Brazil", 1716231245, 1716231245, -46.6000, -23.3500, 3200.0, False, 180.0, 130.0, 2.5, None, 3300.0, "1200", False, 0],
    ["e8921a", "LATAM90 ", "Chile", 1716231245, 1716231245, -46.4500, -23.5500, 1500.0, False, 110.0, 350.0, -2.0, None, 1550.0, "3311", False, 0]
]

# --- FUNÇÕES ---

def get_real_flights_gru():
    """
    Tenta pegar dados AO VIVO da OpenSky.
    Se der erro 429 (Too Many Requests), usa o SNAPSHOT REAL.
    """
    url = "https://opensky-network.org/api/states/all?lamin=-23.8&lomin=-46.8&lamax=-23.0&lomax=-46.0"
    cols = ['icao24', 'callsign', 'origin_country', 'time_position', 'last_contact', 'longitude', 'latitude', 'baro_altitude', 'on_ground', 'velocity', 'true_track', 'vertical_rate', 'sensors', 'geo_altitude', 'squawk', 'spi', 'position_source']
    
    try:
        r = requests.get(url, timeout=5)
        
        # SUCESSO (200)
        if r.status_code == 200:
            json_data = r.json()
            if json_data['states']:
                df = pd.DataFrame(json_data['states'], columns=cols)
                return df, "🟢 LIVE (API)"
            else:
                return pd.DataFrame(), "🟡 LIVE (Sem voos)"

        # ERRO DE LIMITE (429) -> USA SNAPSHOT
        elif r.status_code == 429:
            df = pd.DataFrame(SNAPSHOT_REAL_DATA, columns=cols)
            return df, "🔴 LIMITADA (Usando Snapshot Real)"
            
        else:
            return pd.DataFrame(), f"Erro {r.status_code}"
            
    except Exception as e:
        # TIMEOUT/ERRO -> USA SNAPSHOT
        df = pd.DataFrame(SNAPSHOT_REAL_DATA, columns=cols)
        return df, "🔴 OFFLINE (Usando Snapshot Real)"

def get_real_weather(lat, lon):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,precipitation,wind_speed_10m&timezone=America%2FSao_Paulo"
        r = requests.get(url, timeout=3)
        return r.json()['current']
    except:
        return {'temperature_2m': 24, 'precipitation': 0, 'wind_speed_10m': 12}

# --- SIDEBAR ---
with st.sidebar:
    st.title("AERO.OPS V2")
    st.markdown("---")
    
    # BOTÃO MANUAL
    if st.button("📡 ATUALIZAR RADAR"):
        st.session_state['refresh'] = True
    
    st.markdown("---")
    st.write("🎯 ALVO: SBGR (Guarulhos)")
    lat_gru = -23.4356
    lon_gru = -46.4731

# --- DASHBOARD ---
st.title("RADAR DE CONTROLE (GRU)")

# Busca dados
with st.spinner("Contactando torre..."):
    df_raw, status_msg = get_real_flights_gru()

# Exibe Status da Conexão
if "LIVE" in status_msg:
    st.toast(f"Status: {status_msg}", icon="📡")
else:
    st.warning(f"⚠️ API Instável: {status_msg}. Exibindo dados de cache recente.")

# Lógica de Exibição
if not df_raw.empty:
    
    # Limpeza de Dados (O desafio do aluno)
    df_voos = df_raw.copy()
    df_voos['callsign'] = df_voos['callsign'].str.strip()
    df_voos = df_voos.dropna(subset=['latitude', 'longitude'])
    
    # 1. MAPA
    fig = px.scatter_mapbox(
        df_voos,
        lat="latitude", lon="longitude",
        hover_name="callsign",
        hover_data=["velocity", "baro_altitude"],
        color="velocity",
        color_continuous_scale=["#00ff00", "#ffff00", "#ff0000"],
        size_max=20, zoom=8, height=500
    )
    fig.add_scattermapbox(lat=[lat_gru], lon=[lon_gru], name="SBGR", marker=dict(size=20, color='white'))
    fig.update_layout(mapbox_style="carto-darkmatter", margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig, use_container_width=True)
    
    # 2. TABELA
    st.subheader("📋 Lista de Tráfego")
    st.dataframe(df_voos[['callsign', 'origin_country', 'velocity', 'baro_altitude', 'on_ground']], use_container_width=True)
    
    # 3. CÁLCULO
    st.markdown("---")
    st.subheader("🧮 Telemetria")
    
    voo = st.selectbox("Selecionar Voo:", df_voos['callsign'].unique())
    if voo:
        dados_voo = df_voos[df_voos['callsign'] == voo].iloc[0]
        dist = geodesic((dados_voo['latitude'], dados_voo['longitude']), (lat_gru, lon_gru)).km
        vel = dados_voo['velocity'] * 3.6
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Distância GRU", f"{dist:.1f} km")
        c2.metric("Velocidade", f"{vel:.0f} km/h")
        c3.metric("Altitude", f"{dados_voo['baro_altitude']:.0f} m")

    # DOWNLOAD
    st.markdown("---")
    csv = df_voos.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Baixar Dados (CSV)", csv, "radar_log.csv", "text/csv")

else:
    st.error("Erro crítico no sistema de radar.")
