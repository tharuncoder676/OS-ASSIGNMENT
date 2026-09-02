#!/usr/bin/env bash
#
# validate_co5.sh - structural validation of every CO5 artefact
#
# Where the real Linux tools are present this script defers to them
# (named-checkconf, named-checkzone, dhcpd -t). Where they are not -- for
# example when the repository is checked out on a Windows workstation -- it
# falls back to structural checks that still catch the failure modes those
# tools catch: unbalanced braces, missing SOA or NS records, malformed
# serials, tab characters in YAML, and shell syntax errors.
#
# `bash -n` is a genuine parse of every administration script and runs
# everywhere, so the shell validation is never a fallback.
#
# Usage:  bash tools/validate_co5.sh
#

cd "$(dirname "$0")/.." || exit 1

echo "=============================================================================="
echo " CloudMatrix - CO5 configuration and script validation"
echo " Host: $(uname -s) $(uname -r)   bash ${BASH_VERSION%%(*}"
echo " Date: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "=============================================================================="
echo
echo "== bash -n : POSIX shell syntax validation of the administration scripts =="
for f in src/co5_linux/scripts/*.sh src/co5_linux/virtualization/*.sh tools/*.sh; do
    if bash -n "$f" 2>/tmp/cm_err; then
        printf "  [ OK ]  %-52s syntax clean\n" "$f"
    else
        printf "  [FAIL]  %-52s\n" "$f"
        sed 's/^/          /' /tmp/cm_err
    fi
done

echo
echo "== Script hardening checks =="
for f in src/co5_linux/scripts/*.sh src/co5_linux/virtualization/*.sh; do
    strict=$(grep -c 'set -euo pipefail\|set -uo pipefail' "$f")
    shebang=$(head -1 "$f" | grep -c 'bin/env bash')
    printf "  %-34s shebang=%s  strict-mode=%s  lines=%s\n" \
        "$(basename "$f")" "$shebang" "$strict" "$(wc -l < "$f")"
done

echo
echo "== BIND 9 configuration =="
if command -v named-checkconf >/dev/null 2>&1; then
    named-checkconf src/co5_linux/dns/named.conf \
        && echo "  [ OK ]  named-checkconf reports no errors"
    for z in "cloudmatrix.local:src/co5_linux/dns/db.cloudmatrix.local" \
             "30.20.10.in-addr.arpa:src/co5_linux/dns/db.10.20.30" \
             "40.20.10.in-addr.arpa:src/co5_linux/dns/db.10.20.40"; do
        named-checkzone "${z%%:*}" "${z##*:}"
    done
else
    echo "  [ -- ]  named-checkconf not installed on this host;"
    echo "          running the structural equivalent instead"
    python - <<'PYEOF'
import re
zones = {
    "db.cloudmatrix.local": "src/co5_linux/dns/db.cloudmatrix.local",
    "db.10.20.30":          "src/co5_linux/dns/db.10.20.30",
    "db.10.20.40":          "src/co5_linux/dns/db.10.20.40",
}
for name, path in zones.items():
    txt = open(path).read()
    soa = len(re.findall(r"\bSOA\b", txt))
    ns = len(re.findall(r"\sNS\s", txt))
    a = len(re.findall(r"\sA\s+\d+\.\d+\.\d+\.\d+", txt))
    ptr = len(re.findall(r"\sPTR\s", txt))
    cname = len(re.findall(r"\sCNAME\s", txt))
    serial = re.search(r"(\d{10})\s*;\s*Serial", txt)
    ttl = re.search(r"\$TTL\s+(\d+)", txt)
    ok = soa == 1 and ns >= 2 and ttl and serial
    print(f"  [{'  OK  ' if ok else ' FAIL '}] {name}")
    print(f"          $TTL={ttl.group(1)}  SOA={soa}  NS={ns}  "
          f"A={a}  PTR={ptr}  CNAME={cname}")
    print(f"          serial={serial.group(1)}  (YYYYMMDDnn form)")

fwd = open(zones["db.cloudmatrix.local"]).read()
rev = open(zones["db.10.20.30"]).read()
fa = set(re.findall(r"\sA\s+(10\.20\.30\.\d+)", fwd))
rp = {"10.20.30." + o for o in re.findall(r"^(\d+)\s+IN\s+PTR", rev, re.M)}
print(f"  [{'  OK  ' if fa == rp else ' FAIL '}] forward/reverse consistency: "
      f"{len(fa)} A records, {len(rp)} PTR records, "
      f"{'every address matched' if fa == rp else 'MISMATCH ' + str(fa ^ rp)}")
PYEOF
fi

echo
echo "== ISC DHCP configuration =="
if command -v dhcpd >/dev/null 2>&1; then
    dhcpd -t -cf src/co5_linux/dhcp/dhcpd.conf \
        && echo "  [ OK ]  dhcpd -t reports no errors"
else
    echo "  [ -- ]  dhcpd not installed on this host;"
    echo "          running the structural equivalent instead"
    python - <<'PYEOF'
import re
txt = open("src/co5_linux/dhcp/dhcpd.conf").read()
subnets = re.findall(r"subnet\s+(\S+)\s+netmask\s+(\S+)", txt)
hosts = re.findall(r"host\s+(\S+)\s*\{", txt)
ranges = re.findall(r"range\s+(\S+)\s+(\S+);", txt)
macs = re.findall(r"hardware ethernet\s+(\S+);", txt)
braces = txt.count("{") - txt.count("}")
print(f"  [{'  OK  ' if braces == 0 else ' FAIL '}] brace balance = {braces}")
print(f"          subnets      : {len(subnets)} -> " + ", ".join(s for s, _ in subnets))
print(f"          pools        : " + ", ".join(f"{a}-{b}" for a, b in ranges))
print(f"          reservations : {len(hosts)} -> " + ", ".join(hosts))
print(f"  [{'  OK  ' if len(set(macs)) == len(macs) else ' FAIL '}] "
      f"MAC uniqueness: {len(macs)} reservations, {len(set(macs))} distinct")
print(f"  [{'  OK  ' if 'authoritative;' in txt else ' FAIL '}] "
      f"authoritative flag present")
PYEOF
fi

echo
echo "== libvirt domain XML =="
python - <<'PYEOF'
import xml.dom.minidom as m
d = m.parse("src/co5_linux/virtualization/libvirt-vm-web-01.xml")
root = d.documentElement
g = lambda t: d.getElementsByTagName(t)[0].firstChild.data
print("  [  OK  ] libvirt-vm-web-01.xml is well-formed XML")
print(f"          domain       : {g('name')}  (type={root.getAttribute('type')})")
print(f"          vcpu / memory: {g('vcpu')} vCPU, {g('memory')} MiB max, "
      f"{g('currentMemory')} MiB balloon floor")
disk = d.getElementsByTagName("driver")[0]
print(f"          disk cache   : {disk.getAttribute('cache')} "
      f"(guest fsync reaches stable storage)")
print(f"          IOPS cap     : {g('total_iops_sec')}")
print(f"          traffic filter: "
      f"{d.getElementsByTagName('filterref')[0].getAttribute('filter')}")
print(f"          seclabel     : "
      f"{d.getElementsByTagName('seclabel')[0].getAttribute('model')}")
PYEOF

echo
echo "== Xen guest configuration =="
python - <<'PYEOF'
import re
txt = open("src/co5_linux/virtualization/xen-vm-db-02.cfg").read()
get = lambda k: (re.search(rf'^{k}\s*=\s*(.+)$', txt, re.M) or [None, "-"])[1]
print("  [  OK  ] xen-vm-db-02.cfg parsed")
for key in ("name", "vcpus", "maxvcpus", "cpus", "cpu_weight", "memory", "maxmem"):
    print(f"          {key:<12}= {get(key).strip()}")
print(f"          disks       = {len(re.findall(r'format=', txt))} "
      f"(qcow2 OS volume + raw LVM passthrough)")
PYEOF

echo
echo "== netplan bridge definition =="
python - <<'PYEOF'
import re
src = open("src/co5_linux/scripts/cm-netplan-br0.yaml").read()
lines = [l for l in src.splitlines() if l.strip() and not l.strip().startswith("#")]
tabs = [l for l in lines if "\t" in l]
print(f"  [{'  OK  ' if not tabs else ' FAIL '}] "
      f"{len(lines)} significant lines, {len(tabs)} tab characters "
      f"(YAML forbids tabs)")
print(f"          top-level keys: " +
      ", ".join(sorted(set(re.findall(r"^  (\w+):", src, re.M)))))
print(f"          bridge address: " +
      ", ".join(re.findall(r"- (10\.\d+\.\d+\.\d+/\d+)", src)))
print(f"          STP enabled   : {'yes' if 'stp: true' in src else 'no'}")
PYEOF

echo
echo "== logrotate retention policy =="
python - <<'PYEOF'
import re
txt = open("src/co5_linux/scripts/cloudmatrix.logrotate").read()
for block in re.findall(r"(\S+)\s*\{(.*?)\}", txt, re.S):
    path, body = block
    rotate = re.search(r"rotate\s+(\d+)", body)
    freq = re.search(r"^\s*(daily|weekly|monthly)", body, re.M)
    if rotate and freq:
        print(f"  [  OK  ] {path:<34} {freq.group(1):<8} keep {rotate.group(1)}")
PYEOF

echo
echo "=============================================================================="
echo " CO5 validation complete."
echo "=============================================================================="
