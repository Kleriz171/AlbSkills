"""Mission 6, Goal 3: run a clinic visit and save it inside the case.

  clinic visit <case id>    ask the days, run the three tests, save the visit
  clinic record <case id>   ask the days and the three results typed in by hand

A saved visit looks like this inside the case:
  { "day": 14, "reactionMs": 540, "memoryDigits": 4, "colorWordSeconds": 31.0 }
and the list of visits is always kept oldest first.
"""

import re

import braintests
import triage

NUMBER = re.compile(r'\d+(\.\d+)?')


# ------------------------------------------------------------------ checks
# Each check takes the typed text and returns the clean value,
# or raises ValueError with the message to show (the same way as in triage.py).

def check_days(text):
    text = text.strip()
    if not (text.isascii() and text.isdigit()) or int(text) < 1:
        raise ValueError('Days since the stroke must be a whole number of 1 or more.')
    return int(text)


def check_reaction(text):
    text = text.strip()
    if not (text.isascii() and text.isdigit()) or int(text) < 1:
        raise ValueError('Reaction time must be a whole number of milliseconds above 0.')
    return int(text)


def check_memory(text):
    text = text.strip()
    if not (text.isascii() and text.isdigit()) or int(text) > braintests.MEMORY_MAX:
        raise ValueError(f'Memory span must be a whole number of digits from 0 to {braintests.MEMORY_MAX}.')
    return int(text)


def check_seconds(text):
    text = text.strip()
    if not (text.isascii() and NUMBER.fullmatch(text)) or float(text) <= 0:      # 31, 31.5: no sign, no comma
        raise ValueError('Colour words time must be a number of seconds above 0.')
    return float(text)


# ------------------------------------------------------------------ the visit

def make_visit(day, reaction, memory, seconds):
    return {'day': day, 'reactionMs': reaction, 'memoryDigits': memory, 'colorWordSeconds': float(seconds)}


def ask_day(case):
    """Ask the days since the stroke. A day that already has a visit stops the command, so
    nobody plays three tests for a visit that cannot be saved."""
    day = triage.ask('Days since the stroke: ', check_days)
    if any(visit['day'] == day for visit in case.visits):
        raise ValueError(f'{case.id} already has a visit on day {day}.')
    return day


def run_tests(io=None):
    """Play the three tests one after another. They all work the same way, so one loop does it.
    Returns the three numbers in the order of braintests.ALL_TESTS."""
    results = []
    for number, test_class in enumerate(braintests.ALL_TESTS, start=1):
        test = test_class(io)
        print(f'Test {number} of {len(braintests.ALL_TESTS)}: {test.title}')
        results.append(test.run())
    return results


def save_visit(state, case, visit):
    """Add the visit (oldest first) and write the file. If the write fails nothing is kept."""
    old = case.visits
    case.visits = sorted(old + [visit], key=lambda item: item['day'])
    try:
        triage.save_cases(state['cases_path'], state['cases'])
    except OSError:
        case.visits = old                             # not saved = no visit
        print(f'ERROR: Could not save the case to {state["cases_path"]}.')
        return False
    print(f'SUCCESS: Visit on day {visit["day"]} saved for {case.id}.')
    return True


def visit_case(state, case_id, io=None):
    """clinic visit <id>: ask the days, run the three tests, save the visit."""
    case = triage.find_case(state['cases'], case_id)
    day = ask_day(case)
    reaction, memory, seconds = run_tests(io)
    save_visit(state, case, make_visit(day, reaction, memory, seconds))


def record_visit(state, case_id):
    """clinic record <id>: save a visit from results typed in by hand (tests done on paper)."""
    case = triage.find_case(state['cases'], case_id)
    day = ask_day(case)
    reaction = triage.ask('Reaction time (ms): ', check_reaction)
    memory = triage.ask('Memory span (digits): ', check_memory)
    seconds = triage.ask('Colour words (seconds): ', check_seconds)
    save_visit(state, case, make_visit(day, reaction, memory, seconds))
