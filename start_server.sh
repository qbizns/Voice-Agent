#!/bin/bash
cd /Users/Galal/vodo/Agent
source venv/bin/activate
export STT_ENGINE=whisper
export WHISPER_MODEL=base
export WHISPER_LANGUAGE=ar
python main.py
