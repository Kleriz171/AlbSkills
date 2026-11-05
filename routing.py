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


# ------------------------------------------------------- Goal 3: choose a hospital

DRUG_AFTER_ARRIVAL = 30     # minutes from arrival to the drug (fixed by the PDF)
CLOT_AFTER_ARRIVAL = 60     # minutes from arrival to clot removal (fixed by the PDF)
TRANSFER_AFTER_ARRIVAL = 45     # Bonus 1: the transfer leaves the first hospital this long after arrival
CLOT_AFTER_TRANSFER = 30        # Bonus 1: from arrival at the second hospital to clot removal


class FirstStop:
    """Bonus 1: the hospital where the drug is given before the transfer."""

    def __init__(self, route, arrives, drug_at):
        self.hospital = route.hospital
        self.path = route.path
        self.drive = route.minutes
        self.arrives = arrives
        self.drug_at = drug_at


class Plan:
    """Where the ambulance goes and when each step happens (minutes on the case timeline).
    For a transfer plan, hospital/path/drive/leaves/arrives describe the LAST leg: the trip
    from the first hospital to the clot removal hospital."""

    def __init__(self, goal, route, leaves, drug_at, clot_at, stop=None):
        self.goal = goal                    # 'clot', 'drug' or 'scan': the best treatment chosen
        self.hospital = route.hospital
        self.path = route.path
        self.drive = route.minutes
        self.leaves = leaves
        self.arrives = leaves + route.minutes
        self.drug_at = drug_at              # None when the drug is not given here
        self.clot_at = clot_at              # None when there is no clot removal
        self.stop = stop                    # a FirstStop for a transfer plan, else None


class Decision:
    """The answer: the chosen plan, and the two plans that were compared (Bonus 1)."""

    def __init__(self, chosen, straight, transfer=None, reason=''):
        self.chosen = chosen
        self.straight = straight            # Plan A (straight to the best hospital)
        self.transfer = transfer            # Plan B (drug first, then transfer), or None
        self.reason = reason                # why the chosen plan won


def plan_route(case, roads, hospitals):
    """Choose the hospital for a case. Raises ValueError with a message for the user.

    The case already says which treatments are still possible (clot_possible,
    drug_possible, computed in Mission 3). We try the best one first: clot removal,
    then the drug, then a scan. For each, a hospital counts only if it can do it AND
    the patient gets it in time. Among those, the fastest to reach wins; equally fast
    hospitals keep the order of hospitals.txt.

    Bonus 1: a patient who needs clot removal has a second option, Plan B."""
    start = find_city(roads, case.city)
    if start is None:
        raise ValueError(f'The city of case {case.id}, "{case.city}", is not on the map.')
    routes = hospital_routes(roads, hospitals, start)            # fastest first
    if not routes:
        raise ValueError(f'No road leads from {start} to any hospital.')

    leaves = case.created                      # the ambulance leaves when the case was created

    def drug_in_time(route):
        return (case.drug_possible and route.hospital.can('DRUG')
                and leaves + route.minutes + DRUG_AFTER_ARRIVAL <= case.drug_until)

    def clot_in_time(route):
        return (case.clot_possible and route.hospital.can('CLOT')
                and leaves + route.minutes + CLOT_AFTER_ARRIVAL <= case.clot_until)

    for route in routes:
        if clot_in_time(route):
            arrives = leaves + route.minutes
            drug_at = arrives + DRUG_AFTER_ARRIVAL if drug_in_time(route) else None
            straight = Plan('clot', route, leaves, drug_at, arrives + CLOT_AFTER_ARRIVAL)
            return compare_plans(straight, plan_transfer(case, roads, hospitals, routes, leaves))
    for route in routes:
        if drug_in_time(route):
            plan = Plan('drug', route, leaves, leaves + route.minutes + DRUG_AFTER_ARRIVAL, None)
            return Decision(plan, plan)
    for route in routes:
        if route.hospital.can('CT'):
            plan = Plan('scan', route, leaves, None, None)
            return Decision(plan, plan)
    raise ValueError(f'No hospital with a CT can be reached from {start}.')


# ------------------------------------------------- Bonus 1: drug first, then transfer

def plan_transfer(case, roads, hospitals, routes, leaves):
    """Plan B: drive to the fastest hospital that can give the drug IN TIME, give it,
    then transfer to the fastest clot removal hospital that is still in time.
    Returns a Plan, or None when there is no such plan."""
    if not (case.clot_possible and case.drug_possible):
        return None
    first = None
    for route in routes:                                  # fastest first
        arrives = leaves + route.minutes
        if route.hospital.can('DRUG') and arrives + DRUG_AFTER_ARRIVAL <= case.drug_until:
            first = route
            break
    if first is None or first.hospital.can('CLOT'):       # nothing to transfer to, or no transfer needed
        return None

    arrives_first = leaves + first.minutes
    stop = FirstStop(first, arrives_first, arrives_first + DRUG_AFTER_ARRIVAL)
    transfer_leaves = arrives_first + TRANSFER_AFTER_ARRIVAL

    # the same road search, started from the first hospital's city
    for route in hospital_routes(roads, hospitals, first.hospital.city):
        if not route.hospital.can('CLOT') or route.hospital is first.hospital:
            continue
        clot_at = transfer_leaves + route.minutes + CLOT_AFTER_TRANSFER
        if clot_at <= case.clot_until:                    # the exact limit still counts
            return Plan('clot', route, transfer_leaves, stop.drug_at, clot_at, stop)
    return None


def compare_plans(straight, transfer):
    """The rule from the PDF: if only one plan gives the drug in time, choose it.
    Otherwise choose the plan with the earlier clot removal (a tie goes to Plan A)."""
    if transfer is None:
        return Decision(straight, straight)
    a_drug = straight.drug_at is not None
    b_drug = transfer.drug_at is not None
    if a_drug != b_drug:
        chosen = straight if a_drug else transfer
        reason = 'Only this plan gives the drug in time.'
    elif transfer.clot_at < straight.clot_at:
        chosen = transfer
        reason = f'The clot is removed {straight.clot_at - transfer.clot_at} min sooner.'
    else:
        chosen = straight
        reason = ('Both plans give the drug in time, and Plan A removes the clot '
                  f'{transfer.clot_at - straight.clot_at} min sooner.' if a_drug else
                  'Plan A removes the clot sooner.')
    return Decision(chosen, straight, transfer, reason)


# ------------------------------------------------------- Bonus 2: coverage report

FAR_LIMIT = 120             # clot removal further than this many minutes is marked FAR (the PDF)


def nearest(routes, ability):
    """The first route (fastest, then hospitals.txt order) to a hospital that has the ability."""
    for route in routes:
        if route.hospital.can(ability):
            return route
    return None


def coverage(roads, hospitals):
    """Bonus 2: for every city, the nearest drug hospital and the nearest clot removal hospital.
    Returns [(city, drug route or None, clot route or None)] in the order of roads.txt.

    One shortest-path search per city (hospital_routes), asked both questions at once:
    a few milliseconds even for hundreds of cities. It is the same function route from
    uses, so the report can never disagree with it."""
    rows = []
    for city in roads.cities:
        routes = hospital_routes(roads, hospitals, city)
        rows.append((city, nearest(routes, 'DRUG'), nearest(routes, 'CLOT')))
    return rows


def is_far(clot_route):
    """No clot removal hospital at all counts as far."""
    return clot_route is None or clot_route.minutes > FAR_LIMIT


# ------------------------------------------------------------ Bonus 3: what if?

def with_ability(hospitals, chosen, ability):
    """A COPY of the hospital list in which 'chosen' can also do 'ability'.
    The real list (and hospitals.txt) is never changed."""
    from roadmap import Hospital
    changed = []
    for hospital in hospitals:
        if hospital is chosen:
            hospital = Hospital(hospital.name, hospital.city,
                                hospital.abilities + [ability], hospital.line)
        changed.append(hospital)
    return changed


def clot_drive(roads, hospitals, city):
    """Minutes to the nearest clot removal hospital from this city, or None."""
    route = nearest(hospital_routes(roads, hospitals, city), 'CLOT')
    return None if route is None else route.minutes
