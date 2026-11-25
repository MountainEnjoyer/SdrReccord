#!/bin/bash

source .venv/bin/activate
python record.py
python decode.py
mpv fm_101.1MHz.wav
