# Port de GNU/Linux al Samsung Galaxy A04 (SM-A045M)

## Objetivo
Reemplazar Android por una distro GNU/Linux de escritorio real (no chroot/proot),
usando el enfoque Halium: mantener el kernel downstream de Samsung/MediaTek
(con sus blobs de GPU/módem/wifi funcionando) y correr un userspace GNU/Linux
completo arriba, puenteando el hardware vía `libhybris`.

## Hardware
- Equipo: Samsung Galaxy A04, modelo **SM-A045M**
- SoC: MediaTek MT6765 (Helio P35), 12nm
- GPU: PowerVR GE8320 (blob cerrado, sin driver libre viable)
- Bootloader: **desbloqueado** ✅

## Por qué Halium y no mainline puro
No existe soporte mainline (kernel.org) para el MT6765 — a diferencia de SoCs
MediaTek de Chromebooks (MT8183, MT8192) que Google/Collabora subieron río
arriba, este chip de gama baja no tuvo ese trabajo corporativo. Escribir
drivers desde cero (GPU, clocks, módem) sería un proyecto de investigación de
años sin garantía de resultado.

Halium evita ese problema: no reemplaza el kernel ni sus drivers de vendor,
solo cambia el ramdisk/init y usa `libhybris` para que un userspace glibc
normal pueda llamar a las HALs de Android (gráficos, audio, RIL, sensores).
Es la misma técnica de Ubuntu Touch, LuneOS y los "halium devices" de
postmarketOS.

## Precedentes encontrados
- **Kernel fuente**: [physwizz/a045m-T-s4](https://github.com/physwizz/a045m-T-s4)
  — kernel GPL de Samsung para el A045M, Android 13, **Linux 4.19.191**,
  defconfig `mt6765-general_variant`. Clonado en `./kernel`.
- **Mismo SoC con Halium funcionando** (referencia de arquitectura, no de tu
  dispositivo puntual): [ubports-xiaomi-cereus](https://github.com/ubports-xiaomi-cereus)
  (Redmi 6/6A, también MT6765).
- **Mainline real para el MT6765** (actualizado, corrige lo que decíamos antes):
  [evilMyQueen/linux-mt6765](https://github.com/evilMyQueen/linux-mt6765), rama
  `mt6765-devel`, basado en Linux 7.1 mainline, con patches reales de
  evilMyQueen y Arseniy Velikanov (adomerle) agregando SMP, GPIO, SCP,
  Watchdog, PWRAP, ADC, UART, PWM, I2C, SPI, USB, MMC y DSI (pantalla) para el
  MT6765. Tienen device trees para Nokia 3.1 Plus y soporte parcial de Redmi
  9A, pero **ningún device tree para el A04/A045M todavía**. Comunidad activa
  en Matrix: `#lenovomt6765:matrix.vistaslayer.ovh`.
- Confirmado contra pmaports (GitLab) que **no existe** `device-samsung-a04`
  ni en `main`, `community`, `testing` ni `archived` — cualquier cosa que diga
  la wiki de postmarketOS sobre el A04 "en desarrollo" es informal, no hay un
  port publicado para instalar.
- Alternativa a evaluar más adelante: en vez de (o además de) Halium, escribir
  un device tree nuevo para el A045M sobre `mt6765.dtsi` sería Linux mainline
  real, sin blobs, aunque sin GPU acelerada ni módem al principio.

## Roadmap

### Fase 0 — Entorno de build ✅
- [x] Instalar toolchain aarch64 (`gcc-aarch64-linux-gnu` vía apt) — **no se
      terminó usando**, ver nota abajo.
- [x] Bajar el harness oficial de build de Android (`build/`, rama
      `android-msm-redbull-4.19-android12-qpr1` de
      `android.googlesource.com/kernel/build`, la última que todavía trae
      `build.sh` — las ramas modernas usan Bazel/Kleaf y no sirven acá).
- [ ] Bajar firmware stock completo del CSC exacto del equipo (para poder
      volver atrás con Odin ante cualquier bootloop). **Pendiente, hacelo
      antes de flashear nada.**
- [x] Espacio en disco: con el kernel (~650MB) y el harness de build (liviano,
      son scripts) alcanza y sobra.

**Nota clave de toolchain:** el kernel de physwizz ya trae vendorizado el
compilador exacto original (`kernel/toolchain/clang/host/linux-x86/clang-r383902`
y binutils `toolchain/toolchains-gcc-10.3.0`). El `Makefile` del kernel usa
`CC = clang` hardcodeado (o el path a ese clang si `$LLVM` está vacío) — usar
`aarch64-linux-gnu-gcc` del sistema en vez de este toolchain rompe el build
con errores de sintaxis rarísimos. **Siempre usar el toolchain vendorizado.**

### Fase 1 — Kernel propio, boot sanity check ✅ (compilación) / ⏳ (boot real)
- [x] Compilar `kernel/` tal cual, sin modificar nada — **logrado**, con el
      harness oficial (`build/build.sh`). Generó `Image`, `Image.gz` y el DTB
      exacto `mt6765_a04_eur_open_00.dtb` en
      `out/kernel-4.19/arch/arm64/boot/`.
- [ ] Empaquetar boot.img con el ramdisk **stock** (extraído del firmware
      original) + el kernel recién compilado.
- [ ] Flashear por Odin/heimdall y confirmar que bootea Android normal.
      Esto valida el toolchain y la firma/formato de imagen antes de tocar
      nada del lado de Linux.

**Cómo se compiló (para repetirlo):**
```sh
# Estructura de directorios que espera build.sh (symlinks ya creados en el repo):
#   linux-a04/kernel-4.19 -> kernel
#   linux-a04/prebuilts   -> kernel/toolchain
cd linux-a04
DEFCONFIG=a04_defconfig BUILD_CONFIG=kernel-4.19/build.config.mtk.aarch64 \
  build/build.sh CC=<ruta al wrapper de clang, ver nota>
```

**Bugs reales encontrados y arreglados (no son inventados, son del vendor
kernel o del entorno de build):**
1. **`init/version.c` no compila** con "expected ';' after top level
   declarator": `scripts/mkcompile_h` corre `clang -v` para armar el string de
   versión, y como esta máquina tiene CUDA instalado, clang imprime una línea
   extra ("Found CUDA installation...") que contiene la palabra "version" y
   contamina el string generado. Arreglado con un wrapper de clang que filtra
   esa línea (no se tocó el kernel). Sin este wrapper, **cualquier build en
   una máquina con CUDA va a fallar igual**.
2. **`CONFIG_IKHEADERS`** rompía por `/tools/build/cpio: No such file or
   directory` (el script espera el harness completo de AOSP). Se resuelve
   solo al usar `build.sh` con la estructura de directorios correcta; no hizo
   falta desactivarlo en la build final.
3. **`kernel/trace/Makefile`**: a `mtk_trace.o` y `trace_mmstat.o` les faltaba
   `CFLAGS_*.o := -I$(src)` — bug real del vendor kernel (Kbuild no propaga
   `ccflags-y` a subdirectorios). Fix de una línea, commiteado en el
   submódulo.
4. **⚠️ Peligro con `make mrproper` in-tree**: como el toolchain vendorizado
   vive *adentro* de `kernel/`, un `make mrproper` corrido directo en el
   árbol (sin `O=`) barre `*.a`/`*.o` de **todo** el srctree, incluido el
   toolchain — se borró y se restauró con `git checkout -- .` sin problema
   porque son archivos trackeados. **Nunca correr `make clean`/`mrproper`
   in-tree acá; usar `git clean -fdx` o el `mrproper` con `O=` del harness.**

### Fase 2 — Halium ramdisk (hybris-boot)
- [ ] Reemplazar el ramdisk por el de `halium-boot`, manteniendo vivos los
      servicios de vendor (vold, hwcomposer, etc.) que dependen las HALs.
- [ ] Resolver particularidades de partición de Samsung (AVB/vbmeta,
      `up_param`, posibles chequeos de Knox) que rompan el boot.

### Fase 3 — libhybris + HALs
- [ ] Conectar hwcomposer2 para salida de pantalla.
- [ ] Input (esto sí te va a andar bien acá, a diferencia del S9 con táctil
      roto).
- [ ] Audio y sensores vía HALs binarias existentes.

### Fase 4 — Rootfs
- [ ] Usar el rootfs "halium generic" de postmarketOS o Ubuntu Touch como
      base en vez de armar uno propio.

### Fase 5 — Bring-up iterativo
Orden sugerido (de más fácil a más frágil):
1. Pantalla
2. Táctil
3. WiFi
4. Audio
5. Módem/RIL (vía ofono) — el más propenso a fallar
6. Sensores

### Fase 6 — Debug
- Sin puerto serie disponible, vas a depender de `adb logcat` / `dmesg` en
  cada intento fallido de boot. Más lento, pero viable.

## Riesgos conocidos
- Proyecto de **meses**, no semanas — sos probablemente la primera persona
  portando Halium a este modelo puntual.
- Módem/RIL puede terminar sin funcionar nunca.
- Cualquier boot.img mal armado puede dejar el equipo en un estado que solo
  se recupera reflasheando el firmware stock completo por Odin — **tené
  siempre a mano el firmware original de fábrica de tu CSC exacto antes de
  tocar nada**.
