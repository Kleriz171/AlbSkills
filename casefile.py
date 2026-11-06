"""Mission 7: the case file. One command, one patient, the whole journey.

  case <case id>        triage, route, hospital and recovery, from what the other missions saved
  case find <text>      search every case by name and city
  case export <case id> Bonus 1: write exports/<id>.txt and exports/<id>.json
  case board            Bonus 2: every case on one screen
  case cost <case id>   Bonus 3: time is brain

Nothing here runs the route or the hospital simulation again: it only reads what the
other missions saved inside the case, and it never breaks when a part is missing.

Mission 4 saved PLANNED times, as if the hospital were empty.
Mission 5 saved ACTUAL times, after waiting in line.   Waited = actual - planned.
"""

import json
import os

import clinic
import commands
import triage
import unit
from triage import format_limit, parse_limit

EXPORT_DIR = 'exports'
INDENT = ' ' * 7                            # lines under a time ("07:30  Last seen well") start here
CELLS_PER_MINUTE = 1_900_000                # Bonus 3: brain cells lost per minute of a large stroke
RATING_WIDTH = len('well below')              # the longest rating: ratings are padded to this


# ------------------------------------------------------------ what the other missions saved

def stay_of(case):
    """The saved hospital times, only if they belong to the CURRENT route. A case that was routed
    again after 'unit run' has old times that no longer describe its journey."""
    route, stay = case.route, case.hospital_stay
    if (route and stay and route.get('hospital') == unit.UNIT_HOSPITAL
            and stay.get('hospital') == unit.UNIT_HOSPITAL and stay.get('arrives') == route.get('arrives')):
        return stay
    return None


def minutes_between(first, second):
    """Minutes from one saved time to another ('10:30' to '10:40' is 10)."""
    return parse_limit(second) - parse_limit(first)


def treatments(case):
    """[(label, planned, actual, given where)] for the drug and clot removal. Times are the saved
    text ('10:30') or None. 'given where' is the first hospital when the drug was given there."""
    route, stay = case.route, stay_of(case)
    if route is None:
        return []
    stop = route.get('firstStop')
    return [
        ('drug', route.get('drugAt'), stay.get('drugAt') if stay and not stop else None,
         stop['hospital'] if stop else None),
        ('clot removal', route.get('clotRemovalAt'), stay.get('clotRemovalAt') if stay else None, None),
    ]


def first_treatment(case):
    """(label, time text, is it the actual time, minutes waited or None), or None.
    The first treatment is the drug or the clot removal, whichever comes first: the actual
    time if the hospital recorded it, otherwise the planned time."""
    stay = stay_of(case)
    found = []
    for label, planned, actual, elsewhere in treatments(case):
        if actual is not None:
            found.append((parse_limit(actual), label, actual, True,
                          None if planned is None else minutes_between(planned, actual)))
        elif planned is not None and (stay is None or elsewhere):     # no record yet, or given at the first hospital
            found.append((parse_limit(planned), label, planned, False, None))
    if not found:
        return None
    _, label, text, is_actual, waited = min(found)
    return label, text, is_actual, waited


# ------------------------------------------------------------------ the four sections

def triage_lines(case):
    dot = commands.dot()
    seen = triage.timeline(case.last_seen, case.yesterday)
    pipe = 'unknown' if case.likely_pipe is None else f'{case.likely_pipe} ({"big" if case.big_pipe else "small"})'
    drug = (f'Drug possible until {format_limit(case.drug_until)}' if case.drug_possible
            else f'Drug not possible (the limit passed at {format_limit(case.drug_until)})')
    clot = (f'clot removal possible until {format_limit(case.clot_until)}' if case.clot_possible
            else 'clot removal not possible')
    return ['TRIAGE',
            f'{format_limit(seen)}  Last seen well',
            f'{format_limit(case.created)}  Case created by the ambulance crew',
            f'{INDENT}Symptoms: {", ".join(case.symptoms)}',
            f'{INDENT}Severity {case.severity} ({case.band}){dot}likely blocked pipe: {pipe}',
            f'{INDENT}{drug}{dot}{clot}']


def route_lines(case):
    route = case.route
    if route is None:
        return [f'ROUTE: not planned yet. Run route {case.id}.']
    lines = ['ROUTE']
    stop = route.get('firstStop')
    if stop:                                            # Mission 4, Bonus 1: drug first, then transfer
        lines.append(f'{format_limit(case.created)}  Leaves {case.city}: {triage.way_text(stop["path"])}, '
                     f'{stop["driveMinutes"]} min')
        lines.append(f'{stop["arrives"]}  Arrives at {stop["hospital"]}: drug at {stop["drugAt"]}')
        lines.append(f'{route["leaves"]}  Transfer leaves {route["path"][0]}: {triage.way_text(route["path"])}, '
                     f'{route["driveMinutes"]} min')
    else:
        lines.append(f'{route["leaves"]}  Leaves {case.city}: {triage.way_text(route["path"])}, '
                     f'{route["driveMinutes"]} min')
    lines.append(f'{route["arrives"]}  Arrives at {route["hospital"]}')
    return lines


def planned_text(route):
    parts = []
    if route.get('drugAt'):
        parts.append(f'drug: {route["drugAt"]}')
    if route.get('clotRemovalAt'):
        parts.append(f'clot removal: {route["clotRemovalAt"]}')
    if not parts:
        return 'Planned: scan only.'
    return 'Planned ' + ', '.join(parts) + '.'


def hospital_lines(case):
    route = case.route
    if route is None:
        return [f'HOSPITAL: no route yet, so no hospital. Run route {case.id}.']
    stay = stay_of(case)
    if route['hospital'] != unit.UNIT_HOSPITAL:
        return ['HOSPITAL', f'Not recorded: only {unit.UNIT_HOSPITAL} is simulated. {planned_text(route)}']
    if stay is None:
        return ['HOSPITAL', f'Not recorded for this route yet. Run unit run <file>. {planned_text(route)}']

    rows = [['Scan', '-', stay.get('scanAt') or '-', '-']]
    for label, planned, actual, elsewhere in treatments(case):
        if elsewhere:
            rows.append([label.capitalize(), planned or '-', f'given at {elsewhere}', '-'])
            continue
        if actual is None:
            actual_text = 'missed' if (label == 'drug' and planned) else '-'
        else:
            actual_text = actual
        waited = f'{minutes_between(planned, actual)} min' if planned and actual else '-'
        rows.append([label.capitalize(), planned or '-', actual_text, waited])
    return table_lines(['HOSPITAL', 'PLANNED', 'ACTUAL', 'WAITED'], rows)


def table_lines(header, rows):
    """The lines print_table would print (so the file and the screen can never differ)."""
    widths = [max(len(row[i]) for row in [header] + rows) for i in range(len(header))]
    return ['  '.join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip() for row in [header] + rows]


def recovery_value(test, value):
    """'540 ms', '4' (memory is a bare number in the case file), '31.0 s'."""
    if test.unit_in_case_file:
        return clinic.show_value(test, value)
    return clinic.number_text(clinic.Fraction(str(value)), test.result_decimals)


def recovery_lines(state, case):
    if not case.visits:
        return ['RECOVERY', 'No clinic visits yet.']
    visits = sorted(case.visits, key=lambda visit: visit['day'])
    tests = clinic.braintests.ALL_TESTS
    try:
        bands = clinic.norms_for_case(state, case)
        ranges = {(norm.from_age, norm.to_age) for norm in bands.values()}
        if len(ranges) == 1:
            header = 'RECOVERY (normal for ages {}-{})'.format(*next(iter(ranges)))
        else:
            header = 'RECOVERY (normal for ages ' + ', '.join(
                f'{test.short} {bands[test.key].from_age}-{bands[test.key].to_age}' for test in tests) + ')'
    except ValueError as error:                         # no norms for this age: show the results, unrated
        bands, header, note = None, 'RECOVERY', f'Results not rated: {error}'
    else:
        note = None

    cells = {test.key: [recovery_value(test, visit[clinic.FIELDS[test.key]]) for visit in visits] for test in tests}
    value_width = {test.key: max(len(text) for text in cells[test.key]) for test in tests}
    labels = [f'Day {visit["day"]}' for visit in visits]
    dot = commands.dot()
    lines = [header]
    for index, visit in enumerate(visits):
        parts = []
        for test in tests:
            text = f'{test.short} {cells[test.key][index].ljust(value_width[test.key])}'
            if bands is not None:
                rating = clinic.rate_result(bands[test.key], test, visit[clinic.FIELDS[test.key]])
                text += f' {rating.ljust(RATING_WIDTH)}'
            parts.append(text)
        lines.append((labels[index].ljust(max(map(len, labels))) + '   ' + dot.join(parts)).rstrip())
    if note:
        lines.append(note)
    return lines


# ------------------------------------------------------------------ Goal 1 and 2: show a case

def case_lines(state, case):
    """Every line of the case file. A part that cannot be read prints a plain message, never a crash."""
    lines = [f'=== Case {case.id}: {case.name}, {case.age}, {case.city} ===']
    sections = (('TRIAGE', lambda: triage_lines(case)), ('ROUTE', lambda: route_lines(case)),
                ('HOSPITAL', lambda: hospital_lines(case)), ('RECOVERY', lambda: recovery_lines(state, case)))
    for name, build in sections:
        try:
            lines += build()
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            lines.append(f'{name}: the saved data for this part could not be read.')
    return lines


def show_case(state, case_id):
    case = triage.find_case(state['cases'], case_id)
    for line in case_lines(state, case):
        print(line)


# --------------------------------------------------------------------- Goal 3: find a case

def find_cases(state, text):
    """case find <text>: by name and city, ignoring upper/lower case, part of a word is enough."""
    text = text.strip()
    if not text:
        raise ValueError('Search text cannot be empty.')
    needle = text.lower()
    found = [case for case in state['cases'] if needle in case.name.lower() or needle in case.city.lower()]
    if not found:
        print(f'No cases match "{text}".')
        return
    if len(found) == 1:
        print(f'1 case matches "{text}". Opening it.')
        show_case(state, found[0].id)
        return
    print(f'{len(found)} cases match "{text}":')
    widths = [max(len(value) for value in column)
              for column in zip(*[(case.id, case.name, str(case.age)) for case in found])]
    for number, case in enumerate(found, start=1):
        print(f'{number}. {case.id.ljust(widths[0])}  {case.name.ljust(widths[1])}  '
              f'{str(case.age).ljust(widths[2])}  {case.city}')
    while True:
        answer = input('Enter a number to open, or press ENTER to go back: ').strip()
        if not answer:
            return
        if answer.isascii() and answer.isdigit() and 1 <= int(answer) <= len(found):
            show_case(state, found[int(answer) - 1].id)
            return
        print(f'ERROR: Enter a number from 1 to {len(found)}, or press ENTER to go back.')


# ------------------------------------------------------------------ Bonus 1: export

def write_text_file(path, text):
    """Write to a temporary file first, then swap it in, so a crash cannot leave half a file."""
    temporary = path + '.tmp'
    with open(temporary, 'w', encoding='utf-8') as f:
        f.write(text)
    os.replace(temporary, path)


def export_case(state, case_id):
    """case export <id>: exports/<id>.txt (the same text as 'case <id>') and exports/<id>.json
    (the whole case). Running it again replaces both files."""
    case = triage.find_case(state['cases'], case_id)
    text_path = f'{EXPORT_DIR}/{case.id}.txt'
    json_path = f'{EXPORT_DIR}/{case.id}.json'
    try:
        os.makedirs(EXPORT_DIR, exist_ok=True)
        write_text_file(text_path, '\n'.join(case_lines(state, case)) + '\n')
        write_text_file(json_path, json.dumps(triage.case_to_dict(case), indent=4, ensure_ascii=False) + '\n')
    except OSError as error:
        print(f'ERROR: Could not write the export files ({error}).')
        return
    print(f'SUCCESS: Wrote {text_path} and {json_path}.')


# --------------------------------------------------------------------- Bonus 2: the board

def last_visit_text(state, case):
    """('day 90: 2 below normal', flagged). Flagged when Mission 6's clinic check raises a flag."""
    if not case.visits:
        return 'no visits', False
    latest = max(case.visits, key=lambda visit: visit['day'])
    try:
        ratings = clinic.visit_ratings(clinic.norms_for_case(state, case), latest)
    except ValueError:
        return f'day {latest["day"]}: not rated', False
    below = sum(1 for rating in ratings.values() if rating != 'normal')
    text = f'day {latest["day"]}: ' + ('all normal' if below == 0 else f'{below} below normal')
    try:
        report = clinic.check_report(state, case)
    except ValueError:
        return text, False                              # the damage cannot be worked out: no flag
    return text, bool(report and report[2])


def board_row(state, case):
    route = case.route
    if route is None:
        went, first, waited = 'not planned', 'no route', '-'
    else:
        stop = route.get('firstStop')
        went = f'{stop["hospital"]} -> {route["hospital"]}' if stop else route['hospital']
        treatment = first_treatment(case)
        if treatment is None:
            first, waited = 'none', '-'
        else:
            label, time, is_actual, minutes = treatment
            first = f'{label} {time}' + ('' if is_actual else ' planned')
            waited = f'{minutes} min' if minutes is not None else 'not recorded'
    last, flagged = last_visit_text(state, case)
    return [case.id, case.name, went, first, waited, last + ('  !' if flagged else '')]


def show_board(state):
    """case board: every case on one screen, one row each."""
    if not state['cases']:
        print('No cases yet.')
        return
    rows = []
    for case in state['cases']:
        try:
            rows.append(board_row(state, case))
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            rows.append([case.id, case.name, 'unreadable', '-', '-', '-'])   # one damaged case never hides the others
    commands.print_table(['ID', 'NAME', 'WENT TO', 'FIRST TREATMENT', 'WAITED', 'LAST VISIT'], rows)
    print('! = check for a new stroke')


# ------------------------------------------------------------------- Bonus 3: time is brain

def millions(minutes):
    """Brain cells lost in these minutes, in whole millions (rounded half up)."""
    return (minutes * CELLS_PER_MINUTE + 500_000) // 1_000_000


def cost_case(state, case_id):
    """case cost <id>: minutes from last seen well to the first treatment, and the minutes waited."""
    case = triage.find_case(state['cases'], case_id)
    treatment = first_treatment(case)
    if treatment is None:
        hint = f' Run route {case.id}.' if case.route is None else ''
        print(f'No treatment is recorded or planned for {case.id} yet, so the time cannot be counted.{hint}')
        return
    label, time, is_actual, waited = treatment
    seen = triage.timeline(case.last_seen, case.yesterday)
    minutes = parse_limit(time) - seen
    basis = label if is_actual else f'{label}, planned'
    print(f'Last seen well {format_limit(seen)} -> first treatment {format_limit(parse_limit(time))} '
          f'({basis}): {minutes} min')
    print(f'About {millions(minutes)} million brain cells lost before treatment, at 1.9 million a minute.')
    if waited is None:
        print('The minutes spent waiting in the hospital line are not recorded.')
    elif waited == 0:
        print('None of those minutes were spent waiting in the hospital line.')
    else:
        verb = 'was' if waited == 1 else 'were'
        print(f'{waited} of those minutes {verb} spent waiting in the hospital line: '
              f'about {millions(waited)} million.')
    print('The 1.9 million figure is a published average for large strokes, used here as an estimate.')
