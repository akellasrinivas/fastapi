import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
import folium
from folium.plugins import Draw
from shapely.geometry import shape
from haversine import haversine
import plotly.express as px

# Load dataset
@st.cache_data
def load_data():
    df = pd.read_csv("Indian_GWL_Data.csv")
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['year'] = df['date'].dt.year
    return df

df = load_data()

st.title("Interactive Groundwater Level Finder")
st.markdown("Draw a polygon on the map to find nearest station data.")

# --- Dropdowns for state and district only ---
state = st.selectbox("Select State", sorted(df['state_name'].unique()))
districts = sorted(df[df['state_name'] == state]['district_name'].unique())
district = st.selectbox("Select District", districts)

# Center map on the district's first station
station_row = df[(df['state_name'] == state) & (df['district_name'] == district)].iloc[0]
center_lat = station_row.latitude
center_lon = station_row.longitude

# --- Create Folium Map (satellite + labels) ---
m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles=None)

# Satellite imagery
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri",
    name="Esri Satellite",
    overlay=False
).add_to(m)

# Labels overlay
folium.TileLayer(
    tiles="https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
    attr="Esri",
    name="Esri Labels",
    overlay=True
).add_to(m)

# Draw tool
draw = Draw(
    draw_options={
        'polygon': True,
        'polyline': False,
        'rectangle': True,
        'circle': False,
        'marker': False,
        'circlemarker': False,
    },
    edit_options={'edit': True}
)
draw.add_to(m)

folium.LayerControl().add_to(m)

# Show map and capture drawing
output = st_folium(m, height=500, width=800)

# --- If polygon drawn, find nearest station ---
if output and output.get("last_active_drawing"):
    try:
        geom = shape(output["last_active_drawing"]["geometry"])
        centroid = (geom.centroid.y, geom.centroid.x)

        # Find nearest station
        min_dist = float("inf")
        nearest_row = None
        for _, row in df.iterrows():
            dist = haversine(centroid, (row.latitude, row.longitude))
            if dist < min_dist:
                min_dist = dist
                nearest_row = row

        if nearest_row is not None:
            st.success(
                f"Nearest station: **{nearest_row['station_name']}** "
                f"({nearest_row['district_name']}, {nearest_row['state_name']}) "
                f"— Distance: {min_dist:.2f} km"
            )

        # Filter station data & clean columns
        station_data = (
            df[(df['latitude'] == nearest_row['latitude']) &
               (df['longitude'] == nearest_row['longitude'])]
            .sort_values("date")
            .drop(columns=['id', 'latitude', 'longitude', 'source', 'year'], errors='ignore')
        )

        # Save original for CSV download
        csv_data = station_data.copy()

        # Remove duplicate dates by averaging for plotting
        plot_data = station_data.groupby('date', as_index=False).agg({'currentlevel': 'mean'})

        # Line plot for groundwater level
        if 'currentlevel' in plot_data.columns:
            fig = px.line(
                plot_data,
                x="date",
                y="currentlevel",
                title=f"Groundwater Level Over Time — {nearest_row['station_name']}",
                labels={"currentlevel": "Groundwater Level (m)", "date": "Date"},
                markers=True
            )
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)

        # Download full original station data
        csv = csv_data.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name="nearest_station_data.csv",
            mime="text/csv"
        )

    except Exception as e:
        st.error(f"Error reading polygon: {e}")
