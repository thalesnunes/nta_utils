import datetime as dt
import xml.etree.ElementTree as ET
from decimal import Decimal

from gpx import Extensions, GPX, Latitude, Longitude, Waypoint, read_gpx

GAP_THRESHOLD = 1
GARMIN_TPX_NS = "http://www.garmin.com/xmlschemas/TrackPointExtension/v1"
ELE_SMOOTH_WINDOW = 5


def _lerp(a: Decimal, b: Decimal, t: float, places: int = 7) -> Decimal:
    result = a + (b - a) * Decimal(str(t))
    return result.quantize(Decimal(10) ** -places)


def _build_extension(hr: int | None = None, cad: int | None = None) -> Extensions | None:
    if hr is None and cad is None:
        return None
    tpx = ET.Element(f"{{{GARMIN_TPX_NS}}}TrackPointExtension")
    if hr is not None:
        hr_el = ET.SubElement(tpx, f"{{{GARMIN_TPX_NS}}}hr")
        hr_el.text = str(hr)
    if cad is not None:
        cad_el = ET.SubElement(tpx, f"{{{GARMIN_TPX_NS}}}cad")
        cad_el.text = str(cad)
    return Extensions(elements=[tpx])


def _get_hr(waypoint: Waypoint) -> int | None:
    if waypoint.extensions is None:
        return None
    return waypoint.extensions.get_int("hr", namespace=GARMIN_TPX_NS)


def _get_cad(waypoint: Waypoint) -> int | None:
    if waypoint.extensions is None:
        return None
    return waypoint.extensions.get_int("cad", namespace=GARMIN_TPX_NS)


def _interpolate_missing(values: list[int | None]) -> list[int | None]:
    """Linearly interpolate None gaps between known values."""
    result = list(values)
    n = len(result)

    for i in range(n):
        if result[i] is not None:
            continue

        # Find previous known
        prev_idx = None
        for j in range(i - 1, -1, -1):
            if result[j] is not None:
                prev_idx = j
                break

        # Find next known
        next_idx = None
        for j in range(i + 1, n):
            if result[j] is not None:
                next_idx = j
                break

        if prev_idx is not None and next_idx is not None:
            span = next_idx - prev_idx
            for k in range(prev_idx + 1, next_idx):
                t = (k - prev_idx) / span
                result[k] = round(result[prev_idx] * (1 - t) + result[next_idx] * t)
        elif prev_idx is not None:
            result[i] = result[prev_idx]
        elif next_idx is not None:
            result[i] = result[next_idx]

    return result


def _smooth_elevation(eles: list[float | None], window: int = ELE_SMOOTH_WINDOW) -> list[float | None]:
    """Simple moving average to smooth barometric noise."""
    result = list(eles)
    n = len(result)
    half = window // 2

    for i in range(n):
        if result[i] is None:
            continue
        start = max(0, i - half)
        end = min(n, i + half + 1)
        vals = [result[j] for j in range(start, end) if result[j] is not None]
        if vals:
            result[i] = round(sum(vals) / len(vals), 1)

    return result


def fill_gaps(
    input_path: str, output_path: str, gap_threshold: int = GAP_THRESHOLD
) -> dict:
    gpx = read_gpx(input_path)
    total_interpolated = 0

    for track in gpx.trk:
        track.type = "running"

        for segment in track.trkseg:
            points = segment.trkpt
            if not points:
                continue

            # Pass 1: Fill gaps in lat/lon/time
            new_points: list[Waypoint] = []
            i = 0

            while i < len(points):
                point = points[i]

                if i + 1 < len(points):
                    gap = (points[i + 1].time - point.time).total_seconds()

                    if gap > gap_threshold:
                        old_lat = str(point.lat)
                        old_lon = str(point.lon)

                        dead_end = i + 1
                        while dead_end < len(points) and str(points[dead_end].lat) == old_lat and str(points[dead_end].lon) == old_lon:
                            dead_end += 1

                        if dead_end < len(points):
                            target = points[dead_end]
                            total_seconds = (target.time - point.time).total_seconds()

                            # Append the point before the gap
                            new_points.append(
                                Waypoint(
                                    lat=Latitude(point.lat),
                                    lon=Longitude(point.lon),
                                    ele=point.ele,
                                    time=point.time,
                                    extensions=point.extensions,
                                )
                            )

                            for step in range(1, int(total_seconds)):
                                t = step / total_seconds
                                interp_time = point.time + dt.timedelta(seconds=step)

                                new_points.append(
                                    Waypoint(
                                        lat=Latitude(_lerp(Decimal(str(point.lat)), Decimal(str(target.lat)), t)),
                                        lon=Longitude(_lerp(Decimal(str(point.lon)), Decimal(str(target.lon)), t)),
                                        ele=_lerp(point.ele, target.ele, t),
                                        time=interp_time,
                                    )
                                )
                                total_interpolated += 1

                            i = dead_end
                            continue

                new_points.append(
                    Waypoint(
                        lat=Latitude(point.lat),
                        lon=Longitude(point.lon),
                        ele=point.ele,
                        time=point.time,
                        extensions=point.extensions,
                    )
                )
                i += 1

            segment.trkpt = new_points

            # Pass 2: Smooth elevation
            eles = [p.ele for p in segment.trkpt]
            smoothed = _smooth_elevation(eles)
            for p, e in zip(segment.trkpt, smoothed):
                p.ele = e

            # Pass 3: Interpolate missing HR across all points
            hrs = [_get_hr(p) for p in segment.trkpt]
            filled_hrs = _interpolate_missing(hrs)

            # Pass 4: Interpolate missing cadence across all points
            cads = [_get_cad(p) for p in segment.trkpt]
            filled_cads = _interpolate_missing(cads)

            # Rebuild extensions with interpolated HR + cadence
            for p, hr, cad in zip(segment.trkpt, filled_hrs, filled_cads):
                p.extensions = _build_extension(hr=hr, cad=cad)

    gpx.write_gpx(output_path)
    return {"interpolated": total_interpolated}
