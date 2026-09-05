# its a shell script, i made this to run cmds like iptables cmd (cmd used to control network traffic)
# this runs outside of this python code, and in simpler terms
# agent runs in execution of python and shell script runns before.....
# so agent can't touch this shell as its acts like isp.....

set -e

PROXY_HOST = "${PROXY_HOST:-mitm-proxy}"
PROXY_PORT = "${PROXY_PORT:-8080}"

# Starting Proxy before locking down dns
# also firewall rule to a concrete address instead of leaving a hostname-based

PROXY_IP = $(getent hosts "$PROXY_HOST" | awk '{ print $1 }' | head -n1)
if [ -z "$PROXY_IP" ]; then
    echo "[entrypoint] could not resolve PROXY_HOST=$PROXY_HOST — refusing to start" >&2
    exit 1
fi

# lockdown---

iptablles -F OUTPUT
iptables -P OUTPUT DROP

# this cmd allows for local / loopback trafic
iptables -A OUTPUT -o lo -j ACCEPT

# this cmd allows to connection that continer already staretd
iptables -A OUTPUT -m state --state ESTABLISHED, RELATED -j ACCEPT

# this cmd Allows DNS request to DOcker's Internal Dns Server (the isp we setup in previous code )
iptables -A OUTPUT -p udp -d 127.0.0.11 --dport 53 -j ACCEPT
iptables -A OUTPUT -p tcp -d 127.0.0.11 --dport 53 -j ACCEPT

# this cmd allows the app to connect only to proxy
iptables -A OUTPUT -p tcp -d "$PROXY_IP" --dport "$PROXY_PORT" -j ACCEPT

# This cmd shows network access is allowed or not
e ho "Network locked: only proxy + Docker DNS + local traffic is allowed"

# This Cmd runn the application as the non-root user "appuser" (interesting....)
exec su -s /bin/sh appuser -c \
    "cd/app && exec unicorn server:app --host 0.0.0.0 --port 9000"
 