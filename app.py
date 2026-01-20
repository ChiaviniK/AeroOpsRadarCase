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

# --- FUNÇÕES (ADSB.lol com Tratamento de Tipos) ---

def safe_float(val):
    """Converte qualquer coisa para float. Se falhar, retorna 0.0"""
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0

def get_real_flights_gru():
    # Coordenadas GRU
    lat = -23.4356
    lon = -46.4731
    radius_nm = 50 
    
    url = f"https://api.adsb.lol/v2/lat/{lat}/lon/{lon}/dist/{radius_nm}"
    
    try:
        r = requests.get(url, timeout=5)
        
        if r.status_code == 200:
            data = r.json()
            if not data.get('ac'): return pd.DataFrame()
            
            flights = []
            for ac in data['ac']:
                # Verifica se tem lat/lon antes de processar
                if 'lat' in ac and 'lon' in ac:
                    
                    # --- CORREÇÃO DO ERRO AQUI ---
                    # Convertemos para float antes de multiplicar
                    gs_knots = safe_float(ac.get('gs', 0))
                    alt_feet = safe_float(ac.get('alt_baro', 0))
                    vert_rate = safe_float(ac.get('baro_rate', 0))
                    
                    flights.append({
                        'callsign': str(ac.get('flight', 'N/A')).strip(),
                        'icao24': str(ac.get('hex', '')),
                        'latitude': safe_float(ac.get('lat')),
                        'longitude': safe_float(ac.get('lon')),
                        # Agora a multiplicação é segura (float * float)
                        'velocity': gs_knots * 1.852,     # Knots -> km/h
                        'baro_altitude': alt_feet * 0.3048, # Feet -> Metros
                        'origin_country': 'Unknown', 
                        'vertical_rate': vert_rate
                    })
            
            df = pd.DataFrame(flights)
            
            # Filtros de Qualidade
            if not df.empty:
                df = df[df['callsign'] != 'N/A'] 
                df = df[df['baro_altitude'] > 0]
            
            return df
        else:
            return pd.DataFrame()
            
    except Exception as e:
        # Mostra erro no terminal para debug, mas não quebra o app
        print(f"Erro de dados: {e}")
        return pd.DataFrame()

# --- SIDEBAR ---
with st.sidebar:
    st.title("AERO.OPS V3.1")
    st.caption("Powered by ADSB.lol API")
    st.markdown("---")
    
    if st.button("📡 ATUALIZAR AO VIVO"):
        st.rerun()
    
    st.markdown("---")
    st.info("Sistema conectado à rede ADS-B Global (Open Source).")

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
    fig.add_scattermapbox(lat=[lat_gru], lon=[lon_gru], name="GRU Airport", marker=dict(size=25, color='red'))
    
    fig.update_layout(mapbox_style="carto-darkmatter", margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig, use_container_width=True)
    
    # 2. DETALHES
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
    st.caption("Se persistir, verifique se há voos na região de GRU agora.")
