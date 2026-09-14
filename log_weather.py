#!/usr/bin/env python3
"""
Logs current weather conditions from the Visual Crossing Timeline API to a CSV.

Designed to run on a schedule (GitHub Actions) and append one row per run.
Logs RAW values only - derived measures (onshore flag, wind energy, pressure
anomaly, erosion index) are calculated later in Excel, so they can be revised
without re-collecting data.

Environment variables:
    VC_API_KEY   Visual Crossing API key (required)
    LOCATION     Location to query (default: Happisburgh,Norfolk,UK)
    CSV_PATH     Output file (default: data/happisburgh.csv)
"""

import csv
import os
import sys
from datetime import datetime, timezone
from urllib.parse import quote
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
import json

API_KEY = os.environ.get("VC_API_KEY")
LOCATION = os.environ.get("LOCATION", "Happisburgh,Norfolk,UK")
CSV_PATH = os.environ.get("CSV_PATH", "data/happisburgh.csv")

# unitGroup=uk gives: wind in mph, pressure in mb, temp in Celsius, precip in mm
URL = (
    "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services"
    "/timeline/{loc}/today"
    "?unitGroup=uk&include=current&contentType=json&key={key}"
)

COLUMNS = [
    "timestamp_utc",
    "timestamp_local",
    "location",
    "windspeed_mph",
    "windgust_mph",
    "winddir_deg",
    "pressure_mb",
    "temp_c",
    "humidity_pct",
    "precip_mm",
    "cloudcover_pct",
    "visibility_km",
    "conditions",
    "source",
]


def fetch():
    if not API_KEY:
        sys.exit("ERROR: VC_API_KEY is not set.")
    url = URL.format(loc=quote(LOCATION), key=API_KEY)
    try:
        with urlopen(url, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as e:
        sys.exit(f"ERROR: API returned HTTP {e.code}. {e.reason}")
    except URLError as e:
        sys.exit(f"ERROR: could not reach the API. {e.reason}")


def build_row(payload):
    current = payload.get("currentConditions")
    if not current:
        sys.exit("ERROR: response contained no 'currentConditions' block.")

    epoch = current.get("datetimeEpoch")
    if epoch is None:
        sys.exit("ERROR: response contained no timestamp.")

    utc = datetime.fromtimestamp(epoch, tz=timezone.utc)

    return {
        "timestamp_utc": utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        # Local date + time as the API reports it for the queried location.
        "timestamp_local": f"{payload.get('days', [{}])[0].get('datetime', '')} "
                           f"{current.get('datetime', '')}".strip(),
        "location": LOCATION,
        "windspeed_mph": current.get("windspeed"),
        "windgust_mph": current.get("windgust"),
        "winddir_deg": current.get("winddir"),
        "pressure_mb": current.get("pressure"),
        "temp_c": current.get("temp"),
        "humidity_pct": current.get("humidity"),
        "precip_mm": current.get("precip"),
        "cloudcover_pct": current.get("cloudcover"),
        "visibility_km": current.get("visibility"),
        "conditions": current.get("conditions"),
        "source": "visualcrossing/currentConditions",
    }


def append(row):
    directory = os.path.dirname(CSV_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)

    write_header = not os.path.exists(CSV_PATH) or os.path.getsize(CSV_PATH) == 0

    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def main():
    row = build_row(fetch())
    append(row)
    print(
        f"Logged {row['timestamp_utc']}  "
        f"wind {row['windspeed_mph']} mph  "
        f"dir {row['winddir_deg']}deg  "
        f"pressure {row['pressure_mb']} mb"
    )


if __name__ == "__main__":
    main()
