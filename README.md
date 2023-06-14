# Anticipatory Music Transformer

Implementation of the methods described in [Anticipatory Music Transformer](https://johnthickstun.com/assets/pdf/anticipatory-music-transformer.pdf).

by [__John Thickstun__](https://johnthickstun.com/), [__David Hall__](http://dlwh.org/), [__Chris Donahue__](https://chrisdonahue.com/), and [__Percy Liang__](https://cs.stanford.edu/~pliang/).

-------------------------------------------------------------------------------------

This repository provides the code for creating anticipatory training datasets, and for sampling from models trained with anticipation. It does _not_ contain code for training these models: you may use the preprocessed datasets constructed here as input to your favorite codebase for training autoregressive transformer models. We used the [Levanter](https://github.com/stanford-crfm/levanter) to train models, and include instructions [here](train) for training an Anticipatory Music Transformer with Levanter. For additional detail about this work, see the corresponding [paper](https://johnthickstun.com/assets/pdf/anticipatory-music-transformer.pdf).

Pretrained models are hosted by the Center for Research on Foundation Models (CRFM) on the [HuggingFace Hub](https://huggingface.co/stanford-crfm). 

This project is licensed under the terms of the Apache License, Version 2.0.

Begin by installing the anticipation package (from the root anticipation package directory).

```
pip install .
```

## Software Dependencies

Run the following command to install dependencies.

```
pip install -r requirements.txt
```

## Generating Music with an Anticipatory Music Transformer

See the [Colab](https://colab.research.google.com/drive/1HCQDtGFwROpHRqcmZbV0byqbxDb74YGu?usp=sharing) notebook for an interactive demonstration of music generation using the Anticipatory Music Transformer.

You can load a pretrained model using the HuggingFace Transformers package, e.g.:

```
from transformers import AutoModelForCausalLM

model = AutoModelForCausalLM.from_pretrained('stanford-crfm/music-medium-800k').cuda()
```

You can sample from this model using the custom `generate` function implementated by the anticipation package. You can convert generated event tokens to midi using the `events_to_midi` function:

```
from anticipation.sample import generate
from anticipation.convert import events_to_midi

length = 10 # time in seconds
events = generate(model, start_time=0, end_time=length, top_p=.98)
mid = events_to_midi(events)
mid.save('generated.mid')
```

You can load your own MIDI and tokenize it using the `midi_to_events` function.

```
from anticipation.convert import midi_to_events

events = midi_to_events('anticipation/examples/strawberry.mid')
```

To isolate a segment of a longer stream of events, use the `ops` library to clip the stream and translate the clipped segment to time zero. To isolate a melodic line, use `extract_instruments`:

```
from anticipation import ops
from anticipation.tokenize import extract_instruments

events = ops.clip(events, 41, 41+20)
events = ops.translate(events, -ops.min_time(events, seconds=False))

events, melody = extract_instruments(segment, [53])
```

To generate an accompaniment to an isolated melody, call the `generate` function using the melody as control inputs. Recombine the generated accompaniment with the melody controls using `ops.combine`:

```
history = ops.clip(events, 0, 5, clip_duration=False)
accompaniment = generate(model, 5, 20, inputs=history, controls=melody, top_p=.98)
completed_events = ops.combine(accompaniment, melody)
mid = events_to_midi(completed_events)
mid.save('generated.mid')
```

See the [Colab](https://colab.research.google.com/drive/1HCQDtGFwROpHRqcmZbV0byqbxDb74YGu?usp=sharing) notebook for additional examples of infilling control using the Anticipatory Music Transformer.

## Training an Anticipatory Music Transformer

See the [train](train) directory for instructions on preprocessing the Lakh MIDI dataset and using [Levanter](https://github.com/stanford-crfm/levanter) to train an Anticipatory Music Transformer.

## Reproducing the Human Evaluation Procedure

See the [humaneval](humaneval) directory for instructions on reproducing data used for human evaluations.

-------------------------------------------------------------------------------------

To reference this work, please cite

```bib
@article{thickstun2023anticipatory,
  title={Anticipatory Music Transformer},
  author={Thickstun, John and Hall, David and Donahue, Chris and Liang, Percy},
  journal={},
  year={2023}
}
```
