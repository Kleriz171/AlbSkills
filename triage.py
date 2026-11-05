"""Mission 3, Goal 2: create a case.

Every answer is checked as soon as it is typed. A wrong answer prints
"ERROR: ..." and asks the SAME question again, so nothing typed before is lost.
"""

import re

MAX_AGE = 120
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
    state['cases'].append(case)
    print(f'SUCCESS: Case {case.id} created.')
    return case


def format_time(minutes):
    """490 -> '08:10'"""
    return f'{minutes // 60:02d}:{minutes % 60:02d}'
