"""Mission 2: the lesion engine.

The blood rules are written HERE, once. Every command calls this code.

  1. The heart always has blood. It can never be blocked.
  2. A blocked pipe has no blood.
  3. Any other pipe has blood if at least one pipe it comes from (or, with
     bridges, is bridged to) has blood.
  4. An area works if at least one of the pipes that feed it has blood.
"""

from graph import reachable


class LesionResult:
    """Everything we learn from blocking some pipes."""

    def __init__(self, blocked, dry_pipes, dead_areas, symptoms, saved=None):
        self.blocked = blocked            # the pipes the doctor blocked
        self.dry_pipes = dry_pipes        # every pipe left without blood (file order)
        self.dead_areas = dead_areas      # every area that stops working (file order)
        self.symptoms = symptoms          # their symptoms, each listed once
        self.saved = saved or []          # [(pipe, [pipes it got blood from])] saved by a bridge


def pipes_with_blood(atlas, blocked_names, use_bridges=True):
    """Rules 1, 2 and 3: the names of all pipes that still have blood.

    Start at the heart (rule 1) and follow blood outwards, but never step into
    a blocked pipe (rule 2). Blood flows down the branches and, if use_bridges
    is True, across bridges in both directions (rule 3).

    A bridge can make blood flow in a circle. reachable() keeps a 'seen' set,
    so it never visits a pipe twice and always finishes."""
    edges = {}
    for pipe in atlas.pipes.values():
        neighbours = list(pipe.branches)
        if use_bridges:
            neighbours += pipe.bridged_to
        edges[pipe.name] = [n.name for n in neighbours if n.name not in blocked_names]
    return reachable(atlas.find_heart().name, edges)


def find_saved_pipes(atlas, with_blood, blocked_names):
    """Pipes that would be dry WITHOUT bridges but have blood thanks to them.
    Returns [(pipe, [the neighbouring pipes it received blood from])]."""
    if not atlas.bridges:
        return []
    without_bridges = pipes_with_blood(atlas, blocked_names, use_bridges=False)
    saved = [p for p in atlas.pipes.values()
             if p.name in with_blood and p.name not in without_bridges]
    saved_names = {p.name for p in saved}

    result = []
    for pipe in saved:
        givers = []
        for neighbour in pipe.parents + pipe.bridged_to:
            if neighbour.name in with_blood and neighbour not in givers:
                givers.append(neighbour)
        # prefer neighbours that had blood even without bridges (the real source)
        real_sources = [g for g in givers if g.name not in saved_names]
        result.append((pipe, real_sources or givers))
    return result


def risky_pipes(atlas, area):
    """Mission 2, Goal 2: every pipe that, if it ALONE were blocked, would stop this area.

    We do not write any new blood rule here. For each pipe we simply ask the
    engine (simulate) "what happens if this pipe is blocked?" and see whether
    the area is among the ones that stop. That is why 'lesion risk' and
    'lesion block' can never disagree."""
    heart = atlas.find_heart()
    risky = []
    for pipe in atlas.pipes.values():          # file order
        if pipe is heart:
            continue                           # rule 1: the heart can never be blocked
        result = simulate(atlas, [pipe])
        if area in result.dead_areas:
            risky.append(pipe)
    return risky


def simulate(atlas, blocked_pipes):
    """Block these pipes (a list of Pipe objects) and work out what happens."""
    blocked_names = {pipe.name for pipe in blocked_pipes}
    with_blood = pipes_with_blood(atlas, blocked_names)

    dry_pipes = [p for p in atlas.pipes.values() if p.name not in with_blood]

    # Rule 4: an area stops only when ALL of its feeding pipes have no blood.
    dead_areas = []
    for area in atlas.areas.values():
        if not any(name in with_blood for name in area.fed_by):
            dead_areas.append(area)

    symptoms = []
    for area in dead_areas:
        for symptom in area.symptoms:
            if symptom not in symptoms:       # each symptom once
                symptoms.append(symptom)

    saved = find_saved_pipes(atlas, with_blood, blocked_names)
    return LesionResult(blocked_pipes, dry_pipes, dead_areas, symptoms, saved)
