"""Bonus 3: graph checks used by the loader."""

from collections import deque


def reachable(start, edges):
    """edges: dict of node -> list of neighbours.
    Returns the set of every node we can reach from start (including start)."""
    seen = {start}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for neighbour in edges.get(node, []):
            if neighbour not in seen:
                seen.add(neighbour)
                queue.append(neighbour)
    return seen


def find_loops(parents):
    """parents: dict of node -> list of its parents.
    Returns a list of loops; each loop is a list of names, e.g. ['a', 'b'] when
    a comes from b and b comes from a."""
    state = {}               # name -> 'visiting' (still on our path) or 'done'
    path = []                # the pipes we are walking through right now
    loops = []

    def visit(name):
        state[name] = 'visiting'
        path.append(name)
        for parent in parents[name]:
            if state.get(parent) == 'visiting':
                loops.append(path[path.index(parent):])    # we came back to our own path
            elif parent not in state:
                visit(parent)
        path.pop()
        state[name] = 'done'

    for name in parents:
        if name not in state:
            visit(name)
    return loops


def describe_loop(loop):
    """['left-front', 'left-neck'] -> 'left-front comes from left-neck,
    which comes from left-front.'"""
    steps = loop + [loop[0]]
    text = f'{steps[0]} comes from {steps[1]}'
    for name in steps[2:]:
        text += f', which comes from {name}'
    return text + '.'
