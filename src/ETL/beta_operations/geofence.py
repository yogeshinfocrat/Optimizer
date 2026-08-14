from shapely.geometry import Point, Polygon
from geopy.distance import geodesic
from concurrent.futures import ThreadPoolExecutor
import json

class GeoEngine:

    @staticmethod
    def check_circle(center_lat, center_lng, radius, lat, lng):
        return geodesic((center_lat, center_lng), (lat, lng)).meters <= radius

    @staticmethod
    def check_rectangle(prepared_polygon, point):
        return prepared_polygon.contains(point)

    @staticmethod
    def check_polygon(prepared_polygon, point):
        return prepared_polygon.contains(point)


def _check(emp, lat, lng, point):
    if emp["mode"] == "circle":
        if GeoEngine.check_circle(
            emp["center_lat"],
            emp["center_lng"],
            float(emp["radius"]),
            lat,
            lng
        ):
            return emp["EmployeeNo"]
    else:
        try:
            if emp["polygon"].contains(point):
                return emp["EmployeeNo"]
        except:
            pass
    return None


def get_inbound_parallel(processed_employees, lat, lng):
    point = Point(lng, lat)

    with ThreadPoolExecutor() as executor:
        results = executor.map(
            lambda e: _check(e, lat, lng, point),
            processed_employees
        )

    return [r for r in results if r]


def parse_json(val):
    """Handle string or dict safely"""
    if val is None:
        return None
    if isinstance(val, str):
        return json.loads(val)
    return val


def preprocess_from_df(df):
    processed = []

    for _, row in df.iterrows():
        mode = row["ModeType"]

        obj = {
            "EmployeeNo": row["EmployeeNo"],
            "mode": mode
        }

        # ---- CIRCLE ----
        if mode == "circle":
            if row["CircleCenter"]:
                center = parse_json(row["CircleCenter"])
            else:
                continue

            if center:
                obj["center_lat"] = center["lat"]
                obj["center_lng"] = center["lng"]
                obj["radius"] = row["CircleRadius"]

        # ---- RECTANGLE ----
        elif mode == "rectangle":
            if row["RectangleSouthWest"] and row["RectangleNorthEast"]:
                sw = parse_json(row["RectangleSouthWest"])
                ne = parse_json(row["RectangleNorthEast"])
            else:
                continue
            if sw and ne:
                polygon = Polygon([
                    (sw["lng"], sw["lat"]),
                    (sw["lng"], ne["lat"]),
                    (ne["lng"], ne["lat"]),
                    (ne["lng"], sw["lat"])
                ])
                obj["polygon"] = polygon

        # ---- POLYGON ----
        elif mode == "polygon":
            if row["PolygonLatLngArray"]:
                coords = parse_json(row["PolygonLatLngArray"])
            else:
                continue

            if coords:
                polygon = Polygon([(p["lng"], p["lat"]) for p in coords if len(p)])
                obj["polygon"] = polygon

        processed.append(obj)

    return processed