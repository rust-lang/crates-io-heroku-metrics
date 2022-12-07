#!/usr/bin/env python3

# This script sends the output of `heroku logs --tail --app crates-io` to
# vector.dev, taking care of properly formatting it the way Heroku Logplex
# would send it.
#
# To run it off live data, run:
#
#    heroku logs --tail --app crates-io | ./simulate-heroku.py DRAIN_URL
#
# To capture a sample of logs and then replay it later run:
#
#    heroku logs --tail --app crates-io > cached-logs
#    cat cached-logs | ./simulate-heroku.py DRAIN_URL
#
# Take care of replacing the DRAIN_URL with the URL of your drain. For local
# execution using the instructions in the README, the DRAIN_URL will be:
#
#    http://drain:${DRAIN_PASSWORD}@localhost/drain?app_name=crates-io
#

import re
import requests
import sys
import uuid

# Regex matching the output of `heroku logs --tail --app crates-io`.
HEROKU_CLI_RE = re.compile(
    r"^(?P<time>[^ ]+) (?P<app>[^\[]+)\[(?P<proc>[^\]]+)\]: (?P<message>.*)$"
)

# Randomly generated but hardcoded drain token for this script.
DRAIN_TOKEN = "d.25c16be4-2836-4b8f-8b24-4d62def8116c"

# Limit how much data we send to nginx at a time.
MAX_REQUEST_SIZE = 512 * 1024  # 512 Kb


def messages_from_stdin():
    """Parse the messages from stdin and format them correctly"""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        matches = HEROKU_CLI_RE.search(line)
        if matches is None:
            print(f"warn: skipping invalid line: {line}", file=sys.stderr)
            continue

        # https://stackoverflow.com/a/25247628
        message = f"<14>1 {matches['time']} host {matches['app']} {matches['proc']} - {matches['message']}"
        yield str(len(message)) + " " + message


def send_messages(drain, messages):
    resp = requests.post(
        drain,
        headers={
            "Logplex-Msg-Count": str(len(messages)),
            "Logplex-Frame-Id": str(uuid.uuid4()),
            "Logplex-Drain-Token": DRAIN_TOKEN,
            "User-Agent": "debug script",
            "Content-Type": "application/logplex-1",
        },
        data="\n".join(messages),
    )
    resp.raise_for_status()


def send_all_messages(drain):
    batch = []
    for message in messages_from_stdin():
        batch.append(message)
        if sum(len(m) for m in batch) > MAX_REQUEST_SIZE:
            send_messages(drain, batch)
            batch.clear()
    # Also send remaining messages
    if batch:
        send_messages(drain, batch)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <drain-url>", file=sys.stderr)
        exit(1)

    send_all_messages(sys.argv[1])
