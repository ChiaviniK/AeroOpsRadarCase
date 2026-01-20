import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import random
from datetime import datetime
from geopy.distance import geodesic

# --- Configuração "Air Traffic Control (ATC)" ---
st.set_page_config(page_title="AeroOps Radar | Rio-SP", page_icon="✈️", layout="wide")

# --- CSS CUSTOMIZADO (Dark Terminal Theme) ---
st.markdown("""
<style>
    .stApp { background-color: #050505; color: #00ff41; }
    h1, h2, h3, div, span, p, label { font-family: 'Courier New', monospace !important; }
    h1, h2, h3 { color: #00ff41 !important; text-transform: uppercase; text-shadow: 0 0 5px #003300; }
    
    /* Metrics Cards */
    div[data-testid="stMetric"] {
        background-color: #0f111a;
        border: 1px solid #00ff41;
        box-shadow: 0 0 10px rgba(0, 255, 65, 0.1);
    }
    div[data-testid="stMetricLabel"] { color: #00cc33; font-size: 0.8rem; }
    div[data-testid="stMetricValue"] { color: #ffffff; text-shadow: 0 0 5px #fff; }
    
    /* Inputs e Botões */
    .stTextInput>div>div>input, .stNumberInput>div>div>input, .stSelectbox>div>div>div {
        background-color: #0f111a; color: #00ff41; border: 1px solid #004411;
    }
    .stButton>button {
        background-color: #003300; color: #00ff41; border: 1px solid #00ff41;
        border-radius: 0px; font-weight: bold; transition: all 0.3s;
    }
    .stButton>button:hover {
        background-color: #00ff41; color: black; box-shadow: 0 0 15px #00ff41;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE DADOS (HÍBRIDAS E OTIMIZADAS) ---

@st.cache_data(ttl=15) # Cache curto para sensação de tempo real
def get_live_flights():
    """
    Busca voos no corredor Rio-SP (Mais leve que buscar Brasil todo).
    Se falhar, gera simulação realista.
    """
    # Bounding Box: Eixo Rio-SP (Diminui carga na API)
    url = "https://opensky-network.org/api/states/all?lamin=-24.5&lomin=-47.5&lamax=-22.0&lomax=-42.0"
    
    # 1. TENTATIVA REAL (OPENSKY)
    try:
        r = requests.get(url, timeout=4) # Timeout curto
        if r.status_code == 200:
            json_data = r.json()
            if json_data['states'] is not None:
                cols = ['icao24', 'callsign', 'origin_country', 'time_position', 'last_contact', 'longitude', 'latitude', 'baro_altitude', 'on_ground', 'velocity', 'true_track', 'vertical_rate', 'sensors', 'geo_altitude', 'squawk', 'spi', 'position_source']
                df = pd.DataFrame(json_data['states'], columns=cols)
                
                # Limpeza
                df['callsign'] = df['callsign'].str.strip()
                # Apenas voos comerciais altos e rápidos
                df = df[(df['baro_altitude'] > 2000) & (df['velocity'] > 50)]
                df = df.dropna(subset=['latitude', 'longitude'])
                
                if not df.empty:
                    return df, True # True = Dados Reais
    except:
        pass # Falhou silenciosamente, vai para o plano B

    # 2. SIMULAÇÃO REALISTA (FALLBACK)
    # Gera aviões "fakes" mas com nomes reais (TAM, GLO, AZU) na rota Rio-SP
    fake_data = []
    cias = ['TAM', 'GLO', 'AZU']
    
    for i in range(12): # 12 aviões na tela
        lat = random.uniform(-24.0, -22.5) # Entre SP e Rio
        lon = random.uniform(-46.5, -43.0)
        cia = random.choice(cias)
        num = random.randint(1000, 9999)
        
        fake_data.append({
            'callsign': f"{cia}{num}",
            'latitude': lat,
            'longitude': lon,
            'velocity': random.uniform(200, 260), # ~800km/h (m/s)
            'baro_altitude': random.uniform(8000, 11000), # ~30k pés
            'origin_country': 'Brazil',
            'true_track': random.uniform(45, 65) # Direção Nordeste (SP->Rio)
        })
    
    return pd.DataFrame(fake_data), False # False = Dados Simulados

@st.cache_data(ttl=300)
def get_weather(lat, lon):
    """Busca clima no destino (Open-Meteo é muito estável)"""
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,precipitation,wind_speed_10m&timezone=America%2FSao_Paulo"
        r = requests.get(url, timeout=5)
        return r.json()['current']
    except:
        return {'temperature_2m': 25.0, 'precipitation': 0.0, 'wind_speed_10m': 10.0}

# --- LÓGICA DE CARGA (SEM VISUAL NO CACHE) ---
df_voos, is_real_data = get_live_flights()

# --- SIDEBAR ---
with st.sidebar:
    st.title("AERO.OPS // ATC")
    st.image("https://img.icons8.com/fluency/96/airport.png", width=80)
    st.markdown("---")
    
    st.write("STATUS DO RADAR:")
    if is_real_data:
        st.success("LINK: OPENSKY (LIVE)")
        st.toast("📡 Radar Online: Dados Reais", icon="🟢")
    else:
        st.warning("LINK: SIMULATOR (BACKUP)")
        st.toast("⚠️ Radar Instável: Modo Simulação", icon="🟠")
    
    st.markdown("---")
    st.subheader("✈️ Plano de Voo (Destino)")
    
    # Defaults: Congonhas (CGH) -> Santos Dumont (SDU)
    dest_lat = st.number_input("Lat Destino (SDU)", value=-22.9105, format="%.4f")
    dest_lon = st.number_input("Lon Destino (SDU)", value=-43.1631, format="%.4f")

# --- INTERFACE PRINCIPAL ---
st.title("PONTE AÉREA: MONITORAMENTO TÁTICO")

# 1. MAPA DE RADAR
st.subheader("📍 Radar Eixo Rio-SP")

if not df_voos.empty:
    fig_map = px.scatter_mapbox(
        df_voos, 
        lat="latitude", lon="longitude", 
        hover_name="callsign", 
        hover_data=["velocity", "baro_altitude"],
        color="velocity", 
        color_continuous_scale=["#00ff41", "#ffff00", "#ff0000"],
        size_max=15, zoom=6, height=500
    )
    fig_map.update_layout(
        mapbox_style="carto-darkmatter",
        margin={"r":0,"t":0,"l":0,"b":0},
        paper_bgcolor="#050505"
    )
    st.plotly_chart(fig_map, use_container_width=True)
else:
    st.error("Erro crítico: Nenhum dado de voo disponível.")

st.markdown("---")

# 2. ANÁLISE PREDITIVA
st.subheader("🛑 Calculadora de Atraso (ETA Dinâmico)")

if not df_voos.empty:
    col_sel, col_kpi = st.columns([1, 3])
    
    with col_sel:
        # Lista de voos para o aluno escolher
        voos_lista = df_voos['callsign'].unique()
        voo_selecionado = st.selectbox("RASTREAR AERONAVE:", voos_lista)
    
    if voo_selecionado:
        # Extrai dados do voo escolhido
        dado = df_voos[df_voos['callsign'] == voo_selecionado].iloc[0]
        
        # Busca clima no destino
        clima = get_weather(dest_lat, dest_lon)
        
        # --- CÁLCULOS (O DESAFIO DO ALUNO) ---
        pos_aviao = (dado['latitude'], dado['longitude'])
        pos_dest = (dest_lat, dest_lon)
        
        # 1. Distância Real (Geodesic)
        dist_km = geodesic(pos_aviao, pos_dest).km
        
        # 2. Conversões
        vel_kmh = dado['velocity'] * 3.6
        alt_ft = dado['baro_altitude'] * 3.28084
        
        # 3. ETA Simples
        if vel_kmh > 0:
            minutos_voo = int((dist_km / vel_kmh) * 60)
        else:
            minutos_voo = 999
            
        # 4. Algoritmo de Risco (Regra de Negócio)
        risco = 0
        msgs = []
        
        # Vento > 25km/h
        if clima['wind_speed_10m'] > 25:
            risco += 30
            msgs.append(f"Vento Forte: {clima['wind_speed_10m']} km/h")
            
        # Chuva > 0.5mm
        if clima['precipitation'] > 0.5:
            risco += 40
            msgs.append(f"Chuva na Pista: {clima['precipitation']} mm")
            
        # Penalidade Distância Longa vs Baixa Vel
        if minutos_voo > 45 and vel_kmh < 400:
            risco += 20
            msgs.append("Aproximação Lenta")

        # --- EXIBIÇÃO DE DADOS ---
        with col_kpi:
            c1, c2, c3 = st.columns(3)
            c1.metric("DISTÂNCIA RESTANTE", f"{int(dist_km)} km")
            c2.metric("VELOCIDADE SOLO", f"{int(vel_kmh)} km/h")
            c3.metric("TEMPO ESTIMADO", f"{minutos_voo} min")
        
        st.markdown("---")
        
        # Painel de Decisão
        c_risk, c_weather = st.columns(2)
        
        with c_risk:
            st.markdown("#### ⚠️ Nível de Risco")
            if risco > 50:
                st.error(f"ALTO RISCO DE ATRASO ({risco}%)")
            elif risco > 20:
                st.warning(f"RISCO MODERADO ({risco}%)")
            else:
                st.success(f"OPERAÇÃO NORMAL ({risco}%)")
            
            for m in msgs: st.caption(f"> {m}")
            
        with c_weather:
            st.markdown("#### 🌦️ Condições no Destino")
            cols_w = st.columns(3)
            cols_w[0].metric("Temp", f"{clima['temperature_2m']}°C")
            cols_w[1].metric("Chuva", f"{clima['precipitation']}mm")
            cols_w[2].metric("Vento", f"{clima['wind_speed_10m']}km/h")

# --- DOWNLOADS ---
st.markdown("---")
st.subheader("💾 Black Box Data")
if not df_voos.empty:
    csv = df_voos.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Baixar Telemetria (CSV)", csv, "flight_logs.csv", "text/csv")
