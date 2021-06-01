#!/bin/bash

set -euo pipefail
IFS=$'\n\t'

# This uses MD5 encryption (-m) instead of bcrypt (-B) to reduce the CPU load
# during logs ingestion. The production passwords are secure enough not to be
# brute-forceable through HTTP requests even with the fast MD5 algorithm.
#
# An attacker gaining access to the container and brute-forcing the hashes is
# outside our treat model, as the plaintext passwords are be available in the
# environment variables anyway.
htpasswd -cbm /etc/nginx/creds-drain drain "${PASSWORD_DRAIN}"
htpasswd -cbm /etc/nginx/creds-metrics metrics "${PASSWORD_METRICS}"

exec supervisord -c /etc/supervisor/supervisord.conf
