import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import random
from datetime import datetime
from geopy.distance import geodesic

# --- Configuração "Air Traffic Control (ATC)" ---
st.set_page_config(page_title="AeroOps Radar", page_icon="✈️", layout="wide")

# --- CSS CUSTOMIZADO: ESTILO RADAR/HACKER ---
st.markdown("""
<style>
    /* Fundo Escuro Profundo */
    .stApp { background-color: #050505; color: #00ff41; }
    
    /* Fontes Monoespaçadas (Estilo Terminal) */
    h1, h2, h3, div, span, p, label { font-family: 'Courier New', monospace !important; }
    
    /* Títulos em Verde Neon */
    h1, h2, h3 { color: #00ff41 !important; text-transform: uppercase; text-shadow: 0 0 5px #003300; }
    
    /* Cards de Métricas */
    div[data-testid="stMetric"] {
        background-color: #0f111a;
        border: 1px solid #00ff41;
        box-shadow: 0 0 10px rgba(0, 255, 65, 0.1);
        padding: 10px;
    }
    div[data-testid="stMetricLabel"] { color: #00cc33; font-size: 0.8rem; }
    div[data-testid="stMetricValue"] { color: #ffffff; text-shadow: 0 0 5px #fff; }
    
    /* Inputs */
    .stTextInput>div>div>input, .stNumberInput>div>div>input, .stSelectbox>div>div>div {
        background-color: #0f111a;
        color: #00ff41;
        border: 1px solid #004411;
    }
    
    /* Botões */
    .stButton>button {
        background-color: #003300; 
        color: #00ff41; 
        border: 1px solid #00ff41;
        border-radius: 0px;
        font-weight: bold;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        background-color: #00ff41;
        color: black;
        box-shadow: 0 0 15px #00ff41;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE DADOS (ROBUSTAS) ---

@st.cache_data(ttl=30)
def get_live_flights():
    """
    Busca voos na OpenSky. 
    Se falhar ou demorar > 4s, gera dados fake para não travar a aula.
    """
    # Bounding Box aproximado do Brasil
    url = "https://opensky-network.org/api/states/all?lamin=-33.7&lomin=-73.9&lamax=5.2&lomax=-34.7"
    
    # 1. Tenta API Real
    try:
        r = requests.get(url, timeout=4) # Timeout curto para agilidade
        if r.status_code == 200:
            data = r.json()
            if data['states'] is None: raise Exception("Sem dados na área")
            
            cols = ['icao24', 'callsign', 'origin_country', 'time_position', 'last_contact', 'longitude', 'latitude', 'baro_altitude', 'on_ground', 'velocity', 'true_track', 'vertical_rate', 'sensors', 'geo_altitude', 'squawk', 'spi', 'position_source']
            df = pd.DataFrame(data['states'], columns=cols)
            
            # Limpeza
            df['callsign'] = df['callsign'].str.strip()
            # Filtra voos voando (não no chão) e altitude de cruzeiro
            df = df[(df['baro_altitude'] > 2000) & (df['velocity'] > 50)]
            df = df.dropna(subset=['latitude', 'longitude'])
            
            if not df.empty:
                st.toast("📡 Link OpenSky: ATIVO (Dados Reais)", icon="🟢")
                return df, True
    except:
        pass # Falhou, vai para simulação

    # 2. Simulação (Fallback)
    st.toast("⚠️ Link OpenSky: INSTÁVEL (Modo Simulação Ativo)", icon="🟠")
    dados_fake = []
    # Gera rotas aleatórias sobre SP/Rio/Minas
    for i in range(20):
        lat = -23.5 + random.uniform(-5, 5)
        lon = -46.6 + random.uniform(-5, 5)
        dados_fake.append({
            'callsign': f"GLO{random.randint(1000, 9999)}",
            'latitude': lat,
            'longitude': lon,
            'velocity': random.uniform(200, 260), # m/s
            'baro_altitude': random.uniform(8000, 11000),
            'origin_country': 'Brazil',
            'true_track': random.uniform(0, 360)
        })
    return pd.DataFrame(dados_fake), False

def get_weather(lat, lon):
    """Busca clima na Open-Meteo (Muito estável)"""
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,precipitation,wind_speed_10m&timezone=America%2FSao_Paulo"
        r = requests.get(url, timeout=5)
        return r.json()['current']
    except:
        return {'temperature_2m': 25.0, 'precipitation': 0.0, 'wind_speed_10m': 10.0}

# --- CARGA DE DADOS ---
df_voos, is_real_data = get_live_flights()

# --- SIDEBAR: PLANO DE VOO ---
with st.sidebar:
    st.title("AERO.OPS // ATC")
    st.image("https://img.icons8.com/fluency/96/airport.png", width=80)
    st.markdown("---")
    
    st.write("STATUS DO SISTEMA:")
    if is_real_data:
        st.success("RADAR: ONLINE (LIVE)")
    else:
        st.warning("RADAR: SIMULATION MODE")
    
    st.markdown("---")
    st.subheader("✈️ Rota Monitorada")
    st.caption("Defina origem/destino para cálculo de atraso.")
    
    # Inputs com valores padrão (GRU -> GIG)
    origem_lat = st.number_input("Lat Origem (GRU)", value=-23.4356, format="%.4f")
    origem_lon = st.number_input("Lon Origem (GRU)", value=-46.4731, format="%.4f")
    
    dest_lat = st.number_input("Lat Destino (GIG)", value=-22.8089, format="%.4f")
    dest_lon = st.number_input("Lon Destino (GIG)", value=-43.2436, format="%.4f")

# --- INTERFACE PRINCIPAL ---
st.title("TORRE DE CONTROLE: MONITORAMENTO AÉREO")

# 1. MAPA DE RADAR
st.subheader("📍 Radar Tático (Brasil)")

if not df_voos.empty:
    fig_map = px.scatter_mapbox(
        df_voos, 
        lat="latitude", lon="longitude", 
        hover_name="callsign", 
        hover_data=["velocity", "baro_altitude"],
        color="velocity", 
        color_continuous_scale=["#00ff41", "#ffff00", "#ff0000"],
        size_max=15, zoom=4, height=500
    )
    fig_map.update_layout(
        mapbox_style="carto-darkmatter",
        margin={"r":0,"t":0,"l":0,"b":0},
        paper_bgcolor="#050505"
    )
    st.plotly_chart(fig_map, use_container_width=True)
else:
    st.error("Erro crítico no sistema de radar.")

st.markdown("---")

# 2. PAINEL DE OPERAÇÕES (Análise de Voo Único)
st.subheader("🛑 Predição de Atrasos & Telemetria")

if not df_voos.empty:
    # Seleção de Voo
    voos_lista = df_voos['callsign'].unique()
    voo_selecionado = st.selectbox("SELECIONE A AERONAVE PARA RASTREIO:", voos_lista)
    
    if voo_selecionado:
        # Filtra dados do voo
        dado = df_voos[df_voos['callsign'] == voo_selecionado].iloc[0]
        
        # Coleta Clima (API Real)
        clima_dest = get_weather(dest_lat, dest_lon)
        
        # --- CÁLCULOS MATEMÁTICOS (GEOPY) ---
        pos_aviao = (dado['latitude'], dado['longitude'])
        pos_dest = (dest_lat, dest_lon)
        
        # Distância Geodésica (considera a curvatura da Terra)
        dist_km = geodesic(pos_aviao, pos_dest).km
        
        # Velocidade: API traz m/s, convertemos para km/h
        vel_kmh = dado['velocity'] * 3.6
        altitude_ft = dado['baro_altitude'] * 3.28084 # Metros para Pés
        
        # ETA (Estimativa de Tempo de Chegada)
        if vel_kmh > 0:
            horas_restantes = dist_km / vel_kmh
            minutos_restantes = int(horas_restantes * 60)
        else:
            minutos_restantes = 999
            
        # --- ALGORITMO DE RISCO (REGRAS DE NEGÓCIO) ---
        risco_score = 0
        fatores = []
        
        # 1. Vento Forte no Destino (> 25 km/h)
        vento = clima_dest['wind_speed_10m']
        if vento > 25:
            risco_score += 30
            fatores.append(f"Vento Cruzado ({vento} km/h)")
            
        # 2. Chuva no Destino (> 0 mm)
        chuva = clima_dest['precipitation']
        if chuva > 0.5:
            risco_score += 40
            fatores.append(f"Chuva na Pista ({chuva} mm)")
            
        # 3. Velocidade Baixa em Rota (< 600 km/h e alto)
        if vel_kmh < 600 and altitude_ft > 20000:
            risco_score += 20
            fatores.append("Velocidade Cruzeiro Baixa")
            
        # Penalidade por Distância Longa
        if minutos_restantes > 120:
            risco_score += 10

        # --- EXIBIÇÃO ---
        
        # Linha 1: Métricas de Voo
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("CALLSIGN", voo_selecionado)
        c2.metric("VELOCIDADE", f"{int(vel_kmh)} km/h")
        c3.metric("ALTITUDE", f"{int(altitude_ft)} ft")
        c4.metric("ETA ESTIMADO", f"{minutos_restantes} min")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Linha 2: Clima e Risco
        col_risk, col_env = st.columns([1, 2])
        
        with col_risk:
            st.markdown("#### STATUS DE RISCO")
            if risco_score > 50:
                st.error(f"CRÍTICO ({risco_score}%)")
                st.markdown("🔴 **ALTA PROBABILIDADE DE ATRASO**")
            elif risco_score > 20:
                st.warning(f"ATENÇÃO ({risco_score}%)")
                st.markdown("🟠 **MONITORAR CONDIÇÕES**")
            else:
                st.success(f"NOMINAL ({risco_score}%)")
                st.markdown("🟢 **VOO NO HORÁRIO**")
                
            if fatores:
                st.markdown("**Fatores de Atraso:**")
                for f in fatores: st.caption(f"> {f}")
        
        with col_env:
            st.markdown("#### TELEMETRIA AMBIENTAL (DESTINO)")
            # Criando um DataFrame visual para o clima
            df_clima = pd.DataFrame([
                {"METRIC": "TEMPERATURA", "VALUE": f"{clima_dest['temperature_2m']} °C"},
                {"METRIC": "PRECIPITAÇÃO", "VALUE": f"{clima_dest['precipitation']} mm"},
                {"METRIC": "VEL. VENTO", "VALUE": f"{clima_dest['wind_speed_10m']} km/h"}
            ])
            st.dataframe(df_clima, hide_index=True, use_container_width=True)

# --- RODAPÉ / DOWNLOADS ---
st.markdown("---")
st.subheader("💾 CAIXA PRETA (LOGS)")

if not df_voos.empty:
    col_dl1, col_dl2 = st.columns([1, 3])
    with col_dl1:
        csv = df_voos.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 BAIXAR DADOS DE VOO (CSV)",
            data=csv,
            file_name="flight_log_blackbox.csv",
            mime="text/csv"
        )
    with col_dl2:
        st.caption("AeroOps Control System v4.2 | Connected to OpenSky Network & Open-Meteo")
