#!/usr/bin/env bash

ARGS='--tocfile api -e -M -a -f'
OUTPUT='.'
INPUT='../qmm'
EXCLUDE='../qmm/ui_* ../qmm/*_rc.py'

EXT_PATH="./_ext/"

rm qmm.* api.rst ${EXT_PATH}ui_*.py

SPHINX_APIDOC_OPTIONS=members,show-inheritance sphinx-apidoc $ARGS -o $OUTPUT $INPUT $EXCLUDE

TEMPLATE="class Ui_@CLASSNAME@:
    def setupUi(self):
        pass"

for f in ../resources/*.ui
do
  FILENAME=$(echo "$f" | sed -r 's/.*ui_([^.]+)\.ui/ui_\1.py/')
  CLASSNAME=$(awk '/class>/{ a=gensub(/<\/?class>/, "", "g", $1); print a }' "$f")
  #CLASSNAME=$(echo "$f" | sed -r 's/.*ui_([^.]+)\.ui/\1/')
  echo "${TEMPLATE/@CLASSNAME@/${CLASSNAME^}}" > "${EXT_PATH}$FILENAME"
done
