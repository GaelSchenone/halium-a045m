#!/bin/bash
# Builds halium-boot-artifacts/halium-boot-httpd.img: the good kernel +
# the original Halium ramdisk with debug-initramfs/panic-telnet swapped in
# for scripts/panic/telnet, repacked with root ownership via fakeroot.
#
# Run from the repository root:
#   debug-initramfs/build.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

echo "Extracting pristine ramdisk into $WORKDIR ..."
mkdir -p "$WORKDIR/rd"
(cd "$WORKDIR/rd" && zcat "$REPO_ROOT/halium-boot-artifacts/halium-initramfs.gz" | cpio -idm --quiet)

cp "$REPO_ROOT/debug-initramfs/panic-telnet" "$WORKDIR/rd/scripts/panic/telnet"
chmod 755 "$WORKDIR/rd/scripts/panic/telnet"

echo "Repacking ramdisk with root ownership (fakeroot) ..."
( cd "$WORKDIR/rd" && fakeroot bash -c '
    chown -R root:root .
    find . | cpio -o -H newc 2>/dev/null | gzip -9 > "'"$WORKDIR"'/initramfs-httpd.gz"
' )

echo "Building boot.img ..."
python3 "$REPO_ROOT/debug-initramfs/make_halium_boot.py" \
  "$REPO_ROOT/firmware/boot.img" \
  "$REPO_ROOT/out/kernel-4.19/arch/arm64/boot/Image.gz" \
  "$WORKDIR/initramfs-httpd.gz" \
  "$REPO_ROOT/halium-boot-artifacts/halium-boot-httpd.img" \
  "ramoops.mem_address=0x47c90000 ramoops.mem_size=0xe0000 ramoops.pmsg_size=0x10000 ramoops.console_size=0x40000 console=tty0"

echo "Done: halium-boot-artifacts/halium-boot-httpd.img"
