import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
import geopandas as gpd
from shapely.geometry import Point
import os

st.set_page_config(layout="wide", page_title="Soundview: Compare Scenarios")

# --- DATA GENERATION (Cached for speed) ---
@st.cache_data
def get_flood_data():
    lat, lon = 40.8250, -73.8700
    return pd.DataFrame({
        'lat': np.random.normal(lat, 0.007, 1200),
        'lon': np.random.normal(lon, 0.007, 1200),
        'base_depth': np.random.uniform(2, 12, 1200),
    })

# --- SIDEBAR ---
st.sidebar.header("Global Controls")
time_step = st.sidebar.slider("Storm Timeline (0-60m)", 0, 60, 30)
reduction = st.sidebar.slider("Green Space Absorption %", 0, 100, 70)
intensity = np.sin((time_step / 60) * np.pi)

# --- DATA PROCESSING ---
df = get_flood_data()
df['baseline_depth'] = df['base_depth'] * intensity
df['mitigated_depth'] = df['baseline_depth'].copy()

# Try to load the SHP file with the index restore option
SHP_PATH = "VACANT_or_PARKING.shp"
lots_layer = None

if os.path.exists(SHP_PATH):
    try:
        # Force the restoration of missing .shx if needed
        os.environ["SHAPE_RESTORE_SHX"] = "YES"
        lots_gdf = gpd.read_file(SHP_PATH).to_crs("EPSG:4326")
        
        # Spatial Join for Mitigation
        geometry = [Point(xy) for xy in zip(df['lon'], df['lat'])]
        flood_gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
        joined = gpd.sjoin(flood_gdf, lots_gdf, how="left", predicate="within")
        
        # Apply reduction only to the 'mitigated' column
        df.loc[joined['index_right'].notnull(), 'mitigated_depth'] *= (1 - (reduction / 100))
        
        lots_layer = pdk.Layer(
            "GeoJsonLayer", lots_gdf,
            get_fill_color=[46, 204, 113, 100], # Green
            get_line_color=[255, 255, 255],
        )
    except Exception as e:
        st.sidebar.error(f"Shapefile Error: {e}")

# --- VIEWPORT SETTINGS ---
view = pdk.ViewState(latitude=40.8250, longitude=-73.8700, zoom=14, pitch=45)

# --- RENDER TWO COLUMNS ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("Baseline: Current Infrastructure")
    base_water = pdk.Layer(
        "ColumnLayer", df,
        get_position=["lon", "lat"],
        get_elevation="baseline_depth",
        elevation_scale=40, radius=20,
        get_fill_color=[231, 76, 60, 160], # Red/Warning for baseline
    )
    st.pydeck_chart(pdk.Deck(layers=[base_water], initial_view_state=view))

with col2:
    st.subheader("Proposed: Green Infrastructure")
    miti_water = pdk.Layer(
        "ColumnLayer", df,
        get_position=["lon", "lat"],
        get_elevation="mitigated_depth",
        elevation_scale=40, radius=20,
        get_fill_color=[52, 152, 219, 160], # Blue for mitigated
    )
    # Add the green lots layer under the water for the proposed scenario
    layers = [miti_water]
    if lots_layer: layers.append(lots_layer)
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view))

st.info(f"Visualizing T+{time_step} minutes. Left shows current risk (Red). Right shows 3D flood reduction via green conversion (Blue).")