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


class Atlas:
    def __init__(self):
        self.pipes = {}                 # pipe name -> Pipe object
        self.areas = {}                 # area name -> Area object

    def add_pipe(self, pipe):
        self.pipes[pipe.name] = pipe

    def add_area(self, area):
        self.areas[area.name] = area

    def link(self):
        """The file only says where a pipe comes FROM.
        Here we work out the other direction: what branches out of a pipe,
        and which areas a pipe feeds."""
        for pipe in self.pipes.values():
            for parent_name in pipe.comes_from:
                if parent_name != HEART:
                    parent = self.pipes[parent_name]
                    parent.branches.append(pipe)

        for area in self.areas.values():
            for pipe_name in area.fed_by:
                self.pipes[pipe_name].areas.append(area)

    def find_heart(self):
        """The one pipe that comes from '-'. (Goal 3 already checked there is exactly one.)"""
        for pipe in self.pipes.values():
            if pipe.comes_from == [HEART]:
                return pipe

    def find_areas(self, word):
        """Goal 4: every area that matches the word, in file order."""
        return [area for area in self.areas.values() if area.matches(word)]
