"""Mission 5: one morning at the stroke unit of Qendra Neuro Tirana.

Goal 1  read the day's patients (a file of arrivals + the saved cases routed here)
Goal 2  replay the morning: one CT scanner and one clot removal room
Goal 3  save the hospital times inside the cases

The fixed times are the PDF's numbers, in one place below.
"""

import os
import re

from loader import read_atlas_file

UNIT_HOSPITAL = 'Qendra Neuro Tirana'

SCAN_MINUTES = 15               # a scan takes
DRUG_AFTER_SCAN = 15            # from the end of the scan to the drug
CLOT_READY_AFTER_SCAN = 45      # from the end of the scan until the clot room can start
CLOT_MINUTES = 60               # clot removal takes
TRANSFER_READY_AFTER_ARRIVAL = 30   # a patient transferred after the drug (Mission 4, Bonus 1)
SLOW_OVER = 60                  # door-to-drug above this is SLOW

DRUG_WINDOW = 4 * 60 + 30       # drug limit = last seen well + 4 h 30 min
MINUTES_PER_DAY = 24 * 60
CLOT_MIN_SEVERITY = 5           # clot removal needs severity 5 or more (and a big pipe)

EVENT_FIELDS = 7
PATIENT_TYPES = ('stroke', 'head')
HEAD_SCAN_WITHIN = 60           # a head injury must be scanned within this of arrival
SCAN_LATEST_FOR_DRUG = SCAN_MINUTES + DRUG_AFTER_SCAN   # drug limit - 30 min = the last moment the scan can start
TIME_FORMAT = re.compile(r'(\d\d):(\d\d)')


class UnitError(Exception):
    """A bad events file. 'messages' holds EVERY problem we found."""

    def __init__(self, messages):
        super().__init__('\n'.join(messages))
        self.messages = messages


class Patient:
    def __init__(self, patient_id, arrival, severity, drug_limit, needs_clot, source,
                 case=None, transferred_from=None, kind='stroke'):
        self.kind = kind                    # 'stroke' or 'head' (a head injury: scan only)
        self.id = patient_id
        self.arrival = arrival              # minutes on the day's timeline (0 = midnight today)
        self.severity = severity
        self.drug_limit = drug_limit        # last moment the drug can be given
        self.needs_clot = needs_clot
        self.source = source                # 'file' or 'case'
        self.case = case                    # the Case object for a patient from the database
        self.transferred_from = transferred_from   # first hospital's name when the drug was already given


class Stay:
    """What happened to one patient in the hospital."""

    def __init__(self, patient):
        self.patient = patient
        self.scan_start = None
        self.drug_at = None
        self.clot_start = None

    @property
    def scan_wait(self):
        return None if self.scan_start is None else self.scan_start - self.patient.arrival

    @property
    def late_head_scan(self):
        return (self.patient.kind == 'head' and self.scan_start is not None
                and self.scan_wait > HEAD_SCAN_WITHIN)

    @property
    def door_to_drug(self):
        return None if self.drug_at is None else self.drug_at - self.patient.arrival


# ------------------------------------------------------------ Goal 1: reading

def parse_clock(text):
    match = TIME_FORMAT.fullmatch(text)
    if not match or int(match.group(1)) > 23 or int(match.group(2)) > 59:
        return None
    return int(match.group(1)) * 60 + int(match.group(2))


def read_events(filename, taken_ids=()):
    """Read the arrivals file. Returns a list of Patients (maybe empty).
    Raises UnitError listing ALL problems.  taken_ids: case ids already in the database."""
    try:
        records = read_atlas_file(filename)
    except FileNotFoundError:
        raise UnitError([f'File not found: {filename}'])
    except UnicodeDecodeError:
        raise UnitError([f'{filename} is not a text file.'])

    name = os.path.basename(filename)
    patients = []
    errors = []
    first_seen = {}                                     # patient id -> line

    for lineno, parts in records:
        where = f'{name}, line {lineno}'
        if parts[0] != 'ARRIVAL':
            errors.append(f'{where}: unknown record type "{parts[0]}". Expected ARRIVAL.')
            continue
        if len(parts) != EVENT_FIELDS:
            errors.append(f'{where}: ARRIVAL needs {EVENT_FIELDS} fields, found {len(parts)}.')
            continue

        _, time_text, patient_id, kind, severity_text, seen_text, pipe_text = parts
        problems = []
        head = kind == 'head'                           # a head injury has '-' in the last three fields

        arrival = parse_clock(time_text)
        if arrival is None:
            problems.append(f'invalid time "{time_text}". Use HH:MM.')
        if not patient_id:
            problems.append('the patient id is empty.')
        elif patient_id in first_seen:
            problems.append(f'patient {patient_id} is listed twice (first on line '
                            f'{first_seen[patient_id]}).')
        elif patient_id in taken_ids:
            problems.append(f'patient {patient_id} is already a case in your database.')
        if kind not in PATIENT_TYPES:
            problems.append(f'unknown patient type "{kind}". Expected {", ".join(PATIENT_TYPES)}.')
        seen = None
        if not head:
            if not (severity_text.isascii() and severity_text.isdigit()):
                problems.append(f'severity must be a whole number, found "{severity_text}".')
            seen = parse_clock(seen_text)
            if seen is None:
                problems.append(f'invalid time "{seen_text}". Use HH:MM.')
            if pipe_text not in ('yes', 'no'):
                problems.append('big pipe must be yes or no.')

        for problem in problems:
            errors.append(f'{where}: {problem}')
        if patient_id and patient_id not in first_seen:
            first_seen[patient_id] = lineno
        if problems:
            continue

        if head:
            patients.append(Patient(patient_id, arrival, 0, None, False, 'file', kind='head'))
            continue
        severity = int(severity_text)
        if seen > arrival:                              # the file has no "yesterday" column:
            seen -= MINUTES_PER_DAY                     # last seen later than the arrival means yesterday
        patients.append(Patient(patient_id, arrival, severity, seen + DRUG_WINDOW,
                                pipe_text == 'yes' and severity >= CLOT_MIN_SEVERITY, 'file'))

    if errors:
        raise UnitError(errors)
    return patients


def patients_from_cases(cases, parse_limit):
    """The saved cases routed to this hospital.
    Returns (patients, notes, other) -- notes are messages, other = ids that go elsewhere."""
    patients, notes, other = [], [], []
    for case in cases:
        if case.route is None:
            notes.append(f'Case {case.id} has no route yet. Run route {case.id} first. Skipped.')
        elif case.route['hospital'] != UNIT_HOSPITAL:
            other.append(case.id)
        else:
            stop = case.route.get('firstStop')
            patients.append(Patient(case.id, parse_limit(case.route['arrives']), case.severity,
                                    case.drug_until, case.clot_possible, 'case', case,
                                    stop['hospital'] if stop else None))
    return patients, notes, other


# ---------------------------------------------------------- Goal 2: the morning

def deadline_key(patient):
    """Bonus 1: who is scanned next when several wait. Smallest key goes first."""
    if patient.kind == 'stroke' and patient.drug_limit - SCAN_LATEST_FOR_DRUG >= patient.arrival:
        deadline = patient.drug_limit - SCAN_LATEST_FOR_DRUG    # the last moment the scan can start
    else:
        deadline = patient.arrival + HEAD_SCAN_WITHIN           # nothing to save: a fair wait
    return (deadline, -patient.severity, patient.arrival, patient.id)


ORDERS = {'fcfs': None, 'deadline': deadline_key}
ORDER_NAMES = {'fcfs': 'first come, first served', 'deadline': 'deadline first'}


def run_morning(patients, scanners=1, key=None):
    """Replay the morning. Returns {patient id: Stay}.

    Scanner: whenever one is free and someone is waiting, it takes the next patient.
    'key' decides who is next (default: first come, first served, then the smaller id).
    Everything that arrives by time t joins the line BEFORE the choice at t, so a patient
    arriving the very minute a scanner frees is already in the line.
    Clot room: one patient at a time, whoever was ready first."""
    key = key or (lambda p: (p.arrival, p.id))
    stays = {p.id: Stay(p) for p in patients}

    to_scan = sorted((p for p in patients if p.transferred_from is None),
                     key=lambda p: (p.arrival, p.id))
    free_at = [float('-inf')] * scanners
    waiting, index, now = [], 0, float('-inf')
    scan_end = {}

    while index < len(to_scan) or waiting:
        if not waiting:
            now = max(now, to_scan[index].arrival)          # idle: jump to the next arrival
        else:
            now = max(now, min(free_at))                    # busy: jump to the next free scanner
        while index < len(to_scan) and to_scan[index].arrival <= now:
            waiting.append(to_scan[index])
            index += 1
        while waiting:
            free = [s for s in range(scanners) if free_at[s] <= now]
            if not free:
                break
            patient = min(waiting, key=key)
            waiting.remove(patient)
            free_at[free[0]] = now + SCAN_MINUTES
            stays[patient.id].scan_start = now
            scan_end[patient.id] = now + SCAN_MINUTES

    ready = []                                              # (ready time, id) for the clot room
    for patient in patients:
        stay = stays[patient.id]
        if patient.kind == 'head':
            continue                                        # a head injury only needs the scan
        if patient.transferred_from is None:
            drug_time = scan_end[patient.id] + DRUG_AFTER_SCAN
            if drug_time <= patient.drug_limit:
                stay.drug_at = drug_time
            if patient.needs_clot:
                ready.append((scan_end[patient.id] + CLOT_READY_AFTER_SCAN, patient.id))
        elif patient.needs_clot:                            # scanned and drugged elsewhere
            ready.append((patient.arrival + TRANSFER_READY_AFTER_ARRIVAL, patient.id))

    room_free = float('-inf')
    for ready_at, patient_id in sorted(ready):
        start = max(room_free, ready_at)
        stays[patient_id].clot_start = start
        room_free = start + CLOT_MINUTES
    return stays


# ------------------------------------------------------------------ the report

def could_get_drug(stay):
    """The drug was still possible when the patient arrived (and not given before)."""
    patient = stay.patient
    return (patient.kind == 'stroke' and patient.transferred_from is None
            and patient.drug_limit >= patient.arrival)


def collect_events(stays, clock):
    """(time, rank, id, text): sorted by time; in one minute arrivals come first, then scans,
    then drugs, then clot removal."""
    events = []
    for stay in stays.values():
        patient = stay.patient
        arrives = f'{patient.id} arrives'
        if patient.transferred_from:
            arrives += f' (transferred, drug already given at {patient.transferred_from})'
        events.append((patient.arrival, 0, patient.id, arrives))
        if stay.scan_start is not None:
            late = f' (LATE: waited {stay.scan_wait} min)' if stay.late_head_scan else ''
            events.append((stay.scan_start, 1, patient.id, f'{patient.id} scan starts{late}'))
        if stay.drug_at is not None:
            events.append((stay.drug_at, 2, patient.id,
                           f'{patient.id} drug given ({stay.door_to_drug} min after arrival)'))
        elif could_get_drug(stay):
            events.append((patient.drug_limit, 2, patient.id,
                           f'{patient.id} drug limit passed before the drug could be given'))
        if stay.clot_start is not None:
            events.append((stay.clot_start, 3, patient.id, f'{patient.id} clot removal starts'))
    events.sort()
    return [f'{clock(time)}  {text}' for time, _, _, text in events]


def table_rows(stays, clock):
    rows = []
    for stay in sorted(stays.values(), key=lambda s: (s.patient.arrival, s.patient.id)):
        patient = stay.patient
        notes = []
        if patient.kind == 'head':
            notes.append(f'head injury, scan after {stay.scan_wait} min')
            if stay.late_head_scan:
                notes.append('SCAN LATE')
        elif patient.transferred_from:
            notes.append(f'drug given at {patient.transferred_from}')
        elif stay.drug_at is None:
            if patient.drug_limit < patient.arrival:
                notes.append('drug limit passed before arrival')
            else:
                notes.append(f'MISSED THE DRUG (limit {clock(patient.drug_limit)})')
        if stay.door_to_drug is not None and stay.door_to_drug > SLOW_OVER:
            notes.append('SLOW')
        show = lambda value: '-' if value is None else clock(value)
        rows.append([patient.id, clock(patient.arrival), show(stay.scan_start), show(stay.drug_at),
                     '-' if stay.door_to_drug is None else f'{stay.door_to_drug} min',
                     show(stay.clot_start), '; '.join(notes)])
    return rows


def summary_line(stays):
    eligible = [s for s in stays.values() if could_get_drug(s)]
    if not eligible:
        return 'No patient could get the drug.'
    given = [s for s in eligible if s.drug_at is not None]
    text = f'Drug given to {len(given)} of {len(eligible)} patients who could get it.'
    if given:
        average = sum(s.door_to_drug for s in given) / len(given)
        text += f' Average door-to-drug: {int(average + 0.5)} min.'
    return text


def head_summary(stays):
    """The head injuries scanned late, or None when there are no head injuries."""
    heads = [s for s in stays.values() if s.patient.kind == 'head']
    if not heads:
        return None
    late = sorted(s.patient.id for s in heads if s.late_head_scan)
    return 'Head scans late: ' + (', '.join(late) if late else 'none')


def missed_ids(stays):
    return sorted(s.patient.id for s in stays.values() if could_get_drug(s) and s.drug_at is None)


def compare_rows(one, two):
    """Bonus 2: the two mornings side by side, as table rows."""
    def figures(stays):
        eligible = [s for s in stays.values() if could_get_drug(s)]
        given = [s for s in eligible if s.drug_at is not None]
        average = f'{int(sum(s.door_to_drug for s in given) / len(given) + 0.5)} min' if given else '-'
        slow = sorted(s.patient.id for s in given if s.door_to_drug > SLOW_OVER)
        missed = missed_ids(stays)
        late = head_summary(stays)
        return [f'{len(given)} of {len(eligible)}', average, ', '.join(slow) or 'none',
                ', '.join(missed) or 'none', None if late is None else late.split(': ', 1)[1]]
    a, b = figures(one), figures(two)
    labels = ['Drug given', 'Average door-to-drug', 'SLOW (over 60 min)', 'Missed the drug',
              'Head scans late']
    return [[label, x, y] for label, x, y in zip(labels, a, b) if x is not None]
