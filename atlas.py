"""Goal 2: model the atlas. Pipes and areas are objects; the Atlas holds them."""

HEART = '-'          # in the "comes from" field, "-" means "this pipe is the heart"


class Pipe:
    def __init__(self, name, size, comes_from, line):
        self.name = name
        self.size = size
        self.comes_from = comes_from    # list of pipe names, exactly as written in the file
        self.line = line                # line number in the file
        self.branches = []              # pipes that come OUT of this pipe (filled by link)
        self.areas = []                 # areas this pipe feeds (filled by link)
        self.parents = []               # the Pipe objects it comes from (filled by link)
        self.bridged_to = []            # pipes joined to this one by a bridge (filled by link)


class Area:
    def __init__(self, name, fed_by, symptoms, description, line):
        self.name = name
        self.fed_by = fed_by            # list of pipe names
        self.symptoms = symptoms        # list of symptom codes
        self.description = description
        self.line = line

    def matches(self, word):
        """Goal 4: does the word appear in the name, the symptoms or the description?
        Upper/lower case does not matter."""
        word = word.lower()
        texts = [self.name, self.description] + self.symptoms
        for text in texts:
            if word in text.lower():
                return True
        return False


class Bridge:
    """Mission 2, Bonus 2: a short pipe joining two pipes. Blood crosses it BOTH ways."""

    def __init__(self, first, second, line):
        self.first = first              # pipe names, as written in the file
        self.second = second
        self.line = line


class Atlas:
    def __init__(self):
        self.pipes = {}                 # pipe name -> Pipe object
        self.areas = {}                 # area name -> Area object
        self.bridges = []               # Bridge objects (empty for a plain atlas)

    def add_pipe(self, pipe):
        self.pipes[pipe.name] = pipe

    def add_area(self, area):
        self.areas[area.name] = area

    def add_bridge(self, first, second, line):
        for bridge in self.bridges:             # the same bridge written twice counts once
            if {bridge.first, bridge.second} == {first, second}:
                return
        self.bridges.append(Bridge(first, second, line))

    def link(self):
        """The file only says where a pipe comes FROM.
        Here we work out the other direction: what branches out of a pipe,
        and which areas a pipe feeds."""
        for pipe in self.pipes.values():
            for parent_name in pipe.comes_from:
                if parent_name != HEART:
                    parent = self.pipes[parent_name]
                    parent.branches.append(pipe)
                    pipe.parents.append(parent)

        for area in self.areas.values():
            for pipe_name in area.fed_by:
                self.pipes[pipe_name].areas.append(area)

        for bridge in self.bridges:             # a bridge works in both directions
            first, second = self.pipes[bridge.first], self.pipes[bridge.second]
            first.bridged_to.append(second)
            second.bridged_to.append(first)

    def routes_to(self, area):
        """Bonus 2: every route blood can take from the heart to this area.
        Returns a list of routes; each route is a list of pipe names, heart first."""
        routes = []
        for pipe_name in area.fed_by:
            self.climb(self.pipes[pipe_name], [], routes)
        return routes

    def climb(self, pipe, tail, routes):
        """Walk UP from a pipe towards the heart. 'tail' is the part of the route
        we have already walked (the pipes below this one, down to the area)."""
        route = [pipe.name] + tail                  # put this pipe in front of the tail
        if pipe.comes_from == [HEART]:
            routes.append(route)                    # reached the heart: the route is complete
            return
        for parent_name in pipe.comes_from:         # a pipe may have several parents
            self.climb(self.pipes[parent_name], route, routes)

    def get_pipe(self, name):
        """Find a pipe by name, ignoring upper/lower case. None if there is no such pipe."""
        return self.lookup(self.pipes, name)

    def get_area(self, name):
        """Find an area by name, ignoring upper/lower case. None if there is no such area."""
        return self.lookup(self.areas, name)

    def lookup(self, items, name):
        for key, item in items.items():
            if key.lower() == name.lower():
                return item
        return None

    def find_heart(self):
        """The one pipe that comes from '-'. (Goal 3 already checked there is exactly one.)"""
        for pipe in self.pipes.values():
            if pipe.comes_from == [HEART]:
                return pipe

    def find_areas(self, word):
        """Goal 4: every area that matches the word, in file order."""
        return [area for area in self.areas.values() if area.matches(word)]
