"""Mission 6, Goal 1: read the normal values (same file format as the atlas).

  NORM | test | from age | to age | normal average | spread

Nothing about the normal values is written in the code: ages, averages and spreads all
come from the file, so a norms-v2.txt just works. The only thing the code knows is the
names of the three tests the clinic can run.

Averages and spreads are kept as exact Fractions, built from the text of the file
(Fraction('6.8') is really 6.8). Goal 4 asks "is the result MORE than 1 spread worse?",
and an exact number lands on the right side of that line when a result is exactly 1.
"""

import os
import re
from fractions import Fraction

from loader import read_atlas_file

FIELD_COUNT = 6                              # NORM | test | from | to | average | spread
TESTS = ('reaction', 'memory', 'colorword')  # the three brain tests (names as written in the file)
NUMBER = re.compile(r'\d+(\.\d+)?')          # 300, 7.0, 3.5: no sign, no exponent, no comma


class NormError(Exception):
    """A bad norms file. 'messages' holds EVERY problem we found, not just the first."""

    def __init__(self, messages):
        super().__init__('\n'.join(messages))
        self.messages = messages


class Norm:
    """The normal values for one test and one age band. Both ends of the band count."""

    def __init__(self, test, from_age, to_age, average, spread, average_text, spread_text, line):
        self.test = test
        self.from_age = from_age
        self.to_age = to_age
        self.average = average                # Fraction
        self.spread = spread                  # Fraction, always above 0
        self.average_text = average_text      # as written in the file, for printing ("7.0")
        self.spread_text = spread_text
        self.line = line

    def covers(self, age):
        return self.from_age <= age <= self.to_age


def is_whole_number(text):
    return text.isascii() and text.isdigit()


def is_number(text):
    return text.isascii() and NUMBER.fullmatch(text) is not None


def load_norms(filename):
    """Return a dict  test -> [Norm, ...]  (tests in file order, bands in file order).
    A bad file raises NormError listing ALL problems, so the caller keeps its old values."""
    try:
        records = read_atlas_file(filename)
    except FileNotFoundError:
        raise NormError([f'File not found: {filename}'])
    except UnicodeDecodeError:
        raise NormError([f'{os.path.basename(filename)} is not a text file.'])
    if not records:
        raise NormError(['The file is empty.'])

    name = os.path.basename(filename)
    norms = {}
    errors = []

    for lineno, parts in records:
        where = f'{name}, line {lineno}'
        if parts[0] != 'NORM':
            errors.append(f'{where}: unknown record type "{parts[0]}". Expected NORM.')
            continue
        if len(parts) != FIELD_COUNT:
            errors.append(f'{where}: NORM needs {FIELD_COUNT} fields, found {len(parts)}.')
            continue

        _, test, from_text, to_text, average_text, spread_text = parts
        problems = []
        if not test:
            problems.append('the test name is empty.')
        elif test not in TESTS:
            problems.append(f'unknown test "{test}". Expected {", ".join(TESTS[:-1])} or {TESTS[-1]}.')
        if not is_whole_number(from_text):
            problems.append(f'from age must be a whole number, found "{from_text}".')
        if not is_whole_number(to_text):
            problems.append(f'to age must be a whole number, found "{to_text}".')
        if is_whole_number(from_text) and is_whole_number(to_text) and int(from_text) > int(to_text):
            problems.append(f'from age {from_text} is above to age {to_text}.')
        if not is_number(average_text):
            problems.append(f'the normal average must be a number, found "{average_text}".')
        if not is_number(spread_text):
            problems.append(f'the spread must be a number, found "{spread_text}".')
        elif Fraction(spread_text) == 0:
            problems.append('the spread must be above 0.')
        if problems:
            errors.extend(f'{where}: {problem}' for problem in problems)
            continue

        norm = Norm(test, int(from_text), int(to_text), Fraction(average_text),
                    Fraction(spread_text), average_text, spread_text, lineno)
        overlap = next((other for other in norms.get(test, [])
                        if norm.from_age <= other.to_age and other.from_age <= norm.to_age), None)
        if overlap:                                 # compared with EARLIER lines of the same test
            errors.append(f'{where}: ages {norm.from_age} to {norm.to_age} overlap with '
                          f'line {overlap.line}.')
            continue
        norms.setdefault(test, []).append(norm)

    if errors:
        raise NormError(errors)
    return norms


def norm_for(norms, test, age):
    """The Norm of this test whose age band holds 'age' (both ends count).
    Raises ValueError with a message for the user when there is none."""
    for norm in norms.get(test, []):
        if norm.covers(age):
            return norm
    if test not in norms:
        raise ValueError(f'No normal values for the {test} test.')
    raise ValueError(f'No normal values for age {age}.')
