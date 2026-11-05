"""Mission 4, Goal 2: drive times and routes over the road network.

Everything comes from the loaded roads and hospitals. The only numbers written here
are the fixed times from the PDF.
"""

import heapq

LOCAL_DRIVE = 10            # minutes to a hospital in the patient's own city (fixed by the PDF)


class HospitalRoute:
    """How to reach one hospital from a starting city."""

    def __init__(self, hospital, minutes, path):
        self.hospital = hospital
        self.minutes = minutes          # drive time
        self.path = path                # cities on the way, first = start city, last = hospital city


def find_city(roads, typed):
    """The map's own spelling of a city, found ignoring upper/lower case. None if unknown."""
    typed = typed.strip().lower()
    for city in roads.cities:
        if city.lower() == typed:
            return city
    return None


def shortest_paths(roads, start):
    """Dijkstra: the fastest drive time from 'start' to every city, and the road taken.

    Always settle the closest unsettled city next. Because every road time is above 0,
    once a city is settled nothing can reach it faster. A road may be a detour that is
    still quicker: Fier -> Durres -> Tirana (110) beats any direct road we do not have.

    Returns (minutes, came_from):  came_from[city] = the city we drove from."""
    order = {city: i for i, city in enumerate(roads.cities)}
    minutes = {start: 0}
    came_from = {}
    queue = [(0, order[start], start)]                  # (minutes, file order, city)
    settled = set()

    while queue:
        spent, _, city = heapq.heappop(queue)
        if city in settled:
            continue                                    # an older, slower entry
        settled.add(city)
        for neighbour, road_minutes in roads.links[city].items():
            total = spent + road_minutes
            if neighbour not in minutes or total < minutes[neighbour]:   # strictly faster only
                minutes[neighbour] = total
                came_from[neighbour] = city
                heapq.heappush(queue, (total, order[neighbour], neighbour))
    return minutes, came_from


def path_to(came_from, start, target):
    """Walk back from the target to the start, then reverse: ['Fier', 'Durres', 'Tirana']."""
    path = [target]
    while path[-1] != start:
        path.append(came_from[path[-1]])
    path.reverse()
    return path


def hospital_routes(roads, hospitals, start):
    """Every reachable hospital with its drive time and path, fastest first.
    Equally fast hospitals keep the order of hospitals.txt (sorted() is stable)."""
    minutes, came_from = shortest_paths(roads, start)
    found = []
    for hospital in hospitals:                          # file order
        if hospital.city == start:
            found.append(HospitalRoute(hospital, LOCAL_DRIVE, [start]))
        elif hospital.city in minutes:
            found.append(HospitalRoute(hospital, minutes[hospital.city],
                                       path_to(came_from, start, hospital.city)))
    return sorted(found, key=lambda route: route.minutes)
