#!/usr/bin/env bash
#
# cm-backup.sh - CloudMatrix nightly backup of configs, zones and guest images
#
# Deployed as /usr/local/sbin/cm-backup.sh and invoked from a systemd timer:
#   [Timer]
#   OnCalendar=*-*-* 02:15:00
#   RandomizedDelaySec=600
#
# Design notes
#   * `set -euo pipefail` so a partial backup fails loudly instead of quietly
#     producing an archive that looks fine and restores to nothing.
#   * A guest image is snapshotted with `virsh snapshot-create-as` BEFORE it is
#     copied, so the archive holds a consistent image rather than a torn one.
#     Copying a running qcow2 without a snapshot is the single most common way
#     to produce an unrestorable backup.
#   * The archive is checksummed, flushed with `sync -f`, and then verified.
#     An archive still sitting in the page cache is not a backup.
#

set -euo pipefail

readonly BACKUP_ROOT="/srv/backup/cloudmatrix"
readonly RETENTION_DAYS=14
readonly STAMP="$(date +%Y%m%d-%H%M%S)"
readonly DEST="${BACKUP_ROOT}/${STAMP}"
readonly LOG="/var/log/cloudmatrix/backup.log"
readonly LOCKFILE="/var/run/cm-backup.lock"

log() { printf "%s [%s] %s\n" "$(date -Is)" "${1}" "${2}" | tee -a "${LOG}"; }
die() { log ERROR "${1}"; exit 1; }

# Refuse to run twice: a second copy racing the first corrupts the archive.
exec 9>"${LOCKFILE}"
flock -n 9 || die "another cm-backup run holds the lock; aborting"

trap 'log ERROR "backup aborted at line ${LINENO}"; exit 1' ERR

[[ ${EUID} -eq 0 ]] || die "must run as root (needs virsh and /etc access)"

mkdir -p "${DEST}" "$(dirname "${LOG}")"
log INFO "backup started -> ${DEST}"

# --- 1. flat configuration -------------------------------------------------
log INFO "archiving DNS, DHCP, netplan and libvirt configuration"
tar --create --gzip \
    --file "${DEST}/etc-config.tar.gz" \
    --absolute-names \
    /etc/bind /etc/dhcp /etc/netplan /etc/libvirt \
    2>>"${LOG}"

# --- 2. inventory, so a rebuild is reproducible ---------------------------
dpkg --get-selections > "${DEST}/packages.list"
systemctl list-unit-files --state=enabled --no-pager > "${DEST}/enabled-units.list"
ip -json addr show > "${DEST}/network-state.json"

# --- 3. guest images, snapshot first --------------------------------------
mapfile -t GUESTS < <(virsh list --name --state-running || true)
log INFO "found ${#GUESTS[@]} running guest(s)"

for guest in "${GUESTS[@]}"; do
    [[ -z "${guest}" ]] && continue
    snap="backup-${STAMP}"
    log INFO "snapshotting ${guest}"

    # --quiesce asks qemu-guest-agent to freeze the guest filesystem, which
    # turns a crash-consistent copy into an application-consistent one. If the
    # agent is absent we degrade rather than fail, but we say so in the log.
    if ! virsh snapshot-create-as --domain "${guest}" --name "${snap}" \
            --atomic --disk-only --quiesce >>"${LOG}" 2>&1; then
        log WARN "guest-agent quiesce unavailable for ${guest}; falling back to crash-consistent"
        virsh snapshot-create-as --domain "${guest}" --name "${snap}" \
            --atomic --disk-only >>"${LOG}" 2>&1 \
            || { log ERROR "snapshot failed for ${guest}; skipping"; continue; }
    fi

    virsh dumpxml "${guest}" > "${DEST}/${guest}.xml"
    base=$(virsh domblklist "${guest}" --details | awk "/disk/ && /file/ {print \$4; exit}")
    if [[ -n "${base}" && -f "${base}" ]]; then
        log INFO "copying ${base}"
        cp --sparse=always "${base}" "${DEST}/${guest}.qcow2"
    fi

    # Fold the snapshot overlay back into the base image and drop it.
    virsh blockcommit "${guest}" vda --active --pivot --wait >>"${LOG}" 2>&1 \
        || log WARN "blockcommit failed for ${guest}; overlay left in place"
done

# --- 4. checksum, then force everything to stable storage -----------------
cd "${DEST}" && sha256sum ./* > SHA256SUMS
sync -f "${DEST}"
log INFO "checksums written and flushed to stable storage"

# --- 5. verify before trusting --------------------------------------------
sha256sum --check --quiet SHA256SUMS \
    || die "checksum verification FAILED - this backup is not trustworthy"
log INFO "checksum verification passed"

# --- 6. retention ----------------------------------------------------------
find "${BACKUP_ROOT}" -maxdepth 1 -type d -mtime "+${RETENTION_DAYS}" \
     -regextype posix-extended -regex ".*/[0-9]{8}-[0-9]{6}$" \
     -print -exec rm -rf {} +

SIZE=$(du -sh "${DEST}" | cut -f1)
log INFO "backup completed successfully: ${DEST} (${SIZE})"
