#!/usr/bin/env bash
#
# cm-healthcheck.sh - CloudMatrix service and resource validation
#
# Collects the evidence that the report's "Results and Validation" section
# relies on: DNS forward and reverse resolution, DHCP lease state, hypervisor
# domain status, memory pressure, and block-device queue behaviour.
#
# Usage:  cm-healthcheck.sh [--json]
#
# Exit code is the number of failed checks, so it can drive a systemd
# OnFailure= unit or a monitoring probe directly.
#

set -uo pipefail

readonly NS1="10.20.30.10"
readonly DOMAIN="cloudmatrix.local"
FAILURES=0

pass() { printf "  [ OK ]  %s\n" "${1}"; }
fail() { printf "  [FAIL]  %s\n" "${1}"; FAILURES=$((FAILURES + 1)); }
head2() { printf "\n== %s ==\n" "${1}"; }

head2 "DNS forward resolution (BIND9 authoritative zone)"
for host in ns1 ns2 vm-web-01 vm-db-02 vm-win11-07 www; do
    if answer=$(dig +short "@${NS1}" "${host}.${DOMAIN}" A 2>/dev/null) \
       && [[ -n "${answer}" ]]; then
        pass "${host}.${DOMAIN} -> ${answer//$'\n'/ }"
    else
        fail "${host}.${DOMAIN} did not resolve"
    fi
done

head2 "DNS reverse resolution (in-addr.arpa PTR records)"
for ip in 10.20.30.10 10.20.30.101 10.20.30.102 10.20.30.107; do
    if answer=$(dig +short "@${NS1}" -x "${ip}" 2>/dev/null) \
       && [[ -n "${answer}" ]]; then
        pass "${ip} -> ${answer}"
    else
        fail "${ip} has no PTR record"
    fi
done

head2 "DNS query latency (Section D target: sub-10 ms)"
for i in 1 2 3; do
    ms=$(dig "@${NS1}" "www.${DOMAIN}" \
         | awk '/Query time:/ {print $4}')
    if [[ -n "${ms}" ]] && (( ms < 10 )); then
        pass "query ${i}: ${ms} ms"
    else
        fail "query ${i}: ${ms:-no answer} ms exceeds the 10 ms target"
    fi
done

head2 "Zone file syntax"
if named-checkconf /etc/bind/named.conf; then
    pass "named.conf parses clean"
else
    fail "named.conf has syntax errors"
fi
for z in "${DOMAIN}:/etc/bind/zones/db.cloudmatrix.local" \
         "30.20.10.in-addr.arpa:/etc/bind/zones/db.10.20.30"; do
    zone="${z%%:*}"; file="${z##*:}"
    if named-checkzone "${zone}" "${file}" >/dev/null; then
        pass "zone ${zone} is valid"
    else
        fail "zone ${zone} FAILED validation"
    fi
done

head2 "DHCP server"
if dhcpd -t -cf /etc/dhcp/dhcpd.conf >/dev/null 2>&1; then
    pass "dhcpd.conf parses clean"
else
    fail "dhcpd.conf has syntax errors"
fi
if systemctl is-active --quiet isc-dhcp-server; then
    pass "isc-dhcp-server is running"
    leases=$(grep -c "^lease" /var/lib/dhcp/dhcpd.leases 2>/dev/null || echo 0)
    printf "          %s lease record(s) in dhcpd.leases\n" "${leases}"
else
    fail "isc-dhcp-server is not running"
fi

head2 "Hypervisor and guest domains"
if command -v virsh >/dev/null; then
    pass "libvirt present"
    virsh list --all 2>/dev/null | sed "s/^/          /"
    virsh nodeinfo 2>/dev/null | sed "s/^/          /"
else
    fail "virsh not installed"
fi
if command -v xl >/dev/null; then
    pass "Xen toolstack present"
    xl list 2>/dev/null | sed "s/^/          /"
else
    printf "  [ -- ]  Xen toolstack not installed (KVM/libvirt path in use)\n"
fi

head2 "Virtual bridge networking"
if ip link show br0 >/dev/null 2>&1; then
    pass "br0 exists"
    ip -brief addr show br0 | sed "s/^/          /"
    bridge link show 2>/dev/null | sed "s/^/          /"
else
    fail "br0 is missing; guests have no L2 path"
fi

head2 "Memory pressure (CO3 evidence)"
free -h | sed "s/^/          /"
printf "          swap in/out since boot: %s\n" \
    "$(vmstat 1 2 | tail -1 | awk '{print $7 "/" $8}')"
major=$(awk '/pgmajfault/ {print $2}' /proc/vmstat)
printf "          major page faults since boot: %s\n" "${major}"
if [[ -f /sys/kernel/mm/ksm/pages_sharing ]]; then
    printf "          KSM pages shared: %s (saving %s MB)\n" \
        "$(cat /sys/kernel/mm/ksm/pages_sharing)" \
        "$(( $(cat /sys/kernel/mm/ksm/pages_sharing) * 4 / 1024 ))"
fi

head2 "Block layer (CO4 evidence)"
for dev in /sys/block/sd* /sys/block/nvme*; do
    [[ -e "${dev}/queue/scheduler" ]] || continue
    printf "          %-12s scheduler: %s\n" \
        "$(basename "${dev}")" "$(cat "${dev}/queue/scheduler")"
    printf "          %-12s nr_requests: %s  read_ahead_kb: %s\n" "" \
        "$(cat "${dev}/queue/nr_requests")" \
        "$(cat "${dev}/queue/read_ahead_kb")"
done
command -v iostat >/dev/null && iostat -x 1 2 | tail -n +7 | sed "s/^/          /"

printf "\n== SUMMARY ==\n"
if (( FAILURES == 0 )); then
    printf "  All checks passed.\n"
else
    printf "  %d check(s) FAILED.\n" "${FAILURES}"
fi
exit "${FAILURES}"
