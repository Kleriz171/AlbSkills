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
        if pipe.bridged_to:
            print(f'Bridged to:     {names(pipe.bridged_to)}')
    elif name in atlas.areas:
        area = atlas.areas[name]
        print(f'Area: {area.name}')
        print(f'What it does:   {area.description}')
        print(f'Fed by:         {", ".join(area.fed_by)}')
        print(f'If it stops:    {", ".join(area.symptoms)}')
    else:
        raise ValueError(f'No pipe or area called "{name}".')


def tree_lines(atlas, indent_size, mark_pipe=None, mark_area=None):
    """Draw the atlas as an indented tree that starts at the heart.
    Returns a list of (text, mark) pairs. 'mark' is an optional note for the
    right-hand side (used by lesion tree); show_tree ignores it."""
    lines = []
    seen = set()                       # names already written in full

    def add_pipe(pipe, depth):
        indent = ' ' * indent_size * depth
        if pipe.name in seen:
            lines.append((f'{indent}{pipe.name} (see above)', ''))
            return                     # do NOT repeat its children
        seen.add(pipe.name)
        lines.append((f'{indent}{pipe.name}', mark_pipe(pipe) if mark_pipe else ''))
        for branch in pipe.branches:   # the pipes that come out of this pipe
            add_pipe(branch, depth + 1)
        for area in pipe.areas:        # the areas this pipe feeds
            add_area(area, depth + 1)

    def add_area(area, depth):
        indent = ' ' * indent_size * depth
        if area.name in seen:
            lines.append((f'{indent}[{area.name}] (see above)', ''))
            return
        seen.add(area.name)
        lines.append((f'{indent}[{area.name}]', mark_area(area) if mark_area else ''))

    add_pipe(atlas.find_heart(), 0)
    return lines


def show_tree(atlas):
    """Mission 1, Bonus 1: atlas tree."""
    for text, _ in tree_lines(atlas, 4):
        print(text)


def lesion_tree(atlas, typed_text):
    """Mission 2, Bonus 3: the tree, marking what the blocked pipe(s) affect."""
    pipes = pipes_to_block(atlas, typed_text, 'lesion tree <pipe>')
    result = lesion.simulate(atlas, pipes)
    dry = {pipe.name for pipe in result.dry_pipes}
    dead = {area.name for area in result.dead_areas}

    def mark_pipe(pipe):
        if pipe in pipes:
            return 'BLOCKED'
        return 'no blood' if pipe.name in dry else ''

    def mark_area(area):
        return 'stops working' if area.name in dead else ''

    lines = tree_lines(atlas, 2, mark_pipe, mark_area)
    width = max(len(text) for text, _ in lines) + 2       # one column for all the marks
    for text, mark in lines:
        print(f'{text.ljust(width)}{mark}'.rstrip())


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


def pipe_to_block(atlas, typed_name):
    """Check one typed name and return the Pipe, or raise a clear error."""
    if atlas.get_area(typed_name) and not atlas.get_pipe(typed_name):
        raise ValueError(f'"{typed_name}" is an area, not a pipe. Only pipes can be blocked.')
    pipe = atlas.get_pipe(typed_name)
    if pipe is None:
        raise ValueError(f'No pipe called "{typed_name}".')
    if pipe is atlas.find_heart():
        raise ValueError('The heart cannot be blocked.')
    return pipe


def pipes_to_block(atlas, typed_text, usage):
    """Turn 'a, b' into a list of Pipe objects. Every name is checked first."""
    typed_names = [name.strip() for name in typed_text.split(',') if name.strip()]
    if not typed_names:
        raise ValueError(f'Missing pipe. Usage: {usage}')
    pipes = []
    for typed_name in typed_names:
        pipe = pipe_to_block(atlas, typed_name)
        if pipe not in pipes:                     # "a, a" blocks the pipe once
            pipes.append(pipe)
    return pipes


def lesion_block(atlas, typed_text):
    """Mission 2: block one pipe, or several separated by commas, and print the result."""
    pipes = pipes_to_block(atlas, typed_text, 'lesion block <pipe>')
    result = lesion.simulate(atlas, pipes)

    if len(pipes) == 1:
        print(f'Blocked pipe: {pipes[0].name} ({pipes[0].size})')
    else:
        print(f'Blocked pipes: {names(pipes)}')
    print(f'Pipes without blood ({len(result.dry_pipes)}): {names(result.dry_pipes)}')

    if not result.dead_areas:
        print('Areas that stop working (0): none')
    else:
        if len(pipes) == 1:                       # one pipe: a table with descriptions
            print(f'Areas that stop working ({len(result.dead_areas)}):')
            width = max(len(area.name) for area in result.dead_areas)
            for area in result.dead_areas:
                print(f'  {area.name.ljust(width)}  {area.description}')
        else:                                     # several pipes: one line, as in the PDF
            print(f'Areas that stop working ({len(result.dead_areas)}): '
                  f'{names(result.dead_areas)}')
        print(f'Expected symptoms ({len(result.symptoms)}): {", ".join(result.symptoms)}')

    if result.saved:                              # Bonus 2: pipes a bridge kept alive
        parts = [f'{pipe.name} (from {names(givers)})' for pipe, givers in result.saved]
        print(f'Saved by a bridge: {", ".join(parts)}')


def lesion_risk(atlas, typed_name):
    """Mission 2, Goal 2: which single blocked pipes would stop this area?"""
    if atlas.get_pipe(typed_name) and not atlas.get_area(typed_name):
        raise ValueError(f'"{typed_name}" is a pipe, not an area. Usage: lesion risk <area>')
    area = atlas.get_area(typed_name)
    if area is None:
        raise ValueError(f'No area called "{typed_name}".')

    risky = lesion.risky_pipes(atlas, area)
    if not risky:
        print(f'No single blocked pipe can stop {area.name}.')
        return

    if len(risky) == 1:
        print(f'1 pipe stops {area.name} if blocked:')
    else:
        print(f'{len(risky)} pipes stop {area.name} if blocked:')
    width = max(len(pipe.name) for pipe in risky)
    for pipe in risky:
        print(f'  {pipe.name.ljust(width)}  {pipe.size}')


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


# ------------------------------------------------------------ Mission 3: triage

def show_symptoms(symptoms):
    """triage symptoms: list every symptom code so the crew can look one up."""
    rows = [[s.code, str(s.points), s.description] for s in symptoms.values()]
    print_table(['CODE', 'POINTS', 'WHAT THE CREW SEES'], rows)
    print(f'{len(rows)} symptoms')
