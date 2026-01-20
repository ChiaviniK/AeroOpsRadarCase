import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime
from geopy.distance import geodesic

# --- Configuração ---
st.set_page_config(page_title="AeroOps | ADSB.lol", page_icon="✈️", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #58a6ff; }
    h1, h2, h3, div, span, p { font-family: 'Consolas', monospace !important; }
    .stButton>button {
        background-color: #238636; color: white; border: none;
        width: 100%; height: 50px; font-weight: bold;
    }
    div[data-testid="stMetric"] { background-color: #161b22; border: 1px solid #30363d; }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES (API NOVA: ADSB.lol) ---

def get_real_flights_gru():
    """
    Busca dados na ADSB.lol (API Comunitária Open Source).
    Endpoint: Busca por raio (lat/lon/raio).
    """
    # Coordenadas GRU
    lat = -23.4356
    lon = -46.4731
    radius_nm = 50 # Raio de 50 milhas náuticas
    
    url = f"https://api.adsb.lol/v2/lat/{lat}/lon/{lon}/dist/{radius_nm}"
    
    try:
        r = requests.get(url, timeout=5)
        
        if r.status_code == 200:
            data = r.json()
            if not data.get('ac'): return pd.DataFrame()
            
            flights = []
            for ac in data['ac']:
                # A API retorna dados brutos, precisamos tratar se existem
                if 'lat' in ac and 'lon' in ac:
                    flights.append({
                        'callsign': ac.get('flight', 'N/A').strip(),
                        'icao24': ac.get('hex', ''),
                        'latitude': ac.get('lat'),
                        'longitude': ac.get('lon'),
                        # Conversões: Knots -> km/h, Feet -> Metros
                        'velocity': ac.get('gs', 0) * 1.852, 
                        'baro_altitude': ac.get('alt_baro', 0) * 0.3048,
                        'origin_country': 'Unknown', # Essa API não foca no país
                        'vertical_rate': ac.get('baro_rate', 0)
                    })
            
            df = pd.DataFrame(flights)
            # Filtros de Qualidade
            df = df[df['callsign'] != 'N/A'] # Remove quem está sem identificação
            df = df[df['baro_altitude'] > 0] # Remove erros de altitude 0
            
            return df
        else:
            st.error(f"Erro na API ADSB.lol: {r.status_code}")
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Erro de Conexão: {e}")
        return pd.DataFrame()

def get_real_weather(lat, lon):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,precipitation,wind_speed_10m&timezone=America%2FSao_Paulo"
        r = requests.get(url, timeout=3)
        return r.json()['current']
    except:
        return None

# --- SIDEBAR ---
with st.sidebar:
    st.title("AERO.OPS V3")
    st.caption("Powered by ADSB.lol API")
    st.markdown("---")
    
    if st.button("📡 ATUALIZAR AO VIVO"):
        st.rerun() # Recarrega o app forçando nova chamada
    
    st.markdown("---")
    st.info("Esta API (ADSB.lol) não exige cadastro e é alimentada pela comunidade. Muito mais rápida e estável.")

# --- DASHBOARD ---
st.title("RADAR DE TRÁFEGO: GUARULHOS (SBGR)")
lat_gru = -23.4356
lon_gru = -46.4731

# Busca Dados
with st.spinner("Rastreando transponders ADS-B..."):
    df_voos = get_real_flights_gru()

if not df_voos.empty:
    st.toast(f"{len(df_voos)} voos detectados via ADS-B", icon="✈️")
    
    # 1. MAPA
    fig = px.scatter_mapbox(
        df_voos,
        lat="latitude", lon="longitude",
        hover_name="callsign",
        hover_data=["velocity", "baro_altitude"],
        color="baro_altitude",
        size_max=15, zoom=8, height=500,
        color_continuous_scale="Viridis"
    )
    # Adiciona GRU no mapa
    fig.add_scattermapbox(lat=[lat_gru], lon=[lon_gru], name="GRU Airport", marker=dict(size=25, color='red'))
    
    fig.update_layout(mapbox_style="carto-darkmatter", margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig, use_container_width=True)
    
    # 2. CÁLCULO DE APROXIMAÇÃO
    st.markdown("---")
    col_kpi, col_table = st.columns([1, 2])
    
    with col_kpi:
        st.subheader("🔭 Focar Aeronave")
        lista_voos = df_voos['callsign'].unique()
        voo_sel = st.selectbox("Callsign:", lista_voos)
        
        if voo_sel:
            dado = df_voos[df_voos['callsign'] == voo_sel].iloc[0]
            dist = geodesic((dado['latitude'], dado['longitude']), (lat_gru, lon_gru)).km
            
            st.metric("Distância da Pista", f"{dist:.1f} km")
            st.metric("Velocidade Solo", f"{dado['velocity']:.0f} km/h")
            st.metric("Altitude", f"{dado['baro_altitude']:.0f} m")
            
    with col_table:
        st.subheader("📋 Lista de Chegadas")
        st.dataframe(
            df_voos[['callsign', 'velocity', 'baro_altitude']].sort_values('baro_altitude'),
            use_container_width=True,
            height=300
        )

    # DOWNLOAD
    st.markdown("---")
    csv = df_voos.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Baixar Dados ADS-B (CSV)", csv, "adsb_log.csv", "text/csv")

else:
    st.warning("Nenhum dado recebido. Tente clicar em 'ATUALIZAR' novamente.")
