"""Mission 3, Goal 2: create a case.

Every answer is checked as soon as it is typed. A wrong answer prints
"ERROR: ..." and asks the SAME question again, so nothing typed before is lost.
"""

import re

import lesion

MAX_AGE = 120

# The rules of Goal 3. They are numbers from the PDF, kept in one place,
# so a changed rule is a one-line change.
MINUTES_PER_DAY = 24 * 60
DRUG_WINDOW = 4 * 60 + 30            # the drug works up to 4 h 30 min after last seen well
CLOT_WINDOW = 24 * 60                # clot removal works up to 24 h after last seen well
CLOT_MIN_SEVERITY = 5                # clot removal needs severity 5 or more
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
        self.now = now                    # minutes after midnight, "today"
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
        self.likely_pipe = None           # Pipe object, or None when unknown (Goal 4)
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
    print(f'SUCCESS: Case {case.id} created.')
    print_assessment(case)
    return case


def format_time(minutes):
    """490 -> '08:10'"""
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


# ------------------------------------------------- Goal 4: the likely blocked pipe

def find_likely_pipe(atlas, symptoms):
    """Work backwards from the symptoms to ONE pipe, or None.

    We write no new blood rule. For each pipe we ask the Mission 2 engine
    (lesion.simulate) "what symptoms appear if ONLY this pipe is blocked?" and keep
    the pipes whose answer is EXACTLY the patient's symptoms, in any order.
    Several match? The one that leaves the fewest pipes dry wins; still tied, the
    one listed first in the atlas (min() keeps the first of equal items)."""
    wanted = set(symptoms)
    heart = atlas.find_heart()
    matches = []
    for pipe in atlas.pipes.values():               # atlas file order
        if pipe is heart:
            continue                                # the heart can never be blocked
        result = lesion.simulate(atlas, [pipe])
        if set(result.symptoms) == wanted:
            matches.append((len(result.dry_pipes), pipe))
    if not matches:
        return None
    return min(matches, key=lambda match: match[0])[1]


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

    seen = timeline(case.last_seen, case.yesterday)
    case.drug_until = seen + DRUG_WINDOW
    case.drug_possible = case.now <= case.drug_until        # equal to the limit still counts
    case.clot_until = seen + CLOT_WINDOW
    case.clot_time_ok = case.now <= case.clot_until

    case.likely_pipe = find_likely_pipe(atlas, case.symptoms)
    big_pipe = case.likely_pipe is not None and case.likely_pipe.size == 'big'
    case.clot_possible = (case.clot_time_ok and big_pipe
                          and case.severity >= CLOT_MIN_SEVERITY)


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
    if case.likely_pipe.size != 'big':
        return 'no, the blocked pipe is not big enough for the tool'
    return f'no, the severity is below {CLOT_MIN_SEVERITY}'


def pipe_text(case):
    if case.likely_pipe is None:
        return 'unknown, no single pipe matches these symptoms exactly'
    return f'{case.likely_pipe.name} ({case.likely_pipe.size})'


def print_field(label, value):
    print(f'{label + ":":<24}{value}')


def print_assessment(case):
    print_field('Severity', f'{case.severity} ({case.band})')
    print_field('Likely blocked pipe', pipe_text(case))
    print_field('Drug possible', drug_text(case))
    print_field('Clot removal', clot_text(case))
