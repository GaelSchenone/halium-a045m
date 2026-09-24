# halium-a045m

Halium-based GNU/Linux port for the Samsung Galaxy A04 (SM-A045M), MediaTek
MT6765 (Helio P35). The goal is to replace Android entirely with a real
desktop GNU/Linux userspace at boot, while reusing the vendor kernel and its
closed-source HALs (GPU, modem, Wi-Fi) through `libhybris` instead of
rewriting drivers from scratch.

## Status

Phase 1 is complete and verified on real hardware: the vendor kernel builds
cleanly with the original Android kernel build harness, boots on the device
(confirmed via `adb shell uname -r` reporting our own build, not Samsung's),
and required a full data wipe due to a gap in Samsung's published GPL source
(see [PORTING.md](PORTING.md) for details — `CONFIG_F2FS_SEC_ENC_STRICT_MODE`
is enabled in the shipped kernel but its implementation was never published).

Phase 2 has a first major milestone: the generic Halium reference product
(`lineage_halium_arm64`, VNDK 31 / Android 12, matching this device's vendor
partition) builds successfully end to end with the real Android build system,
producing a 571MB `system.img`. Getting there required syncing Halium's full
~1159-project source tree and fixing several real bugs — a Halium/libhybris
branch mismatch (pinned to `halium-11.0` while everything else tracks
`halium-12.0`), a legacy host-toolchain dependency, and host RAM/disk limits
on the build machine. See [PORTING.md](PORTING.md) for the full log.

The first flash attempt (`halium-boot.img` + a repacked `super.img`) failed
reproducibly partway through with the repacked image as a sparse file
(confirmed cause: too many sparse chunks — 4760 vs. 168 in the stock
image). Repacking it as raw instead flashed cleanly on the first try. With
both flashed, the device boots as far as the "bootloader unlocked" warning
screen and hangs there, with no USB interface exposed — no serial console
available on this hardware.

To debug the hang without opening the device, it was rooted with Magisk (to
read `/sys/fs/pstore/`) and several capture attempts were made. pstore turned
out not to be viable here: the only way found to force the device out of the
hang (a hardware key-combo reset) itself triggers a deliberate kernel
`BUG()` (Samsung's own "hold Power+VolDown 7s" hard-reset mechanism), which
overwrites the actual hang's log with its own panic dump before it can be
read. A more promising path was found instead: Halium's own `hybris-boot`
exposes a USB-networked telnet debug shell automatically when boot fails
(confirmed reaching this device — the host sees a distinct USB descriptor,
"Halium initrd" / "Failed to boot", handing out DHCP over RNDIS), but the
bundled BusyBox `telnetd` (v1.22.1) fails to actually attach a shell to the
connection — a fix is still unconfirmed.

As an alternative, work moved to building `hybris-recovery.img` (a
purpose-built debug/rescue image) on a second machine over the LAN, which
surfaced and fully resolved a real, reusable build issue: this checkout's
VNDK prebuilt snapshots (v28-v31) reference generated interface headers via
a relative `include/out` path that needs a symlink back into the main
build's `out/` tree — one that never existed, plus one snapshot version
(v30) turned out to be entirely unnecessary and had to be excised from a
platform-level Android.bp that hardcodes all four versions. After clearing
that, `hybris-recovery` itself turned out not to be a valid build target in
this Halium checkout at all — neither the (also missing, since separately
found and added) Halium recovery fork nor `halium-boot`'s own build rules
define it, and it may simply be obsolete in Halium 12 (the docs describing
it reference the old LXC-container architecture from Halium 9-11).

The debug telnet path was resolved instead, with a working shell obtained
for the first time. Two real, unrelated bugs were found and fixed:
repacking the ramdisk as a non-root user silently records the invoking
user's UID/GID in the cpio archive instead of root's, which breaks early
boot outright (fixed with `fakeroot`) — this had been masking every prior
attempt at fixing `telnetd` itself; and `/dev/ptmx` is simply missing from
this ramdisk's `/dev` (`/dev/pts/ptmx`, the underlying devpts multiplexer,
is present, but the conventional top-level symlink isn't), which is why no
program — `telnetd` included — could ever allocate a pty. With a one-line
`ln -s pts/ptmx /dev/ptmx` added before starting `telnetd -F`, a real
interactive shell finally comes up. That shell confirms the actual hang:
`/proc/mounts` never gains a `/system` or `/vendor` entry, and `ps` shows
nothing beyond kernel threads and the debug script's own `/init` — the boot
fails before `mountroot` ever attempts to mount the dynamic partitions from
`super`.

`telnetd` turned out to only ever be reliable for one interaction per
connection, so an HTTP/CGI debug channel (`debug-initramfs/`, `busybox
httpd`) was built to sidestep telnet/pty entirely — which surfaced a much
bigger finding: a hardcoded, no-fork response (a 404 page) always arrives
instantly and complete, but *anything requiring a forked child to read or
write through the inherited network socket* — real static files, CGI
command output, and `telnetd`'s own shell — hangs forever. The same class
of hang was independently observed reading certain sysfs attributes (under
`/sys/class/mmc_host/` and `/sys/class/android_usb/.../f_mass_storage/`),
freezing `/init` (PID 1) itself mid-read. This looks like a real kernel bug
— some sysfs `.show()` callback blocking forever in uninterruptible sleep —
and is now the leading suspect for why Halium's own mount script never gets
past discovering `/system`/`/vendor` in the first place.

Two more isolated tests ruled out the remaining alternative explanations.
Capturing a `sysrq` task-state dump into pstore across a reboot turned out
to be a dead end regardless of timing or technique: Samsung's own reboot
handler unconditionally overwrites the pstore console buffer with a fixed
message on every reboot. And re-testing the telnet/HTTP channels on a fresh
boot, with `dmesg` as the sole first command over telnet and with the HTTP
diagnostic file already fully written to disk beforehand, confirmed neither
failure is about command choice, timing, or connection reuse: telnet's
shell echo cuts off at an unpredictable byte offset each time (consistent
with BusyBox `ash`'s line editor getting stuck after an unanswered cursor-
position query), while HTTP serves perfect headers — including the correct
`Content-Length` for a file that already existed — but never delivers any
body bytes. Both debug channels are unusable for bulk data for reasons
unrelated to the underlying sysfs-hang bug; only the single-line `iSerial`
channel remains reliable.

Using that channel to grep the kernel log directly turned up a real
surprise: `mmcblk0` enumerates its 16 partitions cleanly less than a
second into boot, with no sign of the block driver itself hanging —
contradicting the earlier suspicion that MMC probing never completes. To
dig further, the kernel's own hung-task detector was enabled
(`CONFIG_DETECT_HUNG_TASK`, 30-second threshold), which surfaced something
bigger: a *second* `dmesg` call made roughly 35 seconds into boot hangs
forever and is not even killable via `timeout` — a genuine kernel-side
uninterruptible-sleep stall, not a slow read. The first call, made early,
always succeeds. Removing `console=tty0` (the framebuffer console, on a
device with no working display driver yet) from the kernel command line,
to test whether something was stuck mid-`printk()` against a broken
console, made no difference — the same hang recurred identically. This
points at something more fundamental than any one storage or display
driver: some kernel-internal lock or mechanism that jams up on essentially
every boot of this kernel around the 30-40 second mark, independent of
Halium or mounting at all — and which also happens to make the very tool
needed to diagnose it (`dmesg`) unusable past that point. See PORTING.md
for the full investigation and the plan to pin the root cause down
further.

See [PORTING.md](PORTING.md) for the full roadmap, build instructions, and a
detailed log of every issue found and fixed so far.

## Why Halium instead of a from-scratch mainline port

There is no meaningful mainline (kernel.org) support for the MT6765. Unlike
the MediaTek SoCs used in Chromebooks (MT8183, MT8192), which Google and
Collabora upstreamed, this budget-tier chip never received that investment.
A community fork ([evilMyQueen/linux-mt6765][mt6765-mainline]) is doing real
mainline bring-up for this SoC — SMP, UART, I2C, SPI, USB, MMC, and display
are working on other devices — but it has no device tree for the A045M yet,
and it will not have a working GPU driver for the foreseeable future, since
the PowerVR GE8320 has no open driver.

Halium sidesteps this: the Android kernel and its vendor blobs are kept
mostly intact, and `libhybris` bridges a normal glibc userspace to the
Android HALs. This is the same approach used by Ubuntu Touch, LuneOS, and
postmarketOS's "halium" device family.

[mt6765-mainline]: https://github.com/evilMyQueen/linux-mt6765

## Hardware target

| | |
|---|---|
| Device | Samsung Galaxy A04, model **SM-A045M** |
| SoC | MediaTek MT6765 (Helio P35), 12nm |
| GPU | Imagination PowerVR GE8320 (closed-source blob) |
| Kernel base | Linux 4.19.191, Samsung/MediaTek downstream (Android 13) |

## Repository layout

```
kernel/          Git submodule: physwizz/a045m-T-s4, the GPL kernel source
                 Samsung published for the SM-A045M.
build/           Git submodule: the last branch of Google's kernel/build
                 that still ships the legacy build.sh (newer branches moved
                 to Bazel/Kleaf, which this old kernel doesn't use).
kernel-4.19 ->   Symlink to kernel/, matching the directory name build.sh
kernel           expects (set via KERNEL_DIR in build.config.mtk.aarch64).
prebuilts ->     Symlink to kernel/toolchain, matching the sibling
kernel/toolchain "prebuilts/" directory build.config.mtk.aarch64 expects
                 for the clang toolchain — already vendored inside the
                 kernel source, no separate download needed.
out/             Build output (gitignored).
halium/          Halium's full repo-synced source tree (gitignored, ~88GB —
                 not something to version; reproducible from
                 vendor/halium/manifest, branch halium-12.0).
halium-patches/  Patches applied inside halium/ that aren't upstream yet
                 (branch mismatches, compat fixes), with instructions to
                 reapply them after a clean repo sync.
firmware/        Stock firmware backup + extracted boot.img pieces
                 (gitignored, several GB).
debug-initramfs/ Tooling to build a debug boot.img: a patched copy of
                 initramfs-tools-halium's scripts/panic/telnet (the /dev/
                 ptmx fix, an HTTP/CGI debug channel), the boot.img
                 assembly script, and an `hdbg` client. Run
                 `debug-initramfs/build.sh` to produce
                 halium-boot-artifacts/halium-boot-httpd.img.
PORTING.md       Full roadmap, phase-by-phase status, and build log.
```

## Building the kernel

```sh
DEFCONFIG=a04_defconfig \
BUILD_CONFIG=kernel-4.19/build.config.mtk.aarch64 \
  build/build.sh
```

This must run from the repository root, with the `kernel-4.19` and
`prebuilts` symlinks in place (already committed to the repo). See
[PORTING.md](PORTING.md) for the toolchain gotchas this build hits on a
modern host (in particular: a machine with CUDA installed needs a small
clang wrapper, documented there, or `init/version.c` fails to compile) and
for the full list of vendor Makefile bugs found and fixed along the way.

Do not run `make clean` or `make mrproper` directly inside `kernel/`: the
vendor toolchain lives inside that same tree, and Kbuild's clean targets
sweep `*.o`/`*.a` across the whole source tree, deleting it as collateral
damage. Use `git clean -fdx` inside `kernel/` instead, or the `O=`-scoped
`mrproper` that `build.sh` already runs.

## Roadmap

1. **Kernel build** — done.
2. **Boot sanity check** — done. Custom kernel + stock ramdisk boots on
   real hardware (required a data wipe, see PORTING.md).
3. **Halium system.img** — done. The generic `lineage_halium_arm64` product
   builds successfully (571MB system.img).
4. **`halium-boot.img` + repacked `super.img`** — built.
   `/system` turned out to be a dynamic-partitions logical volume inside
   `super`, not a physical partition — required compiling `lpmake`/
   `lpunpack` and repacking `super.img` with Halium's system.img swapped in.
   See PORTING.md for the full process.
5. **Flashing** — solved. The sparse-format repack failed reproducibly at
   ~18% (too many sparse chunks — 168 in the original vs. 4760 in ours);
   repacking as raw instead flashed cleanly.
6. **First boot attempt** — hangs at the bootloader warning screen, no
   crash, no recovery prompt, nothing visible past that point, no USB
   interface exposed. Device rooted (Magisk) to enable further debugging.
   pstore/ramoops ruled out as a diagnostic path (the only recovery method
   found overwrites it with its own panic dump). Halium's built-in
   USB-networked telnet debug shell was confirmed reachable on this device,
   but its `telnetd` has a bug preventing an actual shell from attaching —
   a fix is in progress, with `hybris-recovery.img` as the fallback plan.
   See PORTING.md for the full investigation.
7. Wire up `libhybris` and the HALs: display, input, audio, sensors.
8. Bring up a Halium-generic rootfs (postmarketOS or Ubuntu Touch base).
9. Iterative hardware bring-up: display, touch, Wi-Fi, audio, modem/RIL,
   sensors — in that order, from least to most likely to fail.

Full detail, including known risks and every fix applied so far, is in
[PORTING.md](PORTING.md).

## License

`kernel/` and `build/` are separate upstream projects under their own
licenses (GPL-2.0 for the kernel, Apache-2.0 for the build scripts). This
repository's own content (documentation, patches, build glue) has no license
file yet; treat it as all-rights-reserved until one is added.

## Credits

- [physwizz](https://github.com/physwizz) for mirroring Samsung's GPL kernel
  release for the A045M.
- [evilMyQueen](https://github.com/evilMyQueen) and Arseniy Velikanov
  (adomerle) for the mainline MT6765 bring-up work referenced above.
- The [Halium](https://halium.org/) and [ubports-xiaomi-cereus][cereus]
  projects, for proving this approach works on the same SoC.

[cereus]: https://github.com/ubports-xiaomi-cereus
