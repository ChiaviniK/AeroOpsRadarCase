import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime
from geopy.distance import geodesic

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

# --- FUNÇÕES (SOMENTE DADOS REAIS) ---

def get_real_flights_gru():
    """
    Busca SOMENTE dados reais da OpenSky.
    Foco: Bounding Box pequeno ao redor de Guarulhos para garantir performance.
    """
    # Box pequeno ao redor de SP (reduz load da API)
    # lamin=-24.0, lomin=-47.0, lamax=-23.0, lomax=-46.0
    url = "https://opensky-network.org/api/states/all?lamin=-24.5&lomin=-47.5&lamax=-22.5&lomax=-45.5"
    
    try:
        # Timeout um pouco maior (10s) já que não temos fallback
        r = requests.get(url, timeout=10)
        
        if r.status_code == 200:
            json_data = r.json()
            if json_data['states'] is not None:
                cols = ['icao24', 'callsign', 'origin_country', 'time_position', 'last_contact', 'longitude', 'latitude', 'baro_altitude', 'on_ground', 'velocity', 'true_track', 'vertical_rate', 'sensors', 'geo_altitude', 'squawk', 'spi', 'position_source']
                df = pd.DataFrame(json_data['states'], columns=cols)
                
                # Limpeza básica
                df['callsign'] = df['callsign'].str.strip()
                # Remove aviões no chão (on_ground = True) para limpar o mapa
                df = df[df['on_ground'] == False]
                # Remove dados sem posição
                df = df.dropna(subset=['latitude', 'longitude'])
                
                return df
            else:
                return pd.DataFrame() # API respondeu, mas sem aviões na área
        else:
            st.error(f"Erro API OpenSky: {r.status_code}")
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Falha de Conexão: {e}")
        return pd.DataFrame()

def get_real_weather(lat, lon):
    """Clima Real (Open-Meteo)"""
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,precipitation,wind_speed_10m&timezone=America%2FSao_Paulo"
        r = requests.get(url, timeout=5)
        return r.json()['current']
    except:
        return None

# --- SIDEBAR ---
with st.sidebar:
    st.title("AERO.OPS V1")
    st.image("https://img.icons8.com/ios-filled/100/40C057/radar.png", width=80)
    st.markdown("---")
    
    st.write("📡 CONTROLE DE DADOS")
    st.info("Este sistema consome dados REAIS. Se a API estiver ocupada, aguarde 10s e tente novamente.")
    
    # BOTÃO MANUAL (Essencial para não bloquear IP)
    if st.button("📡 ATUALIZAR RADAR"):
        st.session_state['refresh'] = datetime.now()
    
    st.markdown("---")
    st.write("🎯 ALVO: SBGR (Guarulhos)")
    lat_gru = -23.4356
    lon_gru = -46.4731

# --- DASHBOARD ---
st.title("MONITORAMENTO DE TRÁFEGO EM TEMPO REAL")

# Busca dados APENAS se o botão for clicado ou na primeira carga
with st.spinner("Sintonizando satélites OpenSky..."):
    df_voos = get_real_flights_gru()

# Lógica de Exibição
if not df_voos.empty:
    st.success(f"SINAL ESTABELECIDO: {len(df_voos)} AERONAVES DETECTADAS")
    
    # 1. MAPA REAL
    fig = px.scatter_mapbox(
        df_voos,
        lat="latitude", lon="longitude",
        hover_name="callsign",
        hover_data=["velocity", "baro_altitude", "origin_country"],
        color="baro_altitude", # Cor pela altitude
        size="velocity",       # Tamanho pela velocidade
        color_continuous_scale="HSV",
        zoom=7, height=500
    )
    # Adiciona ponto do aeroporto
    fig.add_scattermapbox(lat=[lat_gru], lon=[lon_gru], name="GRU Airport", marker=dict(size=15, color='red'))
    
    fig.update_layout(mapbox_style="carto-darkmatter", margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig, use_container_width=True)
    
    # 2. TABELA DE DADOS REAIS
    st.subheader("📋 Telemetria Bruta (Live)")
    st.dataframe(
        df_voos[['callsign', 'origin_country', 'velocity', 'baro_altitude', 'vertical_rate']].sort_values('baro_altitude'),
        use_container_width=True
    )
    
    # 3. CÁLCULO DE CHEGADA (REAL)
    st.markdown("---")
    st.subheader("🧮 Calculadora de Aproximação")
    
    # Selectbox apenas com voos reais
    opcoes = df_voos['callsign'].tolist()
    voo_escolhido = st.selectbox("Selecione Aeronave:", options=opcoes)
    
    if voo_escolhido:
        # Pega dados do voo
        aviao = df_voos[df_voos['callsign'] == voo_escolhido].iloc[0]
        
        # Pega Clima Real de Guarulhos
        clima = get_real_weather(lat_gru, lon_gru)
        
        # Cálculos Reais
        pos_aviao = (aviao['latitude'], aviao['longitude'])
        pos_gru = (lat_gru, lon_gru)
        dist_km = geodesic(pos_aviao, pos_gru).km
        vel_kmh = aviao['velocity'] * 3.6
        
        # ETA
        if vel_kmh > 10:
            eta_min = int((dist_km / vel_kmh) * 60)
        else:
            eta_min = "N/A (Parado)"
            
        # Exibição
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Distância GRU", f"{dist_km:.1f} km")
        c2.metric("Velocidade", f"{vel_kmh:.0f} km/h")
        c3.metric("Altitude", f"{aviao['baro_altitude']:.0f} m")
        c4.metric("ETA Estimado", f"{eta_min} min")
        
        if clima:
            st.caption(f"Condições em Solo (GRU): Vento {clima['wind_speed_10m']} km/h | Chuva {clima['precipitation']} mm")
            if clima['wind_speed_10m'] > 20 or clima['precipitation'] > 1.0:
                st.warning("⚠️ ALERTA: Condições meteorológicas adversas para pouso.")

    # DOWNLOAD DOS DADOS REAIS
    st.markdown("---")
    csv = df_voos.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Baixar Snapshot de Dados Reais", csv, "live_data_gru.csv", "text/csv")

else:
    # SE A API FALHAR OU ESTIVER VAZIA
    st.warning("⚠️ Nenhum dado recebido da OpenSky.")
    st.markdown("""
    **Possíveis Causas:**
    1. A API está ocupada (Limite de requisições).
    2. Não há aviões voando NESTE MOMENTO exato no setor selecionado.
    3. Bloqueio temporário de IP.
    
    👉 **Aguarde 15 segundos e clique em 'ATUALIZAR RADAR' novamente.**
    """)
