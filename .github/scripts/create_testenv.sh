#!/bin/bash
set -euxo pipefail

print_help() {
  echo "Usage: create_testenv.sh -q=qmm -l=lilith -r=repo"
}

if [ $# = 0 ]; then
  print_help
  exit 1
fi

while getopts 'q:l:r:' opt; do
  case "$opt" in
    q) QMMPATH="$OPTARG" ;;
    l) LILITHPATH="$OPTARG" ;;
    r) REPOPATH="$OPTARG" ;;
    :) print_help ;;
    ?) echo "unknown option '$opt'" ;;
  esac
done

shift $((OPTIND - 1))

CONFIG_HOME="${HOME}/.config/qmm/"
mkdir -p "${CONFIG_HOME}"
cat <<EOF >"${CONFIG_HOME}/test.json"
{
    "local_repository": "${REPOPATH}",
    "game_folder": "${LILITHPATH}",
    "language": "en_US",
    "ck_descriptive_text": false
}
EOF
