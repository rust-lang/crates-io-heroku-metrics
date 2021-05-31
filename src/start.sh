#!/bin/bash

set -euo pipefail
IFS=$'\n\t'

htpasswd -cbB /etc/nginx/creds-drain drain "${PASSWORD_DRAIN}"
htpasswd -cbB /etc/nginx/creds-metrics metrics "${PASSWORD_METRICS}"

exec supervisord -c /etc/supervisor/supervisord.conf
