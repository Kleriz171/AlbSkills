"""Goal 1: read the atlas file format.  Goal 2: build objects from it.
Goal 3: check the file.  Bonus 3: report EVERY problem at once, plus deep checks."""

from atlas import Atlas, Pipe, Area, HEART
from graph import find_loops, describe_loop, reachable

# Rules live here, in one place, so a changed rule is a one-line change.
PIPE_SIZES = ('big', 'small')
FIELD_COUNTS = {'PIPE': 4, 'AREA': 5, 'BRIDGE': 3}      # how many fields each record type needs


class AtlasError(Exception):
    """A bad atlas file. 'messages' holds EVERY problem we found, not just the first."""

    def __init__(self, messages):
        super().__init__('\n'.join(messages))
        self.messages = messages


# ---------------------------------------------------------------- Goal 1: reading

def read_atlas_file(filename):
    records = []                                   # we will fill this list and return it

    with open(filename, encoding='utf-8-sig') as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()                     # remove spaces around the whole line

            if not line or line.startswith('#'):   # empty line or comment
                continue                           # skip it, go to the next line

            parts = [p.strip() for p in line.split('|')]   # cut at '|' and clean each piece
            records.append((lineno, parts))

    return records


def split_list(text):
    """'a, b ,c' -> ['a', 'b', 'c']"""
    return [item.strip() for item in text.split(',') if item.strip()]


# ------------------------------------------------- Goals 2 and 3: build and check

def load_atlas(filename):
    """Read the file, check it, build the objects.
    If anything is wrong it raises AtlasError listing ALL the problems.
    A bad file returns nothing, so the caller keeps its old atlas."""
    try:
        records = read_atlas_file(filename)
    except FileNotFoundError:
        raise AtlasError([f'File not found: {filename}'])
    if not records:
        raise AtlasError(['The file is empty.'])

    errors = []                                   # list of (line number or None, message)
    atlas, declared_pipes = build_objects(records, filename, errors)
    check_references(atlas, declared_pipes, filename, errors)
    check_heart(atlas, errors)

    if not errors:                                # deep checks need an otherwise sound atlas
        atlas.link()
        deep_checks(atlas, errors)

    if errors:
        errors.sort(key=lambda e: (e[0] is None, e[0] or 0))   # by line; general errors last
        raise AtlasError([message for _, message in errors])
    return atlas


def build_objects(records, filename, errors):
    """Pass 1: check each line on its own, then build the object.
    A bad line is reported and skipped; we keep going to find the other problems."""
    atlas = Atlas()
    first_seen = {}                               # name -> line where it was first defined
    declared_pipes = set()                        # every pipe name written, even on bad lines

    for lineno, parts in records:
        where = f'{filename}, line {lineno}'
        record_type = parts[0]

        if record_type not in FIELD_COUNTS:
            errors.append((lineno, f'{where}: unknown record type "{record_type}". '
                                   f'Expected PIPE, AREA or BRIDGE.'))
            if len(parts) > 1 and parts[1]:
                declared_pipes.add(parts[1])      # probably a typo'd pipe: avoid false errors
            continue
        if record_type == 'PIPE' and len(parts) > 1 and parts[1]:
            declared_pipes.add(parts[1])          # so one bad line does not cause many more
        if len(parts) != FIELD_COUNTS[record_type]:
            errors.append((lineno, f'{where}: {record_type} needs '
                                   f'{FIELD_COUNTS[record_type]} fields, found {len(parts)}.'))
            continue

        if record_type == 'BRIDGE':               # a bridge has no name of its own
            atlas.add_bridge(parts[1], parts[2], lineno)
            continue

        name = parts[1]
        if name in first_seen:
            errors.append((lineno, f'{where}: "{name}" is defined twice '
                                   f'(first on line {first_seen[name]}).'))
            continue
        first_seen[name] = lineno

        if record_type == 'PIPE':
            _, name, size, comes_from = parts
            if size not in PIPE_SIZES:
                errors.append((lineno, f'{where}: size must be big or small, found "{size}".'))
            atlas.add_pipe(Pipe(name, size, split_list(comes_from), lineno))
        else:
            _, name, fed_by, symptoms, description = parts
            atlas.add_area(Area(name, split_list(fed_by), split_list(symptoms),
                                description, lineno))
    return atlas, declared_pipes


def check_references(atlas, declared_pipes, filename, errors):
    """Pass 2: every pipe name that points to another pipe must exist."""
    for pipe in atlas.pipes.values():
        if pipe.comes_from == [HEART]:
            continue                              # the heart has no parent
        for parent in pipe.comes_from:
            if parent not in declared_pipes:
                errors.append((pipe.line, f'{filename}, line {pipe.line}: pipe "{pipe.name}" '
                                          f'comes from "{parent}", which does not exist.'))
    for area in atlas.areas.values():
        for feeder in area.fed_by:
            if feeder not in declared_pipes:
                errors.append((area.line, f'{filename}, line {area.line}: area "{area.name}" '
                                          f'is fed by "{feeder}", which does not exist.'))
    for bridge in atlas.bridges:
        where = f'{filename}, line {bridge.line}'
        for name in (bridge.first, bridge.second):
            if name not in declared_pipes:
                errors.append((bridge.line, f'{where}: bridge joins "{name}", '
                                            f'which does not exist.'))
        if bridge.first == bridge.second:
            errors.append((bridge.line, f'{where}: bridge joins "{bridge.first}" to itself.'))


def check_heart(atlas, errors):
    hearts = [p for p in atlas.pipes.values() if p.comes_from == [HEART]]
    if len(hearts) != 1:
        errors.append((None, f'The atlas needs exactly one pipe that comes from "{HEART}" '
                             f'(the heart). Found {len(hearts)}.'))


# ----------------------------------------------------------- Bonus 3: deep checks

def deep_checks(atlas, errors):
    """Loops, and pipes the heart can never reach. Runs only when the file is otherwise sound."""
    parents = {p.name: ([] if p.comes_from == [HEART] else p.comes_from)
               for p in atlas.pipes.values()}
    for loop in find_loops(parents):
        errors.append((None, 'Loop: ' + describe_loop(loop)))

    # blood can also cross a bridge, so a bridge counts as a way to reach a pipe
    edges = {p.name: [q.name for q in p.branches + p.bridged_to] for p in atlas.pipes.values()}
    reached = reachable(atlas.find_heart().name, edges)
    for pipe in atlas.pipes.values():
        if pipe.name not in reached:
            errors.append((None, f'Pipe "{pipe.name}" can never receive blood from the heart.'))


if __name__ == '__main__':
    # Manual check:  python loader.py
    for lineno, parts in read_atlas_file('data/atlas.txt'):
        print(lineno, parts)
