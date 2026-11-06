"""Mission 6, Goal 2: the three brain tests.

Each test is its own class and returns ONE number. They all work the same way
(a BrainTest with a key, a title, instructions and run()), so the clinic can run them
one after another in a loop: Goal 3 only has to go through ALL_TESTS.

  reaction   average milliseconds          lower is better
  memory     longest row of digits         higher is better
  colorword  seconds (with a penalty)      lower is better

All the numbers from the PDF are constants at the top. Everything that touches the
real world (screen, keyboard, clock, random numbers, waiting) goes through a small
'io' object, so the same code can be played by hand or driven by a script.
"""

import os
import random
import sys
import time

# ---- reaction time
REACTION_ROUNDS = 5
WAIT_MIN = 1                    # seconds: the wait before the * is random between these two
WAIT_MAX = 3
TOO_SOON_MS = 100               # ENTER faster than this was pressed before the *

# ---- memory span
MEMORY_START = 3                # digits in the first row
MEMORY_MAX = 9                  # the longest row
SECONDS_PER_DIGIT = 1           # how long a row stays on screen, per digit

# ---- colour words
COLOUR_ROUNDS = 10
COLOUR_MIN_DIFFERENT = 7        # in at least this many rounds the ink differs from the word
WRONG_PENALTY = 2               # seconds added for every wrong answer

# word -> ANSI colour code of the ink. The first letter of the word is the key the patient types.
COLOURS = {'RED': 31, 'BLUE': 34, 'GREEN': 32, 'YELLOW': 33}   # the PDF's order
ANSWER_KEYS = {word[0].lower(): word for word in COLOURS}       # r, g, y, b


class ConsoleIO:
    """The real screen, keyboard and clocks."""

    def __init__(self):
        self.rng = random.Random()
        if os.name == 'nt':
            os.system('')           # switches the Windows console to understand colour codes

    def say(self, text='', end='\n'):
        print(text, end=end, flush=True)

    def ask(self, prompt=''):
        return input(prompt)

    def wait(self, seconds):
        time.sleep(seconds)

    def now(self):
        """A clock made for timing: perf_counter is precise to far less than a millisecond
        (time.time() can be as coarse as 15 ms on Windows) and never jumps backwards."""
        return time.perf_counter()

    def flush_input(self):
        """Throw away keys pressed earlier, so one early ENTER cannot count in a later round."""
        try:
            if os.name == 'nt':
                import msvcrt
                while msvcrt.kbhit():
                    msvcrt.getwch()
            else:
                import termios
                termios.tcflush(sys.stdin, termios.TCIFLUSH)
        except Exception:           # not a real terminal (a pipe, a script): nothing to throw away
            pass

    def ink(self, word, colour_word):
        """The word printed in the ink of colour_word. Plain text when output is not a terminal."""
        if not sys.stdout.isatty():
            return word
        return f'\033[{COLOURS[colour_word]}m{word}\033[0m'


def half_up(number):
    """2.5 -> 3 (Python's round() would give 2)."""
    return int(number + 0.5)


class BrainTest:
    """What every test has in common."""
    key = ''                        # the test name used in norms.txt
    title = ''                      # "reaction time"
    short = ''                      # the name in tables: "reaction"
    unit = ''                       # shown after a number: "ms"
    unit_one = ''                   # the same unit for exactly 1 ("digit")
    decimals = 0                    # at least this many decimals when showing a normal average
    result_decimals = 0             # the same for a patient's result
    higher_is_better = False        # False: a bigger number is WORSE (slower)
    instructions = ''

    def __init__(self, io=None):
        self.io = io or ConsoleIO()

    def run(self):
        """Play the test and return its one number."""
        raise NotImplementedError


class ReactionTest(BrainTest):
    key = 'reaction'
    title = 'reaction time'
    short = 'reaction'
    unit = unit_one = 'ms'
    instructions = f'Press ENTER as soon as you see *   ({REACTION_ROUNDS} rounds)'

    def run(self):
        io = self.io
        io.say(self.instructions)
        times = []
        while len(times) < REACTION_ROUNDS:
            io.flush_input()
            io.say('Wait...')
            io.wait(io.rng.uniform(WAIT_MIN, WAIT_MAX))
            io.say('*')
            started = io.now()                     # the clock starts the moment the * is printed
            io.ask()
            ms = half_up((io.now() - started) * 1000)
            if ms < TOO_SOON_MS:                   # ENTER was already waiting: repeat this round
                io.say('Too soon!')
                continue
            io.say(f'{ms} ms')
            times.append(ms)
        average = half_up(sum(times) / len(times))
        io.say(f'Average: {average} ms')
        return average


class MemoryTest(BrainTest):
    key = 'memory'
    title = 'memory span'
    short = 'memory'
    unit, unit_one = 'digits', 'digit'
    decimals = 1                    # averages are shown as 6.0, not 6
    higher_is_better = True
    instructions = 'Remember the digits. They disappear after a moment.'

    def new_row(self, length):
        """Random digits, never the same digit twice in a row."""
        digits = [self.io.rng.choice('0123456789')]
        while len(digits) < length:
            digits.append(self.io.rng.choice([d for d in '0123456789' if d != digits[-1]]))
        return ''.join(digits)

    def run(self):
        io = self.io
        io.say(self.instructions)
        longest = 0
        length = MEMORY_START
        while length <= MEMORY_MAX:
            row = self.new_row(length)
            shown = '   ' + ' '.join(row)
            io.say(shown, end='')
            io.wait(SECONDS_PER_DIGIT * length)
            io.say('\r' + ' ' * len(shown) + '\r', end='')    # wipe the line: the row cannot be read any more
            typed = ''.join(io.ask('Type the digits: ').split())     # spaces do not matter
            if typed != row:
                break                                         # the first mistake ends the test
            longest = length
            length += 1
        io.say(f'Longest row repeated: {longest} digits')
        return longest


class ColourWordsTest(BrainTest):
    key = 'colorword'
    title = 'colour words'
    short = 'colour words'
    unit = unit_one = 's'
    decimals = 1                    # seconds are shown with one decimal: 18.0
    result_decimals = 1             # a result is the total seconds, with one decimal: 22.0
    instructions = ('Type the first letter of the COLOUR of each word, not the word: '
                    + ', '.join(ANSWER_KEYS) + '.')

    def make_rounds(self):
        """[(word, ink colour)] for every round. At least COLOUR_MIN_DIFFERENT have an ink
        that differs from the word; which rounds, and how many more, is random."""
        rng = self.io.rng
        words = list(COLOURS)
        different = rng.randint(COLOUR_MIN_DIFFERENT, COLOUR_ROUNDS)
        flags = [True] * different + [False] * (COLOUR_ROUNDS - different)
        rng.shuffle(flags)
        rounds = []
        for is_different in flags:
            word = rng.choice(words)
            ink = rng.choice([w for w in words if w != word]) if is_different else word
            rounds.append((word, ink))
        return rounds

    def run(self):
        io = self.io
        io.say(self.instructions)
        seconds = 0.0
        wrong = 0
        for word, ink in self.make_rounds():
            io.say(io.ink(word, ink))
            started = io.now()
            while True:
                answer = io.ask('> ').strip().lower()
                if answer in ANSWER_KEYS:              # any other key: ask again, it does not count
                    break
            seconds += io.now() - started              # asking again keeps the clock running
            if ANSWER_KEYS[answer] != ink:
                wrong += 1
        total = round(seconds + WRONG_PENALTY * wrong, 1)
        if wrong == 0:
            io.say(f'Time: {seconds:.1f} s, no wrong answers = {total:.1f} s')
        else:
            plural = 'answer' if wrong == 1 else 'answers'
            io.say(f'Time: {seconds:.1f} s, {wrong} wrong {plural} (+{WRONG_PENALTY * wrong} s) = {total:.1f} s')
        return total


ALL_TESTS = (ReactionTest, MemoryTest, ColourWordsTest)         # the order the clinic runs them in
