"""Mission 3, Goal 2: create a case.

Every answer is checked as soon as it is typed. A wrong answer prints
"ERROR: ..." and asks the SAME question again, so nothing typed before is lost.
"""

import copy
import json
import os
import re
from fractions import Fraction

import lesion
import roadmap
import unit
import routing
from commands import print_table

MAX_AGE = 120

# The rules of Goal 3. They are numbers from the PDF, kept in one place,
# so a changed rule is a one-line change.
MINUTES_PER_DAY = 24 * 60
DRUG_WINDOW = 4 * 60 + 30            # the drug works up to 4 h 30 min after last seen well
CLOT_WINDOW = 24 * 60                # clot removal works up to 24 h after last seen well
CLOT_MIN_SEVERITY = 5                # clot removal needs severity 5 or more
CLOSE_ENOUGH = Fraction(60, 100)       # Bonus 1: a close match counts from 60% up
CLOSEST_SHOWN = 3                    # Bonus 1: how many near misses are listed
BANDS = ((10, 'severe'), (5, 'moderate'), (0, 'minor'))    # (lowest severity, band name)
TIME_FORMAT = re.compile(r'(\d\d):(\d\d)')         # exactly HH:MM


class Case:
    """One patient. Times are kept as minutes after midnight (08:10 -> 490), so they
    can be compared and added with plain numbers (the trap this mission warns about)."""

    def __init__(self, case_id, name, age, city, now, last_seen, yesterday, symptoms):
        self.id = case_id
        self.name = name
        self.age = age
        self.city = city
        self.created = now                # when the case was opened (never changes)
        self.now = now                    # the latest time recorded: grows with every update
        self.history = []                 # Bonus 2: one entry per update
        self.route = None                 # Mission 4: the saved route (a dict), or None
        self.hospital_stay = None         # Mission 5: the hospital times (a dict), or None
        self.last_seen = last_seen        # minutes after midnight, today or yesterday
        self.yesterday = yesterday        # True when last_seen was yesterday
        self.symptoms = symptoms          # list of codes, each one once, in typed order
        # filled in by assess() (Goal 3). Times below are on ONE timeline, in minutes:
        # 0 = midnight at the start of today, negative = yesterday, 1440+ = tomorrow.
        self.severity = 0
        self.band = ''
        self.drug_until = 0
        self.drug_possible = False
        self.clot_until = 0
        self.clot_time_ok = False         # the time rule on its own
        self.likely_pipe = None           # pipe NAME, or None when unknown (Goal 4)
        self.big_pipe = False
        self.match_percent = None         # Bonus 1: set only when the match was not exact
        self.closest = []                 # Bonus 1: [(pipe name, percent)], best first
        self.clot_possible = False        # time AND big pipe AND severity


# ------------------------------------------------------------------ checks
# Each check takes the typed text and returns the clean value,
# or raises ValueError with the message to show.

def check_not_empty(label):
    def check(text):
        text = text.strip()
        if not text:
            raise ValueError(f'{label} cannot be empty.')
        return text
    return check


def check_age(text):
    text = text.strip()
    if not (text.isascii() and text.isdigit()) or int(text) > MAX_AGE:
        raise ValueError(f'Age must be a whole number from 0 to {MAX_AGE}.')
    return int(text)


def parse_time(text):
    """'08:10' -> 490 minutes after midnight."""
    text = text.strip()
    match = TIME_FORMAT.fullmatch(text)
    if not match or int(match.group(1)) > 23 or int(match.group(2)) > 59:
        raise ValueError(f'Invalid time "{text}". Use HH:MM, for example 08:10.')
    return int(match.group(1)) * 60 + int(match.group(2))


def check_yes_no(text):
    answer = text.strip().lower()
    if answer in ('yes', 'y'):
        return True
    if answer in ('no', 'n'):
        return False
    raise ValueError('Answer yes or no.')


def make_symptom_check(known):
    """known: dict code -> Symptom (loaded from the file, never written here)."""
    def check(text):
        codes = [c.strip() for c in text.split(',') if c.strip()]
        if not codes:
            raise ValueError('Enter at least one symptom.')
        chosen = []
        for code in codes:
            if code not in known:
                raise ValueError(f'Unknown symptom "{code}". Type triage symptoms to see the list.')
            if code not in chosen:                 # a code typed twice counts once
                chosen.append(code)
        return chosen
    return check


# ------------------------------------------------------------------ asking

def ask(prompt, check):
    """Ask until the answer passes the check. Only the failed question is repeated."""
    while True:
        try:
            return check(input(prompt))
        except ValueError as error:
            print(f'ERROR: {error}')


def format_case_id(number):
    return f'P-{number:04d}'


def new_case(state):
    """triage new: ask the questions one by one and add the case to state['cases'].
    Returns the Case, or None if the input ended before the case was complete."""
    known = state['symptoms']
    try:
        name = ask('Patient name: ', check_not_empty('Name'))
        age = ask('Age: ', check_age)
        city = ask('City: ', check_not_empty('City'))
        now = ask('Time now (HH:MM): ', parse_time)
        last_seen = ask('Last seen well (HH:MM): ', parse_time)

        def check_yesterday(text):
            yesterday = check_yes_no(text)
            if not yesterday and last_seen > now:
                raise ValueError(f'Last seen well ({format_time(last_seen)}) is after '
                                 f'the time now ({format_time(now)}). Was it yesterday?')
            return yesterday
        yesterday = ask('Was that yesterday? (yes/no): ', check_yesterday)

        symptoms = ask('Symptoms (comma separated): ', make_symptom_check(known))
    except EOFError:                              # input closed half way: no half-made case
        print()
        return None

    case_id = format_case_id(state['next_case_number'])
    state['next_case_number'] += 1                # the number is used up, never given out again
    case = Case(case_id, name, age, city, now, last_seen, yesterday, symptoms)
    assess(case, known, state['atlas'])
    state['cases'].append(case)
    try:
        save_cases(state['cases_path'], state['cases'])
    except OSError:
        state['cases'].pop()                      # not saved = not created
        state['next_case_number'] -= 1            # and its number was never given out
        print(f'ERROR: Could not save the case to {state["cases_path"]}.')
        return None
    print(f'SUCCESS: Case {case.id} created and saved.')
    print_assessment(case)
    return case


def format_time(minutes):
    """490 -> '08:10'"""
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


# ------------------------------------------------- Goal 4: the likely blocked pipe

def similarity(wanted, shown):
    """Bonus 1: symptoms in both lists / symptoms in either list, as an exact fraction
    (a Fraction never has rounding errors, so 60% is really 60%)."""
    return Fraction(len(wanted & shown), len(wanted | shown))


def whole_percent(fraction):
    return int(fraction * 100 + Fraction(1, 2))          # 2/3 -> 67, rounding halves up


def find_likely_pipe(atlas, symptoms):
    """Work backwards from the symptoms to ONE pipe.
    Returns (pipe or None, percent or None, closest).
      Exact match         -> (pipe, None, [])
      No exact, but close -> (pipe, percent, top 3 [(name, percent)])
      Nothing close       -> (None, None, top 3)

    We write no new blood rule. For each pipe we ask the Mission 2 engine
    (lesion.simulate) "what symptoms appear if ONLY this pipe is blocked?" and score
    how alike that is to the patient's symptoms. 100% means exactly the same set.
    Best score wins; a tie goes to the pipe that leaves the fewest pipes dry; still
    tied, the one listed first in the atlas (sorted() keeps the original order)."""
    wanted = set(symptoms)
    heart = atlas.find_heart()
    scored = []
    for pipe in atlas.pipes.values():               # atlas file order
        if pipe is heart:
            continue                                # the heart can never be blocked
        result = lesion.simulate(atlas, [pipe])
        scored.append((similarity(wanted, set(result.symptoms)), len(result.dry_pipes), pipe))
    if not scored:
        return None, None, []

    ranked = sorted(scored, key=lambda item: (-item[0], item[1]))
    best_score, _, best_pipe = ranked[0]
    if best_score == 1:
        return best_pipe, None, []                  # exact match: nothing more to show

    closest = [(pipe.name, whole_percent(score)) for score, _, pipe in ranked[:CLOSEST_SHOWN]]
    if best_score >= CLOSE_ENOUGH:
        return best_pipe, whole_percent(best_score), closest
    return None, None, closest


# ------------------------------------------------------- Goal 3: score and time

def band_for(severity):
    for lowest, name in BANDS:
        if severity >= lowest:
            return name


def timeline(clock, yesterday=False):
    """The trap of this mission, solved once: put every time on ONE timeline.
    08:10 today -> 490.   22:30 yesterday -> 1350 - 1440 = -90.
    Then comparing times and adding hours is plain arithmetic, even across midnight."""
    return clock - MINUTES_PER_DAY if yesterday else clock


def assess(case, known, atlas):
    """Fill in severity, band, the likely pipe and the two time limits. known: code -> Symptom."""
    case.severity = sum(known[code].points for code in case.symptoms)
    case.band = band_for(case.severity)

    set_times(case)

    pipe, case.match_percent, case.closest = find_likely_pipe(atlas, case.symptoms)
    case.likely_pipe = pipe.name if pipe else None
    case.big_pipe = pipe is not None and pipe.size == 'big'
    case.clot_possible = (case.clot_time_ok and case.big_pipe
                          and case.severity >= CLOT_MIN_SEVERITY)


def set_times(case):
    """The time limits depend only on the times typed, so they are worked out again
    (never trusted from a file) whenever a case is built."""
    seen = timeline(case.last_seen, case.yesterday)
    case.drug_until = seen + DRUG_WINDOW
    case.drug_possible = case.now <= case.drug_until        # equal to the limit still counts
    case.clot_until = seen + CLOT_WINDOW
    case.clot_time_ok = case.now <= case.clot_until


def format_limit(moment):
    """Timeline minutes -> '12:00', '07:30 tomorrow' or '22:30 yesterday'."""
    text = format_time(moment % MINUTES_PER_DAY)
    day = moment // MINUTES_PER_DAY
    if day == 1:
        return text + ' tomorrow'
    if day == -1:
        return text + ' yesterday'
    return text


def format_left(minutes):
    """200 -> '3 h 20 min'"""
    return f'{minutes // 60} h {minutes % 60:02d} min'


def drug_text(case):
    if case.drug_possible:
        left = case.drug_until - case.now
        return f'yes, until {format_limit(case.drug_until)} ({format_left(left)} left)'
    return f'no, the time limit passed at {format_limit(case.drug_until)}'


def clot_text(case):
    if case.clot_possible:
        return f'yes, until {format_limit(case.clot_until)}'
    if not case.clot_time_ok:
        return f'no, the time limit passed at {format_limit(case.clot_until)}'
    if case.likely_pipe is None:
        return 'no, the blocked pipe is unknown'
    if not case.big_pipe:
        return 'no, the blocked pipe is not big enough for the tool'
    return f'no, the severity is below {CLOT_MIN_SEVERITY}'


def pipe_text(case):
    if case.likely_pipe is None:
        if case.closest:
            return 'unknown, no pipe matches at 60% or more'
        return 'unknown, no single pipe matches these symptoms exactly'
    text = f'{case.likely_pipe} ({"big" if case.big_pipe else "small"})'
    if case.match_percent is not None:
        text += f', {case.match_percent}% match'
    return text


def print_field(label, value):
    print(f'{label + ":":<24}{value}')


def print_closest(case):
    if case.closest:                                     # Bonus 1: only after an inexact match
        print('No exact match. Closest pipes:')
        width = max(len(name) for name, _ in case.closest)
        for name, percent in case.closest:
            print(f'     {name.ljust(width)}  {percent}%')


def print_assessment(case):
    print_field('Severity', f'{case.severity} ({case.band})')
    print_closest(case)
    print_field('Likely blocked pipe', pipe_text(case))
    print_field('Drug possible', drug_text(case))
    print_field('Clot removal', clot_text(case))


# --------------------------------------------- Goal 5: save, load, list and show

class CaseFileError(Exception):
    """The cases file exists but cannot be read."""


def case_to_dict(case):
    return {
        'id': case.id,
        'name': case.name,
        'age': case.age,
        'city': case.city,
        'createdAt': format_time(case.created),
        'updatedAt': format_time(case.now),
        'lastSeenWell': format_time(case.last_seen),
        'lastSeenWellYesterday': case.yesterday,
        'symptoms': case.symptoms,
        'severity': case.severity,
        'band': case.band,
        'likelyPipe': case.likely_pipe,
        'bigPipe': case.big_pipe,
        'matchPercent': case.match_percent,
        'closestPipes': [{'pipe': name, 'percent': percent} for name, percent in case.closest],
        'drugUntil': format_limit(case.drug_until),
        'drugPossible': case.drug_possible,
        'clotUntil': format_limit(case.clot_until),
        'clotPossible': case.clot_possible,
        'history': case.history,
        'route': case.route,
        'hospitalStay': case.hospital_stay,
    }


def case_from_dict(data):
    """Rebuild a Case. The inputs and the answers come from the file; the time
    limits are recalculated from the inputs."""
    case = Case(data['id'], data['name'], data['age'], data['city'],
                parse_time(data['createdAt']), parse_time(data['lastSeenWell']),
                data['lastSeenWellYesterday'], list(data['symptoms']))
    case.severity = data['severity']
    case.band = data['band']
    case.likely_pipe = data['likelyPipe']
    case.big_pipe = data['bigPipe']
    case.match_percent = data.get('matchPercent')            # absent in files saved before Bonus 1
    case.closest = [(item['pipe'], item['percent']) for item in data.get('closestPipes', [])]
    case.clot_possible = data['clotPossible']
    case.now = parse_time(data.get('updatedAt', data['createdAt']))   # absent before Bonus 2
    case.history = data.get('history', [])
    case.route = data.get('route')                          # absent before Mission 4
    case.hospital_stay = data.get('hospitalStay')           # absent before Mission 5
    set_times(case)
    return case


def load_cases(path):
    """Read every saved case. No file yet means no cases yet."""
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        return [case_from_dict(item) for item in data['cases']]
    except FileNotFoundError:
        return []
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise CaseFileError(f'Could not read {path} ({error}).')


def save_cases(path, cases):
    """Write to a temporary file first, then swap it in, so a crash half way
    through can never leave a half-written cases file."""
    temporary = path + '.tmp'
    with open(temporary, 'w', encoding='utf-8') as f:
        json.dump({'cases': [case_to_dict(c) for c in cases]}, f, indent=4, ensure_ascii=False)
    os.replace(temporary, path)


def next_number(cases):
    """One more than the highest id ever saved, so an id is never reused."""
    numbers = [int(c.id[2:]) for c in cases if re.fullmatch(r'P-\d+', c.id)]
    return max(numbers, default=0) + 1


def show_list(cases):
    if not cases:
        print('No cases yet.')
        return
    rows = [[c.id, c.name, str(c.age), c.city, f'{c.severity} {c.band}', c.likely_pipe or 'unknown']
            for c in cases]
    print_table(['ID', 'NAME', 'AGE', 'CITY', 'SEVERITY', 'LIKELY PIPE'], rows)


def show_case(cases, case_id):
    for case in cases:
        if case.id == case_id.upper():
            break
    else:
        raise ValueError(f'No case called "{case_id}".')

    seen = format_time(case.last_seen) + (' yesterday' if case.yesterday else '')
    print(f'=== Case {case.id}: {case.name} ===')
    print_field('Age', case.age)
    print_field('City', case.city)
    print_field('Created at', format_time(case.created))
    print_field('Last seen well', seen)
    print_field('Symptoms', ', '.join(case.symptoms))
    print_assessment(case)
    if case.history:                                     # Bonus 2
        print('History:')
        for entry in case.history:
            print(f'  {entry["time"]}  added {", ".join(entry["added"]) or "nothing new"}; '
                  f'severity {entry["severityWas"]} -> {entry["severityNow"]}; '
                  f'pipe {entry["pipeWas"]} -> {entry["pipeNow"]}')


# ------------------------------------------------ Bonus 2: the patient gets worse

def find_case(cases, case_id):
    for case in cases:
        if case.id == case_id.upper():
            return case
    raise ValueError(f'No case called "{case_id}".')


def update_case(state, case_id):
    """triage update <id>: ask the new time and the new symptoms, add them to the case and
    work everything out again. Every update is kept in the case history."""
    case = find_case(state['cases'], case_id)
    known = state['symptoms']

    def check_later(text):
        moment = parse_time(text)
        if moment < case.now:                          # time cannot run backwards
            raise ValueError(f'Time now ({format_time(moment)}) is earlier than the last '
                             f'time recorded for this case ({format_time(case.now)}).')
        return moment

    try:
        now = ask('Time now (HH:MM): ', check_later)
        new_symptoms = ask('New symptoms (comma separated): ', make_symptom_check(known))
    except EOFError:
        print()
        return None

    backup = copy.deepcopy(case.__dict__)             # so a failed save can be undone
    was_severity, was_band, was_pipe = case.severity, case.band, case.likely_pipe
    had_route = case.route is not None
    case.route = None                                 # it was worked out from the old data
    case.hospital_stay = None                         # and so were the hospital times

    added = [code for code in new_symptoms if code not in case.symptoms]
    case.symptoms = case.symptoms + added             # a symptom already there counts once
    case.now = now
    assess(case, known, state['atlas'])
    case.history.append({
        'time': format_time(now),
        'added': added,
        'severityWas': was_severity,
        'severityNow': case.severity,
        'pipeWas': was_pipe or 'unknown',
        'pipeNow': case.likely_pipe or 'unknown',
    })

    try:
        save_cases(state['cases_path'], state['cases'])
    except OSError:
        case.__dict__.clear()
        case.__dict__.update(backup)                  # not saved = not updated
        print(f'ERROR: Could not save the case to {state["cases_path"]}.')
        return None

    print(f'SUCCESS: Case {case.id} updated and saved.')
    severity = f'{case.severity} ({case.band})'
    if case.severity != was_severity:
        severity += f', was {was_severity}'
    print_field('Severity', severity)
    print_closest(case)
    pipe = pipe_text(case)
    if case.likely_pipe != was_pipe:
        pipe += f', was {was_pipe or "unknown"}'
    print_field('Likely blocked pipe', pipe)
    print_field('Drug possible', drug_text(case))
    print_field('Clot removal', clot_text(case))
    if had_route:
        print(f'The saved route is out of date. Run: route {case.id}')
    return case


# --------------------------------------------------- Bonus 3: most urgent first

def print_rows(rows):
    """Indented, aligned columns, no header."""
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    for row in rows:
        print('   ' + '  '.join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip())


def show_urgent(cases):
    """triage urgent: ask the time now, list the cases that can still be treated,
    the shortest time left first. Uses the time typed here, not each case's own time."""
    if not cases:
        print('No cases yet.')
        return
    try:
        now = ask('Time now (HH:MM): ', parse_time)
    except EOFError:
        print()
        return

    with_drug = []                                    # (minutes left, case)
    clot_only = []
    for case in cases:
        if now <= case.drug_until:                    # equal to the limit still counts
            with_drug.append((case.drug_until - now, case, case.drug_until))
        elif now <= case.clot_until and case.big_pipe and case.severity >= CLOT_MIN_SEVERITY:
            clot_only.append((case.clot_until - now, case, case.clot_until))

    if not with_drug and not clot_only:
        print('No case can be treated any more.')
        return
    for title, group in (('Drug still possible:', with_drug),
                         ('Only clot removal still possible:', clot_only)):
        if not group:
            continue
        print(title)
        group.sort(key=lambda item: item[0])          # shortest time left first (stable)
        print_rows([[f'{case.id} {case.name}', f'until {format_limit(until)}',
                     f'{format_left(left)} left'] for left, case, until in group])


# ------------------------------------------------ Mission 4, Goal 3: route a case

def route_to_dict(decision):
    """What is saved inside the case (Mission 5 reads 'arrives', Mission 7 prints it all).
    The top-level keys always describe the LAST hospital, where the clot is removed."""
    plan = decision.chosen
    saved = {
        'plan': 'drug first, then transfer' if plan.stop else 'straight',
        'goal': {'clot': 'clot removal', 'drug': 'drug', 'scan': 'scan'}[plan.goal],
        'hospital': plan.hospital.name,
        'path': plan.path,
        'driveMinutes': plan.drive,
        'leaves': format_limit(plan.leaves),
        'arrives': format_limit(plan.arrives),
        'drugAt': None if plan.drug_at is None else format_limit(plan.drug_at),
        'clotRemovalAt': None if plan.clot_at is None else format_limit(plan.clot_at),
    }
    if plan.stop:
        saved['firstStop'] = {
            'hospital': plan.stop.hospital.name,
            'path': plan.stop.path,
            'driveMinutes': plan.stop.drive,
            'arrives': format_limit(plan.stop.arrives),
            'drugAt': format_limit(plan.stop.drug_at),
        }
    return saved


def way_text(path):
    return f'inside {path[0]}' if len(path) == 1 else ' -> '.join(path)


def print_header(case, plan):
    print(f'Case {case.id}: {case.name}, {case.city}, leaves at {format_limit(plan.leaves)}')


def print_plan(case, plan, with_header=True):
    needs = []
    if case.clot_possible:
        needs.append(f'clot removal (until {format_limit(case.clot_until)})')
    if case.drug_possible:
        needs.append(f'drug (until {format_limit(case.drug_until)})')
    if case.clot_possible and case.drug_possible:
        text = 'Needs: ' + ', '.join(needs)
    elif case.clot_possible:
        text = f'Needs: {needs[0]}. The drug limit has passed.'
    elif case.drug_possible:
        text = f'Needs: {needs[0]}. Clot removal is not possible.'
    else:
        text = 'Needs: no treatment is possible any more, only a scan and care.'

    if with_header:
        print_header(case, plan)
        print()
        print(text)
        name = plan.hospital.name
        if plan.goal == 'clot':
            print(f'Fastest hospital that can remove the clot: {name}')
        elif plan.goal == 'drug':
            print(f'Fastest hospital that can give the drug in time: {name}')
        else:
            print(f'No hospital can give any treatment in time. Fastest hospital with a CT: {name}')
        print()

    row = lambda label, value: print(f'{label + ":":<14}{value}')
    row('Route', f'{way_text(plan.path)}, {plan.drive} min')
    row('Arrives', format_limit(plan.arrives))
    if plan.drug_at is not None:
        row('Drug', format_limit(plan.drug_at))
    elif case.drug_possible and plan.goal == 'clot':
        if plan.hospital.can('DRUG'):
            row('Drug', f'too late (limit {format_limit(case.drug_until)})')
        else:
            row('Drug', 'not given at this hospital')
    if plan.clot_at is not None:
        row('Clot removal', format_limit(plan.clot_at))
    print()


def print_comparison(case, decision):
    """Bonus 1: show both plans, then which one was chosen and why."""
    a, b = decision.straight, decision.transfer
    print_header(case, a)
    if a.drug_at is not None:
        drug_a = f'drug {format_limit(a.drug_at)}'
    elif a.hospital.can('DRUG'):
        drug_a = 'drug too late'
    else:
        drug_a = 'no drug at this hospital'
    print(f'Plan A, straight to clot removal: {a.hospital.name}')
    print(f'   Arrives {format_limit(a.arrives)} - {drug_a} - clot removal {format_limit(a.clot_at)}')
    print('Plan B, drug first, then transfer:')
    print(f'   {b.stop.hospital.name} ({way_text(b.stop.path)}): arrives '
          f'{format_limit(b.stop.arrives)} - drug {format_limit(b.stop.drug_at)}')
    print(f'   Transfer leaves {format_limit(b.leaves)} -> {" -> ".join(b.path)}, {b.drive} min')
    print(f'   {b.hospital.name}: arrives {format_limit(b.arrives)} - '
          f'clot removal {format_limit(b.clot_at)}')
    letter = 'B' if decision.chosen is b else 'A'
    print(f'Chosen: Plan {letter}. {decision.reason}')
    if letter == 'A':                                  # Plan B lines already show the whole trip
        print()
        print_plan(case, a, with_header=False)


def route_case(state, case_id):
    """route <id>: choose the hospital and save the route inside the case."""
    case = find_case(state['cases'], case_id)
    decision = routing.plan_route(case, state['roads'], state['hospitals'])
    if decision.transfer is not None:
        print_comparison(case, decision)
    else:
        print_plan(case, decision.chosen)

    old_route = case.route
    case.route = route_to_dict(decision)
    try:
        save_cases(state['cases_path'], state['cases'])
    except OSError:
        case.route = old_route                        # not saved = not routed
        print(f'ERROR: Could not save the case to {state["cases_path"]}.')
        return None
    print(f'SUCCESS: Route saved for {case.id}.')
    return decision


# ------------------------------------------------------- Bonus 3: route whatif

ABILITY_PHRASES = {'CT': 'do CT scans', 'DRUG': 'give the drug', 'CLOT': 'remove clots'}


def route_whatif(state, typed_city, typed_ability):
    """route whatif <city> <ability>: what would change for every saved case that can still
    get clot removal, if the hospital in that city could do one more thing.
    Nothing is written anywhere: the change exists only in a copy of the hospital list."""
    roads, hospitals = state['roads'], state['hospitals']
    ability = typed_ability.upper()
    if ability not in roadmap.ABILITIES:
        raise ValueError(f'Unknown ability "{typed_ability}". Expected CT, DRUG or CLOT.')
    city = routing.find_city(roads, typed_city)
    if city is None:
        raise ValueError(f'The city "{typed_city}" is not on the map.')
    in_city = [h for h in hospitals if h.city == city]
    if not in_city:
        raise ValueError(f'There is no hospital in {city}.')
    candidates = [h for h in in_city if ability not in h.abilities]
    if not candidates:
        names = ', '.join(h.name for h in in_city)
        print(f'{names} can already {ABILITY_PHRASES[ability]}. Nothing would change.')
        return
    chosen = candidates[0]                          # the first hospital in the city that lacks it
    if ability == 'DRUG' and 'CT' not in chosen.abilities:
        raise ValueError(f'{chosen.name} cannot give the DRUG without a CT (a hospital that '
                         f'gives the DRUG must also have CT).')

    changed = routing.with_ability(hospitals, chosen, ability)
    print(f'What if {chosen.name} ({city}) could also {ABILITY_PHRASES[ability]}?')
    print()

    rows, skipped = [], []
    total_saved = counted = 0
    for case in state['cases']:
        if not case.clot_possible:
            continue
        start = routing.find_city(roads, case.city)
        if start is None:
            skipped.append(f'{case.id} skipped: its city "{case.city}" is not on the map.')
            continue
        now = routing.clot_drive(roads, hospitals, start)
        after = routing.clot_drive(roads, changed, start)
        if now is None or after is None:
            saved_text = 'n/a'
        else:
            saved_text = f'{now - after} min'
            total_saved += now - after
            counted += 1
        rows.append([case.id, case.city, 'none' if now is None else f'{now} min',
                     'none' if after is None else f'{after} min', saved_text])

    if not rows:
        print('No saved case can still get clot removal, so nothing can be compared.')
    else:
        print_table(['CASE', 'CITY', 'NOW', 'WITH THE CHANGE', 'SAVED'], rows)
        print()
        print(f'Total saved: {total_saved} min over {counted} case{"" if counted == 1 else "s"}.')
    for note in skipped:
        print(note)



# ------------------------------------------------------ Mission 5: the stroke unit

def parse_limit(text):
    """'10:00' -> 600.   '07:30 tomorrow' -> 1830.   '22:30 yesterday' -> -90."""
    clock, _, day = text.partition(' ')
    minutes = parse_time(clock)
    if day == 'tomorrow':
        return minutes + MINUTES_PER_DAY
    if day == 'yesterday':
        return minutes - MINUTES_PER_DAY
    return minutes


def stay_to_dict(stay):
    show = lambda value: None if value is None else format_limit(value)
    return {
        'hospital': unit.UNIT_HOSPITAL,
        'arrives': format_limit(stay.patient.arrival),
        'scanAt': show(stay.scan_start),
        'drugAt': show(stay.drug_at),
        'doorToDrugMinutes': stay.door_to_drug,
        'clotRemovalAt': show(stay.clot_start),
    }


def run_unit(state, filename):
    """unit run <file>: replay the morning, print it, and save the times inside the cases."""
    taken = {case.id for case in state['cases']}
    try:
        from_file = unit.read_events(filename, taken)
    except unit.UnitError as error:
        for message in error.messages:
            print(f'ERROR: {message}')
        return
    from_cases, notes, elsewhere = unit.patients_from_cases(state['cases'], parse_limit)
    for note in notes:                                   # a message; the morning still runs
        print(note)

    patients = from_file + from_cases
    if not patients:
        print('No patients arrive this morning.')
        return

    stays = unit.run_morning(patients)
    print(f'{unit.UNIT_HOSPITAL} - 1 CT scanner - first come, first served')
    detail = f'{len(patients)} patient{"" if len(patients) == 1 else "s"}: {len(from_file)} from {os.path.basename(filename)}, ' \
             f'{len(from_cases)} from your cases'
    if elsewhere:
        verb = 'goes' if len(elsewhere) == 1 else 'go'
        detail += f' ({", ".join(elsewhere)} {verb} to another hospital)'
    print(detail)
    print()
    for line in unit.collect_events(stays, format_limit):
        print(line)
    print()
    print_table(['PATIENT', 'ARRIVES', 'SCAN', 'DRUG', 'DOOR-TO-DRUG', 'CLOT REMOVAL', 'NOTE'],
                unit.table_rows(stays, format_limit))
    print()
    print(unit.summary_line(stays))

    saved = [stay for stay in stays.values() if stay.patient.case is not None]
    if not saved:
        return
    old = {stay.patient.case.id: stay.patient.case.hospital_stay for stay in saved}
    for stay in saved:
        stay.patient.case.hospital_stay = stay_to_dict(stay)   # a new run replaces the old times
    try:
        save_cases(state['cases_path'], state['cases'])
    except OSError:
        for stay in saved:
            stay.patient.case.hospital_stay = old[stay.patient.case.id]
        print(f'ERROR: Could not save the case to {state["cases_path"]}.')
        return
    ids = sorted(stay.patient.case.id for stay in saved)
    print(f'SUCCESS: Hospital times saved for {", ".join(ids)}.')
