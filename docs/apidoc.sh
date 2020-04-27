#!/usr/bin/env bash

ARGS='--tocfile api -e -M -a -f'
OUTPUT='.'
INPUT='../qmm'
EXCLUDE='../qmm/ui_* ../qmm/*_rc.py'

SPHINX_APIDOC_OPTIONS=members,show-inheritance sphinx-apidoc $ARGS -o $OUTPUT $INPUT $EXCLUDE
