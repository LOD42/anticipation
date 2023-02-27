from collections import defaultdict

from anticipation.config import *
from anticipation.vocab import *


def print_tokens(tokens):
    print('---------------------')
    for j, (tm, dur, note) in enumerate(zip(tokens[0::3],tokens[1::3],tokens[2::3])):
        if note == SEPARATOR:
            assert tm == SEPARATOR and dur == SEPARATOR
            print(j, 'SEPARATOR')
            continue

        if note == REST:
            assert tm < LABEL_OFFSET
            assert dur == DUR_OFFSET+0
            print(j, tm, 'REST')
            continue

        if note < LABEL_OFFSET:
            tm = tm - TIME_OFFSET
            dur = dur - DUR_OFFSET
            note = note - NOTE_OFFSET
            instr = note//2**7
            pitch = note - (2**7)*instr
            print(j, tm, dur, instr, pitch)
        else:
            tm = tm - ATIME_OFFSET
            dur = dur - ADUR_OFFSET
            note = note - ANOTE_OFFSET
            instr = note//2**7
            pitch = note - (2**7)*instr
            print(j, tm, dur, instr, pitch, '(A)')


def clip(tokens, start, end, clip_duration=True):
    new_tokens = []
    for (time, dur, note) in zip(tokens[0::3],tokens[1::3],tokens[2::3]):
        if note < LABEL_OFFSET:
            this_time = (time - TIME_OFFSET)/float(TIME_RESOLUTION)
            this_dur = (dur - DUR_OFFSET)/float(TIME_RESOLUTION)
        else:
            this_time = (time - ATIME_OFFSET)/float(TIME_RESOLUTION)
            this_dur = (dur - ADUR_OFFSET)/float(TIME_RESOLUTION)

        if this_time < start or end < this_time:
            continue

        # truncate extended notes
        if clip_duration and end < this_time + this_dur:
            dur -= int(TIME_RESOLUTION*(this_time + this_dur - end))

        new_tokens.extend([time, dur, note])

    return new_tokens


def mask(tokens, start, end):
    new_tokens = []
    for (time, dur, note) in zip(tokens[0::3],tokens[1::3],tokens[2::3]):
        if note < LABEL_OFFSET:
            this_time = (time - TIME_OFFSET)/float(TIME_RESOLUTION)
        else:
            this_time = (time - ATIME_OFFSET)/float(TIME_RESOLUTION)

        if start < this_time < end:
            continue

        new_tokens.extend([time, dur, note])

    return new_tokens


# FIXME
def resequence(tokens):
    new_tokens = []
    anticipated = []
    for (time, dur, note) in zip(tokens[0::3],tokens[1::3],tokens[2::3]):
        if note < BASE_OFFSET:
            # anticipated token
            anticipated.extend([time, dur, note])
        else:
            while anticipated and anticipated[0] - TIME_OFFSET < time - BASE_OFFSET - TIME_OFFSET:
                atime, adur, anote = anticipated[0:3]
                new_tokens.extend([BASE_OFFSET+atime, BASE_OFFSET+adur, BASE_OFFSET+anote])
                anticipated = anticipated[3:]

            new_tokens.extend([time, dur, note])

    while anticipated and anticipated[0] - TIME_OFFSET < time:
        atime, adur, anote = anticipated[0:3]
        new_tokens.extend([BASE_OFFSET+atime, BASE_OFFSET+adur, BASE_OFFSET+anote])
        anticipated = anticipated[3:]

    return new_tokens


def pad(tokens, end_time, density=TIME_RESOLUTION):
    new_tokens = []
    end_time = TIME_OFFSET+end_time
    previous_time = TIME_OFFSET+0
    for (time, dur, note) in zip(tokens[0::3],tokens[1::3],tokens[2::3]):
        # must pad before separation, anticipation
        assert note < LABEL_OFFSET

        # insert pad tokens to ensure the desired density
        while time > previous_time + density:
            new_tokens.extend([previous_time+density, DUR_OFFSET+0, REST])
            previous_time += density

        new_tokens.extend([time, dur, note])
        previous_time = time

    while end_time > previous_time + density:
        new_tokens.extend([previous_time+density, DUR_OFFSET+0, REST])
        previous_time += density

    return new_tokens


def unpad(tokens):
    new_tokens = []
    for (time, dur, note) in zip(tokens[0::3],tokens[1::3],tokens[2::3]):
        if note == REST: continue

        new_tokens.extend([time, dur, note])

    return new_tokens


def anticipate(events, labels, delta=DELTA*TIME_RESOLUTION):
    """
    Interleave a sequence of events with anticipated labels.

    Inputs:
      events : a sequence of events
      labels : a sequence of time-localized labels
      delta  : the anticipation interval
    
    Returns:
      tokens : interleaved events and anticipated labels
      labels : unconsumed labels (label time > max_time(events) + delta)
    """

    if len(labels) == 0:
        return events, labels

    tokens = []
    event_time = 0
    label_time = labels[0] - ATIME_OFFSET
    for time, dur, note in zip(events[0::3],events[1::3],events[2::3]):
        while event_time >= label_time - delta:
            tokens.extend(labels[0:3])
            labels = labels[3:] # consume this label
            label_time = labels[0] - ATIME_OFFSET if len(labels) > 0 else float('inf')

        assert note < LABEL_OFFSET
        event_time = time - TIME_OFFSET
        tokens.extend([time, dur, note])

    return tokens, labels


def sparsity(tokens):
    max_dt = 0
    previous_time = TIME_OFFSET+0
    for (time, dur, note) in zip(tokens[0::3],tokens[1::3],tokens[2::3]):
        if note == SEPARATOR: continue
        assert note < LABEL_OFFSET # don't operate on interleaved sequences

        max_dt = max(max_dt, time - previous_time)
        previous_time = time

    return max_dt


def min_time(tokens, seconds=True, instr=None):
    mt = None
    for time, dur, note in zip(tokens[0::3],tokens[1::3],tokens[2::3]):
        # stop calculating at sequence separator
        if note == SEPARATOR: break

        if note < LABEL_OFFSET:
            time -= TIME_OFFSET
            note -= NOTE_OFFSET
        else:
            time -= ATIME_OFFSET
            note -= ANOTE_OFFSET

        # min time of a particular instrument
        if instr is not None and instr != note//2**7:
            continue

        mt = time if mt is None else min(mt, time)

    if mt is None: mt = 0
    return mt/float(TIME_RESOLUTION) if seconds else mt


def max_time(tokens, seconds=True, instr=None):
    mt = 0
    for time, dur, note in zip(tokens[0::3],tokens[1::3],tokens[2::3]):
        # stop calculating at sequence separator
        if note == SEPARATOR: break

        if note < LABEL_OFFSET:
            time -= TIME_OFFSET
            note -= NOTE_OFFSET
        else:
            time -= ATIME_OFFSET
            note -= ANOTE_OFFSET

        # max time of a particular instrument
        if instr is not None and instr != note//2**7:
            continue

        mt = max(mt, time)

    return mt/float(TIME_RESOLUTION) if seconds else mt


def get_instruments(tokens):
    instruments = defaultdict(int)
    for time, dur, note in zip(tokens[0::3],tokens[1::3],tokens[2::3]):
        if note >= CONTROL_OFFSET: continue

        if note < LABEL_OFFSET:
            note -= NOTE_OFFSET
        else:
            note -= ANOTE_OFFSET

        instr = note//2**7
        instruments[instr] += 1

    return instruments


def translate(tokens, dt, seconds=False):
    if seconds:
        dt = int(TIME_RESOLUTION*dt)

    new_tokens = []
    for (time, dur, note) in zip(tokens[0::3],tokens[1::3],tokens[2::3]):
        # stop translating after EOT
        if note == SEPARATOR:
            new_tokens.extend([time, dur, note])
            dt = 0
            continue

        if note < LABEL_OFFSET:
            this_time = time - TIME_OFFSET
        else:
            this_time = time - ATIME_OFFSET

        assert 0 <= this_time + dt
        if not this_time + dt < MAX_TIME:
            raise OverflowError

        new_tokens.extend([time+dt, dur, note])

    return new_tokens
