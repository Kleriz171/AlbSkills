"""Mission 4, Goal 1: read the two map files (same format as the atlas).

  roads.txt      ROAD | city | city | minutes
  hospitals.txt  HOSPITAL | name | city | can do (CT, DRUG, CLOT)

Nothing about the map is written in the code: cities, roads, hospitals and what
each hospital can do all come from the files, so a roads-v2.txt or hospitals-v2.txt
works without any change.
"""

import os

from loader import read_atlas_file, split_list

# The rules of the format, in one place.
ABILITIES = ('CT', 'DRUG', 'CLOT')
ROAD_FIELDS = 4
HOSPITAL_FIELDS = 4


class MapError(Exception):
    """A bad map file. 'messages' holds EVERY problem we found, not just the first."""

    def __init__(self, messages):
        super().__init__('\n'.join(messages))
        self.messages = messages


class Roads:
    """The road network. Roads go both ways with the same drive time."""

    def __init__(self):
        self.links = {}                     # city -> {neighbour city: minutes}
        self.cities = []                    # every city, in the order the file first names it

    def add(self, first, second, minutes):
        for city in (first, second):
            if city not in self.links:
                self.links[city] = {}
                self.cities.append(city)
        self.links[first][second] = minutes
        self.links[second][first] = minutes

    def has_road_between(self, first, second):
        return second in self.links.get(first, {})

    def road_count(self):
        return sum(len(neighbours) for neighbours in self.links.values()) // 2


class Hospital:
    def __init__(self, name, city, abilities, line):
        self.name = name
        self.city = city
        self.abilities = abilities          # e.g. ['CT', 'DRUG'], in the order written
        self.line = line

    def can(self, ability):
        return ability in self.abilities


# ---------------------------------------------------------------- reading

def read_records(filename):
    """The file's records, or a MapError if it is missing or has none."""
    try:
        records = read_atlas_file(filename)         # skips comments and empty lines
    except FileNotFoundError:
        raise MapError([f'File not found: {filename}'])
    except UnicodeDecodeError:
        raise MapError([f'{filename} is not a text file.'])
    if not records:
        raise MapError(['The file is empty.'])
    return records


def kind_of_file(records, filename):
    """'roads' or 'hospitals', decided by the first record in the file."""
    first = records[0][1][0]
    if first == 'ROAD':
        return 'roads'
    if first == 'HOSPITAL':
        return 'hospitals'
    raise MapError([f'{os.path.basename(filename)}, line {records[0][0]}: unknown record type '
                    f'"{first}". Expected ROAD or HOSPITAL.'])


# ------------------------------------------------------------------ roads

def load_roads(filename, hospitals=(), hospitals_file=''):
    """Read, check and build the road network. Raises MapError listing ALL problems.

    'hospitals' are the hospitals already loaded: a new road file must not leave one
    of them in a city that has no road any more."""
    return build_roads(read_records(filename), filename, hospitals, hospitals_file)


def build_roads(records, filename, hospitals=(), hospitals_file=''):
    name = os.path.basename(filename)
    roads = Roads()
    errors = []                                     # (line number, message)
    seen = {}                                       # frozenset of two cities -> first line

    for lineno, parts in records:
        where = f'{name}, line {lineno}'
        if parts[0] != 'ROAD':
            errors.append((lineno, f'{where}: unknown record type "{parts[0]}". Expected ROAD.'))
            continue
        if len(parts) != ROAD_FIELDS:
            errors.append((lineno, f'{where}: ROAD needs {ROAD_FIELDS} fields, found {len(parts)}.'))
            continue

        _, first, second, minutes_text = parts
        if not first or not second:
            errors.append((lineno, f'{where}: a road needs two city names.'))
            continue
        if first == second:
            errors.append((lineno, f'{where}: the road joins {first} to itself.'))
            continue
        if not (minutes_text.isascii() and minutes_text.isdigit()) or int(minutes_text) == 0:
            errors.append((lineno, f'{where}: minutes must be a whole number above 0, '
                                   f'found "{minutes_text}".'))
            continue
        pair = frozenset((first, second))
        if pair in seen:                            # a road goes both ways, so B-A is A-B too
            errors.append((lineno, f'{where}: the road {first} - {second} is listed twice '
                                   f'(first on line {seen[pair]}).'))
            continue
        seen[pair] = lineno
        roads.add(first, second, int(minutes_text))

    if not errors:                                  # only a sound road file can be judged against hospitals
        for hospital in hospitals:
            if hospital.city not in roads.links:
                errors.append((None, f'{hospitals_file or "hospitals"}, line {hospital.line}: '
                                     f'city "{hospital.city}" would no longer be on any road.'))
    if errors:
        raise MapError(sorted_messages(errors))
    return roads


# -------------------------------------------------------------- hospitals

def load_hospitals(filename, roads):
    """Read, check and build the hospital list. Raises MapError listing ALL problems."""
    return build_hospitals(read_records(filename), filename, roads)


def build_hospitals(records, filename, roads):
    name = os.path.basename(filename)
    hospitals = []
    errors = []
    first_seen = {}                                 # hospital name -> line

    for lineno, parts in records:
        where = f'{name}, line {lineno}'
        if parts[0] != 'HOSPITAL':
            errors.append((lineno, f'{where}: unknown record type "{parts[0]}". Expected HOSPITAL.'))
            continue
        if len(parts) != HOSPITAL_FIELDS:
            errors.append((lineno, f'{where}: HOSPITAL needs {HOSPITAL_FIELDS} fields, '
                                   f'found {len(parts)}.'))
            continue

        _, hospital_name, city, abilities_text = parts
        abilities = split_list(abilities_text)
        problems = []
        if not hospital_name:
            problems.append('the hospital name is empty.')
        elif hospital_name in first_seen:
            problems.append(f'"{hospital_name}" is defined twice (first on line '
                            f'{first_seen[hospital_name]}).')
        if city not in roads.links:
            problems.append(f'city "{city}" is not on any road.')
        for ability in abilities:
            if ability not in ABILITIES:
                problems.append(f'unknown ability "{ability}". Expected '
                                f'{", ".join(ABILITIES[:-1])} or {ABILITIES[-1]}.')
        if not abilities:
            problems.append('a hospital must be able to do at least one thing.')
        if 'DRUG' in abilities and 'CT' not in abilities:
            problems.append('a hospital that gives the DRUG must also have CT.')

        for problem in problems:
            errors.append((lineno, f'{where}: {problem}'))
        if hospital_name and hospital_name not in first_seen:
            first_seen[hospital_name] = lineno
        if not problems:
            hospitals.append(Hospital(hospital_name, city, unique(abilities), lineno))

    if errors:
        raise MapError(sorted_messages(errors))
    return hospitals


def unique(items):
    result = []
    for item in items:
        if item not in result:
            result.append(item)
    return result


def sorted_messages(errors):
    """By line number; problems that belong to no single line go last."""
    errors.sort(key=lambda e: (e[0] is None, e[0] or 0))
    return [message for _, message in errors]
