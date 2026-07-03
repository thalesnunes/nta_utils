import datetime as dt
import xml.etree.ElementTree as ET
from decimal import Decimal

from gpx import Extensions, GPX, Latitude, Longitude, Waypoint, read_gpx

GAP_THRESHOLD = 5
GARMIN_TPX_NS = "http://www.garmin.com/xmlschemas/TrackPointExtension/v1"


def _lerp(a: Decimal, b: Decimal, t: float, places: int = 7) -> Decimal:
    result = a + (b - a) * Decimal(str(t))
    return result.quantize(Decimal(10) ** -places)


def _build_hr_extension(hr: int) -> Extensions:
    tpx = ET.Element(f"{{{GARMIN_TPX_NS}}}TrackPointExtension")
    hr_el = ET.SubElement(tpx, f"{{{GARMIN_TPX_NS}}}hr")
    hr_el.text = str(hr)
    return Extensions(elements=[tpx])


def fill_gaps(
    input_path: str, output_path: str, gap_threshold: int = GAP_THRESHOLD
) -> dict:
    gpx = read_gpx(input_path)
    total_interpolated = 0

    for track in gpx.trk:
        for segment in track.trkseg:
            points = segment.trkpt
            if not points:
                continue

            new_points: list[Waypoint] = []
            last_known_hr: int | None = None
            i = 0

            while i < len(points):
                point = points[i]

                if point.extensions:
                    hr = point.extensions.get_int("hr", namespace=GARMIN_TPX_NS)
                    if hr is not None:
                        last_known_hr = hr

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

                            if point.extensions:
                                hr = point.extensions.get_int("hr", namespace=GARMIN_TPX_NS)
                                if hr is not None:
                                    last_known_hr = hr

                            for step in range(1, int(total_seconds)):
                                t = step / total_seconds
                                interp_time = point.time + dt.timedelta(seconds=step)

                                extensions = (
                                    _build_hr_extension(last_known_hr)
                                    if last_known_hr is not None
                                    else None
                                )

                                new_points.append(
                                    Waypoint(
                                        lat=Latitude(_lerp(Decimal(str(point.lat)), Decimal(str(target.lat)), t)),
                                        lon=Longitude(_lerp(Decimal(str(point.lon)), Decimal(str(target.lon)), t)),
                                        ele=_lerp(point.ele, target.ele, t),
                                        time=interp_time,
                                        extensions=extensions,
                                    )
                                )
                                total_interpolated += 1

                            new_points.append(
                                Waypoint(
                                    lat=Latitude(target.lat),
                                    lon=Longitude(target.lon),
                                    ele=target.ele,
                                    time=target.time,
                                    extensions=target.extensions,
                                )
                            )

                            if target.extensions:
                                hr = target.extensions.get_int("hr", namespace=GARMIN_TPX_NS)
                                if hr is not None:
                                    last_known_hr = hr

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

    gpx.write_gpx(output_path)
    return {"interpolated": total_interpolated}
