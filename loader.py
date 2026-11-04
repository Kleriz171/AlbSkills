"""Goal 1: read the atlas file format.  Goal 2: build objects from it."""

from atlas import Atlas, Pipe, Area, HEART

# Goal 3 rules. They live here, in one place, so a changed rule is a one-line change.
PIPE_SIZES = ('big', 'small')
FIELD_COUNTS = {'PIPE': 4, 'AREA': 5}      # how many fields each record type needs


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


def load_atlas(filename):
    """Goal 2 + 3: read the file, check it, build the objects.
    On the first problem it raises ValueError with a clear message.
    Nothing is returned for a bad file, so the caller keeps its old atlas."""
    try:
        records = read_atlas_file(filename)
    except FileNotFoundError:
        raise ValueError(f'File not found: {filename}')
    if not records:
        raise ValueError('The file is empty.')

    atlas = Atlas()
    first_seen = {}                                   # name -> line where it was first defined

    # --- pass 1: check each line on its own, then build the object ---
    for lineno, parts in records:
        where = f'{filename}, line {lineno}'
        record_type = parts[0]

        if record_type not in FIELD_COUNTS:
            raise ValueError(f'{where}: unknown record type "{record_type}". '
                             f'Expected PIPE or AREA.')
        if len(parts) != FIELD_COUNTS[record_type]:
            raise ValueError(f'{where}: {record_type} needs {FIELD_COUNTS[record_type]} '
                             f'fields, found {len(parts)}.')

        name = parts[1]
        if name in first_seen:
            raise ValueError(f'{where}: "{name}" is defined twice '
                             f'(first on line {first_seen[name]}).')
        first_seen[name] = lineno

        if record_type == 'PIPE':
            _, name, size, comes_from = parts
            if size not in PIPE_SIZES:
                raise ValueError(f'{where}: size must be big or small, found "{size}".')
            atlas.add_pipe(Pipe(name, size, split_list(comes_from), lineno))
        else:
            _, name, fed_by, symptoms, description = parts
            atlas.add_area(Area(name, split_list(fed_by), split_list(symptoms),
                                description, lineno))

    # --- pass 2: now that every line is read, check the names that point to other pipes ---
    for pipe in atlas.pipes.values():
        if pipe.comes_from == [HEART]:
            continue                                  # the heart has no parent
        for parent in pipe.comes_from:
            if parent not in atlas.pipes:
                raise ValueError(f'{filename}, line {pipe.line}: pipe "{pipe.name}" '
                                 f'comes from "{parent}", which does not exist.')
    for area in atlas.areas.values():
        for feeder in area.fed_by:
            if feeder not in atlas.pipes:
                raise ValueError(f'{filename}, line {area.line}: area "{area.name}" '
                                 f'is fed by "{feeder}", which does not exist.')

    hearts = [p for p in atlas.pipes.values() if p.comes_from == [HEART]]
    if len(hearts) != 1:
        raise ValueError(f'The atlas needs exactly one pipe that comes from "{HEART}" '
                         f'(the heart). Found {len(hearts)}.')

    atlas.link()
    return atlas


if __name__ == '__main__':
    for lineno, parts in read_atlas_file('data/atlas.txt'):
        print(lineno, parts)
