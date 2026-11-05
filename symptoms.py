"""Mission 3, Goal 1: read the symptom list (same file format as the atlas).

Nothing about symptoms is written in the code: codes, points and descriptions
all come from the file, so a different symptoms-v2.txt just works.
"""

from loader import read_atlas_file

FIELD_COUNT = 4                    # SYMPTOM | code | points | description


class SymptomError(Exception):
    """A bad symptom file. 'messages' holds EVERY problem we found."""

    def __init__(self, messages):
        super().__init__('\n'.join(messages))
        self.messages = messages


class Symptom:
    def __init__(self, code, points, description, line):
        self.code = code
        self.points = points
        self.description = description
        self.line = line


def load_symptoms(filename):
    """Return a dict  code -> Symptom, in file order.
    A bad file raises SymptomError listing ALL problems, so the caller keeps its old list."""
    try:
        records = read_atlas_file(filename)
    except FileNotFoundError:
        raise SymptomError([f'File not found: {filename}'])
    if not records:
        raise SymptomError(['The file is empty.'])

    symptoms = {}
    first_seen = {}                               # code -> line where it was first defined
    errors = []

    for lineno, parts in records:
        where = f'{filename}, line {lineno}'
        if parts[0] != 'SYMPTOM':
            errors.append(f'{where}: unknown record type "{parts[0]}". Expected SYMPTOM.')
            continue
        if len(parts) != FIELD_COUNT:
            errors.append(f'{where}: SYMPTOM needs {FIELD_COUNT} fields, found {len(parts)}.')
            continue

        _, code, points_text, description = parts
        if not code:
            errors.append(f'{where}: the symptom code is empty.')
            continue
        if code in first_seen:
            errors.append(f'{where}: "{code}" is defined twice (first on line {first_seen[code]}).')
            continue
        first_seen[code] = lineno

        if not points_text.isdigit():             # whole number, 0 or more
            errors.append(f'{where}: points must be a whole number, found "{points_text}".')
            continue
        symptoms[code] = Symptom(code, int(points_text), description, lineno)

    if errors:
        raise SymptomError(errors)
    return symptoms
