"""Goal 4: the commands that ask the atlas questions.

Each function receives the atlas and prints the answer.
A user mistake raises ValueError; synapse.py prints it as "ERROR: ...".
"""


def print_table(header, rows):
    """Print rows in aligned columns. Each column is as wide as its longest cell."""
    all_rows = [header] + rows
    widths = [max(len(row[i]) for row in all_rows) for i in range(len(header))]
    for row in all_rows:
        cells = [cell.ljust(widths[i]) for i, cell in enumerate(row)]
        print('  '.join(cells).rstrip())


def names(items):
    """[pipe, pipe] -> 'name1, name2'   (or 'none' when the list is empty)"""
    return ', '.join(item.name for item in items) or 'none'


def show_pipes(atlas):
    rows = [[p.name, p.size, ', '.join(p.comes_from)] for p in atlas.pipes.values()]
    print_table(['NAME', 'SIZE', 'COMES FROM'], rows)
    print(f'{len(rows)} pipes')


def show_areas(atlas):
    rows = [[a.name, ', '.join(a.fed_by)] for a in atlas.areas.values()]
    print_table(['NAME', 'FED BY'], rows)
    print(f'{len(rows)} areas')


def show_one(atlas, name):
    if name in atlas.pipes:
        pipe = atlas.pipes[name]
        print(f'Pipe: {pipe.name}')
        print(f'Size:           {pipe.size}')
        print(f'Comes from:     {", ".join(pipe.comes_from)}')
        print(f'Branches into:  {names(pipe.branches)}')
        print(f'Feeds areas:    {names(pipe.areas) if pipe.areas else "none directly"}')
    elif name in atlas.areas:
        area = atlas.areas[name]
        print(f'Area: {area.name}')
        print(f'What it does:   {area.description}')
        print(f'Fed by:         {", ".join(area.fed_by)}')
        print(f'If it stops:    {", ".join(area.symptoms)}')
    else:
        raise ValueError(f'No pipe or area called "{name}".')


def find(atlas, word):
    matches = atlas.find_areas(word)
    if not matches:
        print(f'No areas match "{word}".')
        return
    if len(matches) == 1:
        print(f'1 area matches "{word}":')
    else:
        print(f'{len(matches)} areas match "{word}":')
    width = max(len(area.name) for area in matches)
    for area in matches:
        print(f'  {area.name.ljust(width)}  {area.description}')
