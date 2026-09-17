#!/usr/bin/env bash
# Deploy the 3-node cEOS lab on the local OpenShift Local (CRC) VM.
# Containerlab is installed on that VM so AAP job pods can reach device SSH.
set -euo pipefail

SSH_KEY="${CRC_SSH_KEY:-$HOME/.crc/machines/crc/id_ed25519}"
SSH_OPTS=(-p 2222 -i "$SSH_KEY" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o IdentitiesOnly=yes)
SCP_OPTS=(-P 2222 -i "$SSH_KEY" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o IdentitiesOnly=yes)
REMOTE=core@127.0.0.1
REMOTE_DIR=/home/core/arista-clab
ROOT="$(cd "$(dirname "$0")" && pwd)"

find_ceos_archive() {
  local candidates=(
    "$HOME/Downloads"/cEOSarm-lab*.tar.xz
    "$HOME/Downloads"/cEOSarm-lab*.tar
    "$HOME/Downloads"/cEOS64-lab*.tar.xz
    "$HOME/Downloads"/cEOS64-lab*.tar
    "$HOME/Downloads"/cEOS-lab*.tar.xz
    /tmp/cEOS*.tar.xz
    /tmp/cEOSarm*.tar.xz
  )
  local f
  for f in "${candidates[@]}"; do
    [[ -f "$f" ]] && { echo "$f"; return 0; }
  done
  return 1
}

echo "== copying topology to CRC VM =="
ssh "${SSH_OPTS[@]}" "$REMOTE" "mkdir -p $REMOTE_DIR/startup"
scp "${SCP_OPTS[@]}" "$ROOT/eos.clab.yml" "$REMOTE:$REMOTE_DIR/"
scp "${SCP_OPTS[@]}" "$ROOT/startup/"*.cfg "$REMOTE:$REMOTE_DIR/startup/"

ARCHIVE="${CEOS_ARCHIVE:-}"
if [[ -z "$ARCHIVE" ]]; then
  ARCHIVE="$(find_ceos_archive || true)"
fi

if [[ -z "$ARCHIVE" ]]; then
  cat <<'EOF'
No cEOS-lab archive found.

Arista does not publish cEOS to a public registry. Download an ARM64 image
(this CRC VM is aarch64) from https://www.arista.com/en/support/software-download
after logging in with a free Arista account:

  cEOSarm-lab-<version>.tar.xz

Save it to ~/Downloads and re-run this script, or:

  CEOS_ARCHIVE=/path/to/cEOSarm-lab-*.tar.xz ./containerlab/deploy.sh
EOF
  exit 1
fi

echo "== importing $ARCHIVE as ceos:latest =="
scp "${SCP_OPTS[@]}" "$ARCHIVE" "$REMOTE:/tmp/ceos.tar.xz"
ssh "${SSH_OPTS[@]}" "$REMOTE" 'set -e
  if sudo podman image exists ceos:latest; then
    echo "ceos:latest already present"
  else
    sudo podman import /tmp/ceos.tar.xz ceos:latest
  fi
  sudo podman images ceos
  echo "== deploying containerlab =="
  cd /home/core/arista-clab
  sudo CLAB_RUNTIME=podman containerlab deploy --reconfigure --topo eos.clab.yml
  sudo containerlab inspect --topo eos.clab.yml
'
echo
echo "AAP inventory should use:"
echo "  leaf-01  ansible_host=192.168.127.2  ansible_port=2201"
echo "  leaf-02  ansible_host=192.168.127.2  ansible_port=2202"
echo "  spine-01 ansible_host=192.168.127.2  ansible_port=2203"
echo "  Network credential: admin / admin"
