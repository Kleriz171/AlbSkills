"""Mission 6, Goals 3 and 4: run a clinic visit, save it inside the case, and rate the results.

  clinic visit <case id>    ask the days, run the three tests, save the visit
  clinic record <case id>   ask the days and the three results typed in by hand
  clinic results <case id>  every visit, oldest first, each result rated against the norms
  clinic check <case id>    Bonus 2: flags a weak result the damage does not explain, or a test getting worse
  clinic chart <case id> <test>   Bonus 3: one bar per visit

A saved visit looks like this inside the case:
  { "day": 14, "reactionMs": 540, "memoryDigits": 4, "colorWordSeconds": 31.0 }
and the list of visits is always kept oldest first.
"""

import re
from fractions import Fraction

import braintests
import commands
import lesion
import triage
from norms import norm_for

NUMBER = re.compile(r'\d+(\.\d+)?')

# The rule of Goal 4, in one place: how many SPREADS worse than the normal average?
NORMAL_UP_TO = 1                # up to 1 spread worse (or better than the average): normal
BELOW_UP_TO = 2                 # more than 1 and up to 2: below normal. More than 2: well below normal

# Bonus 2: the areas whose damage explains a weak result in each test (the table in the PDF)
EXPLAINED_BY = {
    'reaction': ('right-arm-face', 'awake'),                  # pressed with the right hand
    'memory': ('memory', 'understanding'),
    'colorword': ('understanding', 'left-attention', 'right-vision', 'left-vision'),
}

# where each test's number sits inside a saved visit
FIELDS = {'reaction': 'reactionMs', 'memory': 'memoryDigits', 'colorword': 'colorWordSeconds'}


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


# ------------------------------------------------------- Goal 4: compare with normal values

def number_text(value, decimals=0):
    """An exact Fraction as text with as few decimals as it needs, but never fewer than
    'decimals':  Fraction(6) with 1 -> '6.0',  Fraction('6.75') with 1 -> '6.75'."""
    places = decimals
    while places < 6 and (value * 10 ** places).denominator != 1:
        places += 1
    scaled = int(value * 10 ** places + Fraction(1, 2))         # rounds half up (only after 6 places)
    if places == 0:
        return str(scaled)
    return f'{scaled // 10 ** places}.{scaled % 10 ** places:0{places}d}'


def show_value(test_class, value):
    """A result with its unit: 540 -> '540 ms', 4 -> '4 digits', 31.0 -> '31.0 s'."""
    unit = test_class.unit_one if value == 1 else test_class.unit
    return f'{number_text(Fraction(str(value)), test_class.result_decimals)} {unit}'


def rate_result(norm, test_class, value):
    """'normal', 'below' or 'well below'. Worse means slower for reaction time and colour
    words, and fewer digits for memory span. Exact fractions, so a result exactly 1 spread
    worse is still normal and exactly 2 spreads worse is still only below."""
    value = Fraction(str(value))
    worse = norm.average - value if test_class.higher_is_better else value - norm.average
    if worse <= NORMAL_UP_TO * norm.spread:
        return 'normal'
    if worse <= BELOW_UP_TO * norm.spread:
        return 'below'
    return 'well below'


def norms_for_case(state, case):
    """{test key: Norm} for the age of this patient. Raises ValueError when there is none."""
    if state['norms'] is None:
        raise ValueError('No normal values are loaded. Use: clinic load <path>')
    return {test.key: norm_for(state['norms'], test.key, case.age) for test in braintests.ALL_TESTS}


def norms_line(case, bands):
    """'Arben Hoxha, 67 - normal for ages 65-79: reaction 390 ms, memory 6.0 digits, ...'"""
    ranges = {(norm.from_age, norm.to_age) for norm in bands.values()}
    one_range = len(ranges) == 1                    # the three tests may use different age bands
    parts = []
    for test in braintests.ALL_TESTS:
        norm = bands[test.key]
        text = f'{test.short} {number_text(norm.average, test.decimals)} {test.unit}'
        parts.append(text if one_range else f'{text} (ages {norm.from_age}-{norm.to_age})')
    if one_range:
        low, high = next(iter(ranges))
        return f'{case.name}, {case.age} - normal for ages {low}-{high}: ' + ', '.join(parts)
    return f'{case.name}, {case.age} - normal values: ' + ', '.join(parts)


def show_results(state, case_id):
    """clinic results <id>: every visit, oldest first, each result rated for the patient's age."""
    case = triage.find_case(state['cases'], case_id)
    if not case.visits:
        print(f'Case {case.id} has no visits yet.')          # a message, not a crash
        return
    bands = norms_for_case(state, case)
    print(norms_line(case, bands))

    visits = sorted(case.visits, key=lambda visit: visit['day'])     # oldest first, whatever order they were saved in
    columns = []                                                       # per test: [(value text, rating)]
    for test in braintests.ALL_TESTS:
        cells = []
        for visit in visits:
            value = visit.get(FIELDS[test.key])
            cells.append(('-', '') if value is None
                         else (show_value(test, value), rate_result(bands[test.key], test, value)))
        columns.append(cells)

    rows = []
    for index, visit in enumerate(visits):
        row = [str(visit['day'])]
        for cells, test in zip(columns, braintests.ALL_TESTS):
            width = max(len(text) for text, _ in cells)               # line the ratings up under each other
            text, rating = cells[index]
            row.append(f'{text.ljust(width)}  {rating}'.rstrip())
        rows.append(row)
    commands.print_table(['DAY'] + [test.short.upper() for test in braintests.ALL_TESTS], rows)
    trends = trends_of(visits)
    if trends:                                                         # Bonus 1: needs two visits
        names = ', '.join(f'{test.short} {trends[test.key]}' for test in braintests.ALL_TESTS)
        print(f'Trend, day {visits[-2]["day"]} to day {visits[-1]["day"]}: {names}')


# --------------------------------------------------------------- Bonus 1: trend

def trend_of(test_class, before, now):
    """'improving', 'worse' or 'steady' for the last two results of one test.
    Reaction time and colour words: more than 5% lower is improving, more than 5% higher is worse.
    Memory span: higher is improving, lower is worse. Both are one rule: the change must beat
    trend_percent (5, or 0 for memory) in the right direction. Exact fractions again."""
    before, now = Fraction(str(before)), Fraction(str(now))
    margin = Fraction(test_class.trend_percent, 100)
    if now > before * (1 + margin):
        return 'improving' if test_class.higher_is_better else 'worse'
    if now < before * (1 - margin):
        return 'worse' if test_class.higher_is_better else 'improving'
    return 'steady'


def trends_of(visits):
    """{test key: trend} comparing the last two visits (oldest first), or {} with fewer than two."""
    if len(visits) < 2:
        return {}
    before, now = visits[-2], visits[-1]
    return {test.key: trend_of(test, before[FIELDS[test.key]], now[FIELDS[test.key]])
            for test in braintests.ALL_TESTS}


# ------------------------------------------------- Bonus 2: does it match the damage?

def damaged_areas(state, case):
    """(names of the areas that stopped working, the text of the Damage line).
    The damage is what the Mission 2 engine says for the pipe that was found for this case."""
    if case.likely_pipe is None:
        return [], f'Damage: no blocked pipe is known for {case.id}.'
    if state['atlas'] is None:
        raise ValueError('No atlas is loaded, so the damage cannot be worked out. Use: atlas load <path>')
    pipe = state['atlas'].get_pipe(case.likely_pipe)
    if pipe is None:
        raise ValueError(f'The pipe "{case.likely_pipe}" of {case.id} is not in the loaded atlas.')
    result = lesion.simulate(state['atlas'], [pipe])
    names = [area.name for area in result.dead_areas]
    if not names:
        return names, f'Damage: {pipe.name} blocked -> no area stopped working'
    return names, f'Damage: {pipe.name} blocked -> {", ".join(names)} stopped working'


def check_case(state, case_id):
    """clinic check <id>: flag a latest result that is below normal but not explained by the
    damage, and any test that is getting worse. Either one can mean a new stroke."""
    case = triage.find_case(state['cases'], case_id)
    if not case.visits:
        print(f'Case {case.id} has no visits yet.')
        return
    bands = norms_for_case(state, case)
    dead, damage_line = damaged_areas(state, case)
    visits = sorted(case.visits, key=lambda visit: visit['day'])
    latest = visits[-1]
    trends = trends_of(visits)

    print(damage_line)
    rows, flags = [], []
    for test in braintests.ALL_TESTS:
        value = latest[FIELDS[test.key]]
        rating = rate_result(bands[test.key], test, value)
        expected = any(area in dead for area in EXPLAINED_BY[test.key])
        trend = trends.get(test.key, '-')
        name = test.short.capitalize()
        rows.append([name, f'{show_value(test, value)}  {rating}', trend, 'yes' if expected else 'no'])
        verb = 'are' if name.endswith('s') else 'is'                   # "Colour words are", "Memory is"
        if rating != 'normal' and not expected:
            flags.append(f'FLAG: {name} {verb} {rating} normal, and the damage does not explain it.')
        if trend == 'worse':
            flags.append(f'FLAG: {name} {verb} getting worse since day {visits[-2]["day"]}.')
    commands.print_table(['TEST', f'DAY {latest["day"]}', 'TREND', 'EXPECTED WEAK'], rows)
    if not flags:
        print('No flags.')
        return
    for flag in flags:
        print(flag)
    print('Advice: check the patient for a new stroke.')


# --------------------------------------------------------------- Bonus 3: chart

def find_test(typed):
    """The test class for what was typed: reaction, memory, colorword, colour words, ..."""
    simple = typed.strip().lower().replace(' ', '').replace('-', '').replace('_', '')
    for test in braintests.ALL_TESTS:
        names = {test.key, test.short.replace(' ', ''), test.title.replace(' ', '')}
        if simple in names or (test.key == 'colorword' and simple in ('color', 'colour', 'colorwords')):
            return test
    raise ValueError(f'Unknown test "{typed}". Expected reaction, memory or colorword.')


def half_up_whole(value):
    return int(value + Fraction(1, 2))


def chart_case(state, case_id, typed_test):
    """clinic chart <id> <test>: one bar per visit, one # per chart_unit, rounded to the nearest #."""
    test = find_test(typed_test)
    case = triage.find_case(state['cases'], case_id)
    if not case.visits:
        print(f'Case {case.id} has no visits yet.')
        return
    norm = norms_for_case(state, case)[test.key]
    low, high = norm.average - norm.spread, norm.average + norm.spread
    direction = 'higher' if test.higher_is_better else 'lower'
    print(f'{test.title.capitalize()} - {direction} is better - normal for age {case.age}: '
          f'{number_text(low, test.decimals)} to {number_text(high, test.decimals)} {test.unit}')

    visits = sorted(case.visits, key=lambda visit: visit['day'])
    bars = [half_up_whole(Fraction(str(visit[FIELDS[test.key]])) / test.chart_unit) for visit in visits]
    labels = [f'Day {visit["day"]}' for visit in visits]
    for visit, label, bar in zip(visits, labels, bars):
        print(f'{label.ljust(max(map(len, labels)))}  {("#" * bar).ljust(max(bars))}  '
              f'{show_value(test, visit[FIELDS[test.key]])}'.rstrip())
