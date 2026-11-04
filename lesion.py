"""Mission 2: the lesion engine.

The four blood rules are written HERE, once. Every command calls this code.

  1. The heart always has blood. It can never be blocked.
  2. A blocked pipe has no blood.
  3. Any other pipe has blood if at least one of the pipes it comes from has blood.
  4. An area works if at least one of the pipes that feed it has blood.
"""

from graph import reachable


class LesionResult:
    """Everything we learn from blocking some pipes."""

    def __init__(self, blocked, dry_pipes, dead_areas, symptoms):
        self.blocked = blocked            # the pipes the doctor blocked
        self.dry_pipes = dry_pipes        # every pipe left without blood (file order)
        self.dead_areas = dead_areas      # every area that stops working (file order)
        self.symptoms = symptoms          # their symptoms, each listed once


def pipes_with_blood(atlas, blocked_names):
    """Rules 1, 2 and 3: the names of all pipes that still have blood.

    Start at the heart (rule 1) and follow the branches downwards, but never
    step into a blocked pipe (rule 2). A pipe is reached if ANY parent was
    reached (rule 3)."""
    edges = {}
    for pipe in atlas.pipes.values():
        edges[pipe.name] = [branch.name for branch in pipe.branches
                            if branch.name not in blocked_names]
    return reachable(atlas.find_heart().name, edges)


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

    return LesionResult(blocked_pipes, dry_pipes, dead_areas, symptoms)
