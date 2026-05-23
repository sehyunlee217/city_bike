import os
import psycopg
import requests

STATION_INFORMATION_URL = (
    "https://tor.publicbikesystem.net/ube/gbfs/v1/en/station_information"
)
STATION_STATUS_URL = "https://tor.publicbikesystem.net/ube/gbfs/v1/en/station_status"
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5555/city_bike",
)


def fetch_json(url):
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


def fetch_station_information():
    return fetch_json(STATION_INFORMATION_URL)["data"]["stations"]


def fetch_station_status():
    return fetch_json(STATION_STATUS_URL)["data"]["stations"]


def create_stations_table(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS stations (
                station_id TEXT PRIMARY KEY,
                external_id TEXT,
                name TEXT NOT NULL,
                physical_configuration TEXT,
                lat DOUBLE PRECISION NOT NULL,
                lon DOUBLE PRECISION NOT NULL,
                altitude DOUBLE PRECISION,
                address TEXT,
                capacity INTEGER,
                is_charging_station BOOLEAN,
                rental_methods TEXT[],
                groups_array TEXT[],
                obcn TEXT,
                short_name TEXT,
                nearby_distance DOUBLE PRECISION,
                ride_code_support BOOLEAN,
                updated_at TIMESTAMPTZ DEFAULT now()
            );
            """
        )
    conn.commit()


def normalize_station(station):
    return {
        "station_id": station["station_id"],
        "external_id": station.get("external_id"),
        "name": station["name"],
        "physical_configuration": station.get("physical_configuration"),
        "lat": station["lat"],
        "lon": station["lon"],
        "altitude": station.get("altitude"),
        "address": station.get("address"),
        "capacity": station.get("capacity"),
        "is_charging_station": station.get("is_charging_station"),
        "rental_methods": station.get("rental_methods", []),
        "groups": station.get("groups", []),
        "obcn": station.get("obcn"),
        "short_name": station.get("short_name"),
        "nearby_distance": station.get("nearby_distance"),
        "_ride_code_support": station.get("_ride_code_support"),
    }


def upsert_station(conn, station):
    station = normalize_station(station)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO stations (
                station_id,
                external_id,
                name,
                physical_configuration,
                lat,
                lon,
                altitude,
                address,
                capacity,
                is_charging_station,
                rental_methods,
                groups_array,
                obcn,
                short_name,
                nearby_distance,
                ride_code_support
            )
            VALUES (
                %(station_id)s,
                %(external_id)s,
                %(name)s,
                %(physical_configuration)s,
                %(lat)s,
                %(lon)s,
                %(altitude)s,
                %(address)s,
                %(capacity)s,
                %(is_charging_station)s,
                %(rental_methods)s,
                %(groups)s,
                %(obcn)s,
                %(short_name)s,
                %(nearby_distance)s,
                %(_ride_code_support)s
            )
            ON CONFLICT (station_id)
            DO UPDATE SET
                external_id = EXCLUDED.external_id,
                name = EXCLUDED.name,
                physical_configuration = EXCLUDED.physical_configuration,
                lat = EXCLUDED.lat,
                lon = EXCLUDED.lon,
                altitude = EXCLUDED.altitude,
                address = EXCLUDED.address,
                capacity = EXCLUDED.capacity,
                is_charging_station = EXCLUDED.is_charging_station,
                rental_methods = EXCLUDED.rental_methods,
                groups_array = EXCLUDED.groups_array,
                obcn = EXCLUDED.obcn,
                short_name = EXCLUDED.short_name,
                nearby_distance = EXCLUDED.nearby_distance,
                ride_code_support = EXCLUDED.ride_code_support,
                updated_at = now();
            """,
            station,
        )


def load_stations():
    stations = fetch_station_information()

    with psycopg.connect(DATABASE_URL) as conn:
        create_stations_table(conn)
        for station in stations:
            upsert_station(conn, station)
        conn.commit()

    print(f"Loaded {len(stations)} stations into Postgres")


if __name__ == "__main__":
    load_stations()
