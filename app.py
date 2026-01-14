import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from geopy.distance import geodesic

# --- Configuração "Air Traffic Control (ATC)" ---
st.set_page_config(page_title="AeroOps Radar", page_icon="✈️", layout="wide")

st.markdown("""
<style>
    /* Fundo Radar Escuro */
    .stApp { background-color: #0d1117; color: #00ff41; }
    
    /* Fontes Monoespaçadas (Estilo Terminal) */
    h1, h2, h3, div, span, p { font-family: 'Courier New', monospace !important; }
    
    /* Cor Verde Hacker/Radar */
    h1, h2 { color: #00ff41 !important; text-transform: uppercase; }
    
    /* Metrics Cards */
    div[data-testid="stMetric"] {
        background-color: #161b22;
        border: 1px solid #00ff41;
        box-shadow: 0 0 10px rgba(0, 255, 65, 0.2);
    }
    div[data-testid="stMetricLabel"] { color: #00ff41; }
    div[data-testid="stMetricValue"] { color: #ffffff; }
    
    /* Botões */
    .stButton>button {
        background-color: #1f6feb; color: white; border: 1px solid #1f6feb;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE API (REAL-TIME) ---

@st.cache_data(ttl=60) # Cache de 60 segundos para não estourar a API
def get_live_flights():
    """Busca voos ao vivo sobre o Brasil (OpenSky Network)"""
    # Bounding Box do Brasil (aprox)
    url = "https://opensky-network.org/api/states/all?lamin=-33.7&lomin=-73.9&lamax=5.2&lomax=-34.7"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        colunas = ['icao24', 'callsign', 'origin_country', 'time_position', 'last_contact', 'longitude', 'latitude', 'baro_altitude', 'on_ground', 'velocity', 'true_track', 'vertical_rate', 'sensors', 'geo_altitude', 'squawk', 'spi', 'position_source']
        df = pd.DataFrame(data['states'], columns=colunas)
        
        # Filtrar apenas voos comerciais (geralmente altitude > 5000m e velocidade > 100m/s)
        df_filtered = df[(df['baro_altitude'] > 5000) & (df['velocity'] > 100)].copy()
        df_filtered['callsign'] = df_filtered['callsign'].str.strip() # Limpa espaços
        return df_filtered.dropna(subset=['latitude', 'longitude'])
    except Exception as e:
        return pd.DataFrame()

def get_weather(lat, lon):
    """Busca clima em tempo real para coordenadas (Open-Meteo)"""
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,precipitation,wind_speed_10m&timezone=America%2FSao_Paulo"
        r = requests.get(url)
        return r.json()['current']
    except:
        return {'temperature_2m': 0, 'precipitation': 0, 'wind_speed_10m': 0}

# --- SIDEBAR: PLANO DE VOO ---
with st.sidebar:
    st.title("AeroOps // ATC")
    st.image("https://img.icons8.com/fluency/96/airport.png", width=80)
    st.markdown("---")
    st.write("📡 STATUS DO RADAR: **ONLINE**")
    
    # Simulação de Rota (Aluno deve cruzar isso com banco de dados)
    st.subheader("Simulador de Rota")
    origem_lat = st.number_input("Lat Origem (GRU)", value=-23.4356)
    origem_lon = st.number_input("Lon Origem (GRU)", value=-46.4731)
    
    dest_lat = st.number_input("Lat Destino (GIG)", value=-22.8089)
    dest_lon = st.number_input("Lon Destino (GIG)", value=-43.2436)

    st.markdown("---")
    st.info("Monitorando espaço aéreo brasileiro (OpenSky Network Free Tier)")

# --- DASHBOARD ---
st.title("MONITORAMENTO DE TRÁFEGO AÉREO")

# 1. Mapa de Radar (Plotly)
st.subheader("📍 Radar em Tempo Real")
df_voos = get_live_flights()

if not df_voos.empty:
    # Cria o Mapa
    fig_map = px.scatter_mapbox(
        df_voos, 
        lat="latitude", lon="longitude", 
        hover_name="callsign", 
        hover_data=["velocity", "baro_altitude", "origin_country"],
        color="velocity", # Cor baseada na velocidade
        color_continuous_scale="Viridis",
        zoom=3, 
        height=500
    )
    fig_map.update_layout(mapbox_style="carto-darkmatter") # Estilo Dark Map
    fig_map.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig_map, use_container_width=True)
    
    # 2. Seleção de Voo para Análise Preditiva
    st.markdown("---")
    st.subheader("🛑 Análise de Risco de Atraso")
    
    voo_selecionado = st.selectbox("Selecione uma aeronave no radar:", df_voos['callsign'].unique())
    
    if voo_selecionado:
        # Pega dados do voo
        dados_voo = df_voos[df_voos['callsign'] == voo_selecionado].iloc[0]
        
        # Pega Clima na Origem e Destino (Inputs da Sidebar)
        clima_origem = get_weather(origem_lat, origem_lon)
        clima_destino = get_weather(dest_lat, dest_lon)
        
        # --- CÁLCULO DE ETA (Lógica do Aluno) ---
        # Distância atual do avião até o destino
        pos_aviao = (dados_voo['latitude'], dados_voo['longitude'])
        pos_dest = (dest_lat, dest_lon)
        distancia_km = geodesic(pos_aviao, pos_dest).km
        velocidade_kmh = dados_voo['velocity'] * 3.6 # m/s para km/h
        
        tempo_estimado_horas = distancia_km / velocidade_kmh if velocidade_kmh > 0 else 0
        eta_minutos = int(tempo_estimado_horas * 60)
        
        # --- ALGORITMO DE RISCO (A "Inteligência") ---
        risco = 0
        motivos = []
        
        # Regra 1: Vento forte no destino
        if clima_destino['wind_speed_10m'] > 25:
            risco += 30
            motivos.append("Vento Forte no Destino")
            
        # Regra 2: Chuva na Origem (atrasa decolagem de outros) ou Destino
        if clima_destino['precipitation'] > 0:
            risco += 40
            motivos.append("Chuva no Destino")
            
        # Regra 3: Velocidade abaixo do normal (< 700km/h em cruzeiro)
        if velocidade_kmh < 700 and dados_voo['baro_altitude'] > 8000:
            risco += 20
            motivos.append("Velocidade de Cruzeiro Baixa")

        # Exibição dos KPIs
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Voo", voo_selecionado)
        c2.metric("Velocidade Atual", f"{int(velocidade_kmh)} km/h")
        c3.metric("Distância Destino", f"{int(distancia_km)} km")
        c4.metric("ETA Estimado", f"{eta_minutos} min")
        
        # Card de Risco
        st.markdown("#### Probabilidade de Atraso (AI Model)")
        
        col_risk, col_weather = st.columns([1, 2])
        
        with col_risk:
            if risco > 50:
                st.error(f"RISCO CRÍTICO: {risco}%")
            elif risco > 20:
                st.warning(f"RISCO MÉDIO: {risco}%")
            else:
                st.success(f"VOO PONTUAL: {risco}%")
            
            if motivos:
                st.write("Fatores:")
                for m in motivos: st.caption(f"- {m}")
        
        with col_weather:
            st.dataframe(pd.DataFrame([
                {"Local": "Destino (Previsto)", "Temp": f"{clima_destino['temperature_2m']}°C", "Vento": f"{clima_destino['wind_speed_10m']} km/h", "Chuva": f"{clima_destino['precipitation']} mm"}
            ]))

else:
    st.warning("Buscando satélites... (Se demorar, a API da OpenSky pode estar ocupada).")

# --- ÁREA DE DOWNLOADS (SQL) ---
st.markdown("---")
st.subheader("💾 Flight Data Recorder (Black Box)")
if not df_voos.empty:
    csv = df_voos.to_csv().encode('utf-8')
    st.download_button("📥 Baixar Log de Voo (CSV)", csv, "blackbox_log.csv", "text/csv")
