"""Goal 1: read the atlas file format.  Goal 2: build objects from it."""

from atlas import Atlas, Pipe, Area


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
    """Goal 2: read the file (Goal 1), then build the objects from the records."""
    atlas = Atlas()

    for lineno, parts in read_atlas_file(filename):
        if parts[0] == 'PIPE':
            _, name, size, comes_from = parts
            atlas.add_pipe(Pipe(name, size, split_list(comes_from), lineno))
        elif parts[0] == 'AREA':
            _, name, fed_by, symptoms, description = parts
            atlas.add_area(Area(name, split_list(fed_by), split_list(symptoms),
                                description, lineno))

    atlas.link()
    return atlas


if __name__ == '__main__':
    for lineno, parts in read_atlas_file('data/atlas.txt'):
        print(lineno, parts)
