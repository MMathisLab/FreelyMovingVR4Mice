#!/bin/bash

if [ -z "$1" ]; then
  echo "Usage: $0 folder_name"
  exit 1
fi

# Assign the folder name to a variable
FOLDER="$1"

for FILE in "$FOLDER"/*; do
  BASENAME=$(basename "$FILE")

  IMAGINGSOURCE="Imagingsource"
  MOUSEID="${BASENAME:7:4}"
  RAWDATE="${BASENAME:0:6}"
  YEAR="${RAWDATE:0:2}"
  MONTH="${RAWDATE:2:2}"
  DAY="${RAWDATE:4:2}"
  DATE="20$YEAR-$MONTH-$DAY"
  ATTEMPT=1 #"${BASENAME:12:2}"

  if [[ "$BASENAME" == *"_DLC.hdf5" ]]; then
    NEWNAME="${IMAGINGSOURCE}_${MOUSEID}_${DATE}_${ATTEMPT}_DLC.hdf5"
  elif [[ "$BASENAME" == *"_TS.npy" ]]; then
    NEWNAME="${IMAGINGSOURCE}_${MOUSEID}_${DATE}_${ATTEMPT}_TS.npy"
  elif [[ "$BASENAME" == *"_PROC" ]]; then
    NEWNAME="${IMAGINGSOURCE}_${MOUSEID}_${DATE}_${ATTEMPT}_PROC"
  elif [[ "$BASENAME" == *"_behavior.pickle" ]]; then
    NEWNAME="${MOUSEID}_${DATE}_${ATTEMPT}.pickle"
  else
    echo "Skipping unknown file type: $FILE"
    continue
  fi

  mv "$FILE" "$FOLDER/$NEWNAME"
  echo "Renamed $FILE to $NEWNAME"
done
