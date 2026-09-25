#!/usr/bin/env bash
# Clear all leaderboard entries while preserving the current storage schema.
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
LEADERBOARD_PATH="${ROOT_DIR}/leaderboard.json"
TEMP_PATH=""

cleanup() {
    if [[ -n "${TEMP_PATH}" && -e "${TEMP_PATH}" ]]; then
        rm -f -- "${TEMP_PATH}"
    fi
}
trap cleanup EXIT

# Write beside the destination so the final rename is atomic on the same
# filesystem. This prevents the game from observing a partially written JSON
# document if the machine loses power during the reset.
TEMP_PATH="$(mktemp "${ROOT_DIR}/.leaderboard.json.reset.XXXXXX")"
printf '%s\n' '{' '    "schema_version": 2,' '    "records": {}' '}' > "${TEMP_PATH}"

# Keep the existing file mode when resetting an established deployment.
if [[ -e "${LEADERBOARD_PATH}" ]]; then
    chmod --reference="${LEADERBOARD_PATH}" "${TEMP_PATH}"
fi

mv -f -- "${TEMP_PATH}" "${LEADERBOARD_PATH}"
TEMP_PATH=""

echo "Ranking entries cleared: ${LEADERBOARD_PATH}"
echo "Player name suggestions were not changed."
