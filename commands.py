"""Goal 4: the commands that ask the atlas questions.

Each function receives the atlas and prints the answer.
A user mistake raises ValueError; synapse.py prints it as "ERROR: ...".
"""


import lesion


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


def show_tree(atlas):
    """Bonus 1: draw the atlas as an indented tree that starts at the heart."""
    seen = set()                       # names already printed in full
    print_pipe(atlas.find_heart(), 0, seen)


def print_pipe(pipe, depth, seen):
    indent = '    ' * depth            # 4 spaces for every level down
    if pipe.name in seen:
        print(f'{indent}{pipe.name} (see above)')
        return                         # do NOT print its children a second time
    seen.add(pipe.name)
    print(f'{indent}{pipe.name}')

    for branch in pipe.branches:       # the pipes that come out of this pipe
        print_pipe(branch, depth + 1, seen)
    for area in pipe.areas:            # the areas this pipe feeds
        print_area(area, depth + 1, seen)


def print_area(area, depth, seen):
    indent = '    ' * depth
    if area.name in seen:
        print(f'{indent}[{area.name}] (see above)')
        return
    seen.add(area.name)
    print(f'{indent}[{area.name}]')


def show_paths(atlas, name):
    """Bonus 2: print every route from the heart to an area."""
    if name not in atlas.areas:
        raise ValueError(f'No area called "{name}".')
    area = atlas.areas[name]
    routes = atlas.routes_to(area)

    noun = 'route' if len(routes) == 1 else 'routes'
    print(f'{len(routes)} {noun} from the heart to {area.name}:')
    for route in routes:
        print('   ' + ' > '.join(route + [area.name]))


def lesion_block(atlas, typed_name):
    """Mission 2, Goal 1: block one pipe and print what stops working."""
    if atlas.get_area(typed_name) and not atlas.get_pipe(typed_name):
        raise ValueError(f'"{typed_name}" is an area, not a pipe. Only pipes can be blocked.')
    pipe = atlas.get_pipe(typed_name)
    if pipe is None:
        raise ValueError(f'No pipe called "{typed_name}".')
    if pipe is atlas.find_heart():
        raise ValueError('The heart cannot be blocked.')

    result = lesion.simulate(atlas, [pipe])

    print(f'Blocked pipe: {pipe.name} ({pipe.size})')
    print(f'Pipes without blood ({len(result.dry_pipes)}): {names(result.dry_pipes)}')
    if not result.dead_areas:
        print('Areas that stop working (0): none')
        return
    print(f'Areas that stop working ({len(result.dead_areas)}):')
    width = max(len(area.name) for area in result.dead_areas)
    for area in result.dead_areas:
        print(f'  {area.name.ljust(width)}  {area.description}')
    print(f'Expected symptoms ({len(result.symptoms)}): {", ".join(result.symptoms)}')


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
