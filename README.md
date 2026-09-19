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
4. **`halium-boot.img` + repacked `super.img`** — done, not yet flashed.
   `/system` turned out to be a dynamic-partitions logical volume inside
   `super`, not a physical partition — required compiling `lpmake`/
   `lpunpack` and repacking `super.img` with Halium's system.img swapped in.
   See PORTING.md for the full process.
5. Flash both and see if Halium's HAL-bridge layer actually boots on this
   hardware — next step.
6. Wire up `libhybris` and the HALs: display, input, audio, sensors.
7. Bring up a Halium-generic rootfs (postmarketOS or Ubuntu Touch base).
8. Iterative hardware bring-up: display, touch, Wi-Fi, audio, modem/RIL,
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
