from tqdm import tqdm

import numpy as np

from anticipation import ops
from anticipation.config import *
from anticipation.vocab import *
from anticipation.convert import compound_to_events


def extract_spans(all_events, rate):
    events = []
    labels = []
    span = True
    next_span = end_span = TIME_OFFSET+0
    for time, dur, note in zip(all_events[0::3],all_events[1::3],all_events[2::3]):
        assert(note not in [SEPARATOR, REST]) # shouldn't be in the sequence yet

        # end of an anticipated span; decide when to do it again (next_span)
        if span and time >= end_span:
            span = False
            next_span = time+int(TIME_RESOLUTION*np.random.exponential(1./rate))

        # anticipate a 3-second span
        if (not span) and time >= next_span:
            span = True
            end_span = time + DELTA*TIME_RESOLUTION

        if span:
            # mark this event as a label
            labels.extend([LABEL_OFFSET+time, LABEL_OFFSET+dur, LABEL_OFFSET+note])
        else:
            events.extend([time, dur, note])

    return events, labels


ANTICIPATION_RATES = 10
def extract_random(all_events, rate):
    events = []
    labels = []
    for time, dur, note in zip(all_events[0::3],all_events[1::3],all_events[2::3]):
        assert(note not in [SEPARATOR, REST]) # shouldn't be in the sequence yet

        if np.random.random() < rate/float(ANTICIPATION_RATES):
            # mark this event as a label
            labels.extend([LABEL_OFFSET+time, LABEL_OFFSET+dur, LABEL_OFFSET+note])
        else:
            events.extend([time, dur, note])

    return events, labels


def extract_instruments(all_events, instruments):
    events = []
    labels = []
    for time, dur, note in zip(all_events[0::3],all_events[1::3],all_events[2::3]):
        assert(note not in [SEPARATOR, REST]) # shouldn't be in the sequence yet
        instr = (note-NOTE_OFFSET)//2**7

        if instr in instruments:
            # mark this event as a label
            labels.extend([LABEL_OFFSET+time, LABEL_OFFSET+dur, LABEL_OFFSET+note])
        else:
            events.extend([time, dur, note])

    return events, labels


def tokenize(datafiles, output, augment_factor, idx=0, debug=False):
    tokens = []
    seqcount = discarded = rest_count = 0
    np.random.seed(0)

    with open(output, 'w') as outfile:
        concatenated_tokens = []
        for j, filename in tqdm(list(enumerate(datafiles)), desc=f'#{idx}', position=idx+1):
            #if j == 10: break

            try:
                with open(filename, 'r') as f:
                    compound_tokens = [int(token) for token in f.read().split()]

            except FileNotFoundError:
                continue

            if len(compound_tokens) < 5*MIN_TRACK_EVENTS:
                continue

            if min(int(tok) for tok in compound_tokens[0::5]) < 0:
                if debug:
                    print(f'ERROR: corrupted document {filename} (skipping)')

                continue

            try:
                all_events = compound_to_events(compound_tokens)
            except ValueError:
                if debug:
                    print(f'ERROR: corrupted document {filename} (skipping)')

                continue

            # max time before extracting labels
            end_time = ops.max_time(all_events, seconds=False)

            # get the list of instrument
            instruments = list(ops.get_instruments(all_events).keys())

            # different random augmentations
            for k in range(augment_factor):
                if k % 10 == 0:
                    # no augmentation
                    events = all_events.copy()
                    labels = []
                elif k % 10 == 1:
                    # span augmentation
                    lmbda = .05
                    events, labels = extract_spans(all_events, lmbda)
                elif k % 10 < 6:
                    # random augmentation
                    r = np.random.randint(1,ANTICIPATION_RATES)
                    events, labels = extract_random(all_events, r)
                else:
                    if len(instruments) > 1:
                        # instrument augmentation: at least one, but not all instruments
                        j = 1+np.random.randint(len(instruments)-1)
                        subset = np.random.choice(instruments, j, replace=False)
                        events, labels = extract_instruments(all_events, subset)
                    else:
                        # no augmentation
                        events = all_events.copy()
                        labels = []

                if len(concatenated_tokens) == 0:
                    z = ANTICIPATE if k % 10 != 0 else AUTOREGRESS

                events = ops.pad(events, end_time)
                rest_count += sum(1 if tok == REST else 0 for tok in events[2::3])
                tokens, labels = ops.anticipate(events, labels)
                assert len(labels) == 0 # should have consumed all labels (because of padding)
                tokens[0:0] = [SEPARATOR, SEPARATOR, SEPARATOR]
                concatenated_tokens.extend(tokens)

                # write out full sequences to file
                while len(concatenated_tokens) >= 1023:
                    seq = concatenated_tokens[0:1023]
                    concatenated_tokens = concatenated_tokens[1023:]

                    try:
                        # relativize time to the sequence
                        seq = ops.translate(
                                seq, -ops.min_time(seq, seconds=False), seconds=False)

                        # should have relativized to zero
                        assert ops.min_time(seq, seconds=False) == 0 
                    except OverflowError:
                        # relativized time exceeds MAX_TIME
                        discarded += 1
                        continue

                    # if seq contains SEPARATOR, these labels describe the first sequence
                    seq.insert(0, z)

                    outfile.write(' '.join([str(tok) for tok in seq]) + '\n')
                    seqcount += 1

                    # grab the current augmentation labels if we didn't already
                    z = ANTICIPATE if k % 10 != 0 else AUTOREGRESS

    if debug:
        fmt = 'Processed {} sequences (discarded {}, inserted {} rest tokens)'
        print(fmt.format(seqcount, discarded, rest_count))