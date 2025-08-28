from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Tuple, Any

import os
import requests
import pandas as pd
from shapely.geometry import Polygon
from haversine import haversine

app = FastAPI()

# --------------------------------------------------------------------
# Download CSV from Dropbox/Google-Drive link (if not exists)
# --------------------------------------------------------------------
CSV_FILE = "Indian_GWL_Data.csv"
CSV_URL = "https://www.dropbox.com/scl/fi/3arogeysxlomwr2ofof68/Indian_GWL_Data.csv?rlkey=qbc9sfx7wyxm3mjod6zd30be8&st=ldfhowsc&dl=1"

def download_csv():
    if not os.path.exists(CSV_FILE):
        print("Downloading CSV...")
        r = requests.get(CSV_URL)
        r.raise_for_status()
        with open(CSV_FILE, "wb") as f:
            f.write(r.content)
        print("Download complete.")

download_csv()

# --------------------------------------------------------------------
# Load CSV (once)
# --------------------------------------------------------------------
df = pd.read_csv(CSV_FILE)
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df = df.dropna(subset=["date", "latitude", "longitude"])

# --------------------------------------------------------------------
# Request model
# --------------------------------------------------------------------
class CoordinatesRequest(BaseModel):
    coordinates: List[Tuple[float, float]]

# --------------------------------------------------------------------
# Endpoint
# --------------------------------------------------------------------
@app.post("/nearest-station")
def get_nearest_station(req: CoordinatesRequest) -> Any:
    coords = req.coordinates

    if len(coords) < 3:
        raise HTTPException(status_code=400, detail="At least 3 coordinates are required to form a polygon")

    try:
        poly = Polygon(coords)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid polygon: {e}")

    centroid = (poly.centroid.y, poly.centroid.x)

    # -------------------------------------------------------------
    # Find nearest station (use unique lat/lon values only)
    # -------------------------------------------------------------
    unique_stations = df.drop_duplicates(subset=["latitude", "longitude"])

    min_dist = float("inf")
    nearest_station = None
    for _, row in unique_stations.iterrows():
        dist = haversine(centroid, (row.latitude, row.longitude))
        if dist < min_dist:
            min_dist = dist
            nearest_station = row

    if nearest_station is None:
        raise HTTPException(status_code=404, detail="No station found")

    # -------------------------------------------------------------
    # Retrieve all data rows for that station (all dates)
    # -------------------------------------------------------------
    station_data = (
        df[(df["latitude"] == nearest_station["latitude"]) &
           (df["longitude"] == nearest_station["longitude"])]
        .sort_values("date")
        .drop(columns=["id", "source", "year"], errors="ignore")
    )

    response = {
        "station_name": nearest_station["station_name"],
        "district_name": nearest_station["district_name"],
        "state_name": nearest_station["state_name"],
        "distance_km": round(min_dist, 2),
        "data": []
    }

    for _, row in station_data.iterrows():
        response["data"].append({
            "date": row["date"].strftime("%Y-%m-%d"),
            "currentlevel": float(row["currentlevel"]) if not pd.isna(row["currentlevel"]) else None
        })

    return response

