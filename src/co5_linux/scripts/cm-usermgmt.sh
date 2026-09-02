#!/usr/bin/env bash
#
# cm-usermgmt.sh - CloudMatrix tenant account lifecycle
#
# Usage:
#   cm-usermgmt.sh onboard  <username> <tenant-id> [pubkey-file]
#   cm-usermgmt.sh offboard <username>
#   cm-usermgmt.sh audit
#
# Every tenant gets a dedicated group, a 0700 home directory, an SSH key
# (never a password), a disk quota, and default ACLs. Tenant isolation on
# shared storage is a file-permission problem before it is a hypervisor
# problem, and this script is where that policy is actually enforced.
#

set -euo pipefail

readonly TENANT_ROOT="/srv/tenants"
readonly LOG="/var/log/cloudmatrix/usermgmt.log"
readonly QUOTA_SOFT_MB=20480
readonly QUOTA_HARD_MB=25600

log() { printf "%s [%s] %s\n" "$(date -Is)" "${1}" "${2}" | tee -a "${LOG}"; }
die() { log ERROR "${1}"; exit 1; }

[[ ${EUID} -eq 0 ]] || die "must run as root"
mkdir -p "$(dirname "${LOG}")"

onboard() {
    local user="${1}" tenant="${2}" pubkey="${3:-}"
    id -u "${user}" &>/dev/null && die "user ${user} already exists"

    getent group "tenant-${tenant}" >/dev/null || groupadd "tenant-${tenant}"

    local home="${TENANT_ROOT}/${tenant}/${user}"
    useradd --create-home --home-dir "${home}" \
            --gid "tenant-${tenant}" \
            --shell /bin/bash \
            --comment "CloudMatrix tenant ${tenant}" \
            "${user}"

    # No password is ever set. The account is key-only, so it cannot be
    # brute-forced, and `passwd --lock` makes that explicit to an auditor.
    passwd --lock "${user}" >/dev/null

    chmod 0700 "${home}"
    chown "${user}:tenant-${tenant}" "${home}"

    if [[ -n "${pubkey}" && -f "${pubkey}" ]]; then
        install -d -m 0700 -o "${user}" -g "tenant-${tenant}" "${home}/.ssh"
        install -m 0600 -o "${user}" -g "tenant-${tenant}" \
                "${pubkey}" "${home}/.ssh/authorized_keys"
        log INFO "installed SSH key for ${user}"
    else
        log WARN "no public key supplied; ${user} cannot log in until one is added"
    fi

    # Quotas stop one tenant filling the shared volume and denying service to
    # every other tenant. This is an availability control, not accounting.
    if command -v setquota >/dev/null; then
        setquota -u "${user}" \
                 "$((QUOTA_SOFT_MB * 1024))" "$((QUOTA_HARD_MB * 1024))" \
                 0 0 "${TENANT_ROOT}"
        log INFO "quota set for ${user}: ${QUOTA_SOFT_MB}M soft / ${QUOTA_HARD_MB}M hard"
    fi

    # Default ACLs so anything the tenant creates later stays inside the
    # tenant group and is unreadable by every other tenant on the volume.
    setfacl -d -m "g:tenant-${tenant}:rx" "${home}"
    setfacl -d -m o::--- "${home}"

    log INFO "onboarded ${user} into tenant ${tenant} at ${home}"
}

offboard() {
    local user="${1}"
    id -u "${user}" &>/dev/null || die "no such user: ${user}"

    # Lock first, kill sessions second, archive third, delete last. Deleting a
    # live account leaves orphaned processes holding open descriptors to data
    # that is supposed to be gone.
    usermod --lock --expiredate 1 "${user}"
    pkill -KILL -u "${user}" 2>/dev/null || true

    local home archive
    home=$(getent passwd "${user}" | cut -d: -f6)
    archive="/srv/backup/offboard/${user}-$(date +%Y%m%d).tar.gz"
    mkdir -p "$(dirname "${archive}")"
    tar --create --gzip --file "${archive}" "${home}" 2>/dev/null || true
    chmod 0600 "${archive}"
    log INFO "archived ${home} -> ${archive}"

    userdel --remove "${user}"
    log INFO "offboarded ${user}; home removed, audit archive retained"
}

audit() {
    printf "%-16s %-14s %-32s %-10s\n" USER GROUP HOME SHELL
    while IFS=: read -r name _ uid _ _ home shell; do
        (( uid >= 1000 && uid < 65534 )) || continue
        printf "%-16s %-14s %-32s %-10s\n" \
            "${name}" "$(id -gn "${name}")" "${home}" "$(basename "${shell}")"
    done < /etc/passwd

    echo
    echo "Accounts with a usable password (policy says there should be none):"
    awk -F: '$2 !~ /^[*!]/ {print "  " $1}' /etc/shadow || echo "  none"

    echo
    echo "World-readable tenant homes (policy says there should be none):"
    find "${TENANT_ROOT}" -maxdepth 2 -type d -perm -o=r -print 2>/dev/null \
        || echo "  none"

    echo
    echo "Sudoers entries granting unrestricted root:"
    grep -rE "ALL\s*=\s*\(ALL(:ALL)?\)\s*(NOPASSWD:)?\s*ALL" \
         /etc/sudoers /etc/sudoers.d/ 2>/dev/null || echo "  none"
}

case "${1:-}" in
    onboard)  shift; [[ $# -ge 2 ]] || die "usage: onboard <user> <tenant> [key]"
              onboard "$@" ;;
    offboard) shift; [[ $# -eq 1 ]] || die "usage: offboard <user>"
              offboard "$@" ;;
    audit)    audit ;;
    *)        echo "usage: $0 {onboard|offboard|audit} [args]" >&2; exit 2 ;;
esac
