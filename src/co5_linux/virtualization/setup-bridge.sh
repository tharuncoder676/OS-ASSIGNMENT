#!/usr/bin/env bash
#
# setup-bridge.sh - create the CloudMatrix guest bridge with iproute2
#
# The netplan file is the persistent definition; this script is the imperative
# equivalent, useful for a live host and for demonstrating exactly what netplan
# generates underneath.
#
set -euo pipefail

BRIDGE="br0"
UPLINK="eno1"
HOST_IP="10.20.30.5/24"
GATEWAY="10.20.30.1"

[[ ${EUID} -eq 0 ]] || { echo "must run as root" >&2; exit 1; }

# 1. Create the bridge if it does not exist
if ! ip link show "${BRIDGE}" &>/dev/null; then
    ip link add name "${BRIDGE}" type bridge
    echo "created bridge ${BRIDGE}"
fi

# 2. Spanning tree on: a host with many guest taps can genuinely form a loop
ip link set "${BRIDGE}" type bridge stp_state 1
ip link set "${BRIDGE}" type bridge forward_delay 400

# 3. Move the uplink onto the bridge and strip its address
ip addr flush dev "${UPLINK}"
ip link set "${UPLINK}" master "${BRIDGE}"
ip link set "${UPLINK}" up

# 4. The host address lives on the bridge, not the NIC
ip addr replace "${HOST_IP}" dev "${BRIDGE}"
ip link set "${BRIDGE}" up
ip route replace default via "${GATEWAY}" dev "${BRIDGE}"

# 5. Do not filter bridged traffic through iptables: it costs CPU on every
#    guest-to-guest frame and breaks L2 semantics tenants expect.
sysctl -qw net.bridge.bridge-nf-call-iptables=0
sysctl -qw net.bridge.bridge-nf-call-ip6tables=0

# 6. Forwarding on, reverse-path filtering strict (anti-spoofing between guests)
sysctl -qw net.ipv4.ip_forward=1
sysctl -qw net.ipv4.conf.all.rp_filter=1

echo
echo "--- bridge state ---"
ip -brief link show type bridge
ip -brief addr show "${BRIDGE}"
bridge link show
echo
echo "--- attached guest taps ---"
bridge link show | grep -E "vif|tap" || echo "  (no guests running)"
