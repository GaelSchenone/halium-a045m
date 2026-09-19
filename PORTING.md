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

### Fase 1 — Kernel propio, boot sanity check ✅ COMPLETA
- [x] Compilar `kernel/` tal cual, sin modificar nada — **logrado**, con el
      harness oficial (`build/build.sh`). Generó `Image`, `Image.gz` y el DTB
      exacto `mt6765_a04_eur_open_00.dtb` en
      `out/kernel-4.19/arch/arm64/boot/`.
- [x] Empaquetar boot.img con el ramdisk **stock** (extraído del firmware
      original) + el kernel recién compilado. Header Android bootimg v2,
      formato preservado byte a byte salvo el kernel. Script en
      `PORTING.md` (ver "Cómo se armó el boot.img" abajo).
- [x] Flashear por Heimdall y confirmar boot real en el equipo físico
      (SM-A045M, build A045MUBSGEZE1). **Confirmado**: `adb shell uname -r`
      devuelve `4.19.191-geb4dea5ce8e1-dirty` (nuestro build, no el de
      Samsung) con el equipo andando normalmente.

**Firmware stock de respaldo:** descargado con
[topjohnwu/samloader-rs](https://github.com/topjohnwu/samloader-rs) (el
`samloader` en Python de nlscc está roto — las claves AES hardcodeadas para
desencriptar el nonce de FUS quedaron desactualizadas). Versión exacta:
`A045MUBSGEZE1/A045MOWOGEZE1/A045MUBSGEZE1/A045MUBSGEZE1`, CSC `ARO`
(Argentina). Guardado en `firmware/` (gitignored, pesa ~6GB).

**Cómo se armó el boot.img:**
1. `lz4 -d boot.img.lz4 boot.img` sobre el `boot.img.lz4` del `AP_*.tar.md5`
   del firmware stock.
2. Parsear el header Android bootimg (v2: magic + 10 campos uint32 + name +
   cmdline + id + extra_cmdline + recovery_dtbo\_\* + dtb_size/dtb_addr,
   1660 bytes reales dentro de una página de 2048) para extraer kernel,
   ramdisk y el bloque de DTB final (identificado por el magic
   `0xd7b7ab1e`, formato `DT_TABLE` — no es un `.dtb` suelto).
3. Repacker: mismo header con `kernel_size` actualizado al tamaño de
   nuestro `Image.gz`, mismo ramdisk y bloque DTB copiados sin tocar, mismo
   tamaño total de archivo (32MB, el tamaño de la partición `boot`).
4. `heimdall flash --boot boot_custom.img` (la partición se llama `boot`
   en minúscula, confirmado con `heimdall print-pit`).

**Hallazgo importante — brecha en el release GPL de Samsung:** el primer
intento de boot cayó en recovery ("no se pudo cargar Android, los datos
pueden estar corruptos"). Comparando `/proc/config.gz` del kernel stock
corriendo contra nuestro `.config`, la diferencia relevante fue
`CONFIG_F2FS_SEC_ENC_STRICT_MODE=y` en el stock — **un símbolo de Kconfig
que no existe en ningún lado del código fuente publicado**. Es decir,
Samsung no publicó el 100% de los parches de seguridad del kernel real
(pasa seguido con DEFEX/Knox/cifrado). Nuestro kernel no podía montar el
`/data` ya cifrado bajo esa política estricta. Con un factory reset,
`/data` se recreó desde cero bajo nuestro kernel y bootea sin problema.
**Implicancia a futuro:** cualquier `/data` cifrado con el kernel stock va
a ser ilegible para builds nuestras; hay que wipear al cambiar de kernel.
Para Halium esto probablemente no importa, ya que la idea es no depender
del `/data` cifrado de Android de todos modos.

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

### Fase 2 — Halium ramdisk (hybris-boot) ✅ se flashea bien / ❌ no completa el arranque todavía
- [x] Sincronizar el árbol completo de Halium (manifest `halium-12.0`, ~1159
      proyectos, ~88GB) con `repo`, en `./halium`.
- [x] Compilar el producto genérico de referencia `lineage_halium_arm64` con
      el sistema de build oficial de Android (Soong/Make) — **`system.img`
      generado con éxito** (571MB) en
      `/run/media/gael-schenone/Datos/halium-build/out/target/product/halium_arm64/`.
      `TARGET_NO_KERNEL := true` en este producto: no compila kernel, usa el
      que ya armamos en la Fase 1.
- [x] Armar `halium-boot.img` (kernel + initramfs oficial de Halium + DTB del
      stock) — en `firmware/halium-boot-artifacts/halium-boot.img`.
- [x] Reempaquetar `super.img` con el `system.img` de Halium en vez del
      stock, manteniendo vendor/odm/product/system_ext intactos — en
      `firmware/super_halium_raw.img` (RAW, no sparse — ver más abajo por qué).
- [x] **Flashear ambos con éxito** — el primer intento (sparse) falló
      reproduciblemente; el segundo (RAW) subió sin errores. Ver detalle
      abajo.
- [x] **Arranca hasta la pantalla de warning de bootloader y se cuelga ahí**
      — no llega a mostrar nada del lado de Halium. Sin puerto serie no se
      puede diagnosticar más por ahora. Equipo restaurado a estado de
      fábrica limpio mientras se busca una forma de obtener logs.
- [ ] Reintentar el flasheo con el `super.img` corregido (ver pistas abajo).
- [ ] Resolver particularidades de partición de Samsung (AVB/vbmeta,
      `up_param`, posibles chequeos de Knox) que rompan el boot, si aparecen.

**Entorno de build — limitaciones reales de esta máquina (14GB RAM):**
- `soong_build` (la fase de análisis de dependencias, un solo proceso) llegó
  a usar **11.6GB de RAM por sí solo**. Con solo 4GB de swap, esto disparó
  el OOM killer del kernel **y** `systemd-oomd`, que mató la sesión de
  escritorio completa (no solo el build). Se resolvió agregando un swapfile
  extra de 24GB (`/swapfile_build`). Bajar `-j` no ayuda con esto porque es
  una fase de un solo proceso, no de paralelismo.
- El build también se quedó sin espacio en disco a mitad de camino (out/
  llegó a 40GB+ en un disco con poco margen libre). Se resolvió moviendo
  `out/` a un disco externo con más espacio
  (`/run/media/gael-schenone/Datos/halium-build/out`, symlinkeado de vuelta).
- **Nunca compartas tu contraseña de sudo con el asistente** — ante cualquier
  necesidad de sudo, usar el prefijo `!` para correr el comando vos mismo.

**Bugs reales encontrados y arreglados durante el sync/build (parches
guardados en `halium-patches/`, ver ahí cómo reaplicarlos tras un `repo
sync` limpio):**
1. **Manifest de Halium trae proyectos irrelevantes** que rompen el build si
   se excluyen "a ojo" sin entender las dependencias cruzadas de Soong
   (`packages/modules/Virtualization/microdroid` referencia kernels de
   dispositivo virtual y partes de Cuttlefish sin importar el dispositivo
   real). Terminamos syncando el manifest completo en vez de recortarlo —
   más pesado, pero confiable.
2. **`vendor/halium/libhybris` está pineado en `halium-11.0`** en el
   manifest, mientras el resto del árbol usa `halium-12.0` — no existe una
   rama `halium-12.0` para libhybris (Halium saltó de 11 a 13). Esto causa
   varios choques de API entre el código de compat (escrito contra
   frameworks/av de Android 11) y los headers/símbolos reales de Android 12:
   - `camera_service`: incluye un header movido
     (`media/camera_record_service.h`) → **deshabilitado completo** (no es
     necesario para bootear).
   - `libmedia_compat_layer`: dos headers movidos (`mediadrm/ICrypto.h`,
     `media/MediaMetrics.h`) se arreglaron agregando los `-I` correctos, pero
     después apareció una incompatibilidad de ABI de C++ real
     (`android::MediaCodecInfo` cambió de firma entre Android 11 y 12) →
     **deshabilitado completo** junto con sus dependientes
     (`direct_media_test`, `direct_camera_test`). Es la capa de códecs/
     grabación de video, no hace falta para bootear ni para el bridge básico
     de HALs.
   - `libcamera_compat_layer` (la librería de cámara en sí, distinta del
     `camera_service` de arriba) **no** depende de lo anterior y compiló
     bien tal cual.
3. **Prebuilt clang viejo (`clang-3289846`, usado para RenderScript, ya
   deprecado en Android) necesita `libncurses.so.5`/`libtinfo.so.5`**, que
   Ubuntu 26.04 ya no empaqueta. Se instalaron manualmente los `.deb` viejos
   de `security.ubuntu.com` a nivel sistema (necesario porque un binario
   compilado en el momento, `bcc_strip_attr`, también los necesitaba, y
   Soong ejecuta reglas con entorno limpio (`env -i`), así que
   `LD_LIBRARY_PATH` no alcanza — hace falta o instalar a nivel sistema o
   poner las libs en el `$ORIGIN/../lib64` del binario prebuilt específico).

**Armado de `halium-boot.img` y `super.img`:**

El target oficial `mka halium-boot` ([Halium/halium-boot](https://github.com/Halium/halium-boot),
agregado al árbol vía `.repo/local_manifests/device.xml`) espera
`TARGET_NO_KERNEL := false` con un kernel prebuilt integrado al build de
Android — más trabajo de integración del que vale la pena para lo que
necesitamos. En su lugar, reusamos el script de armado de boot.img de la
Fase 1 para combinar a mano:
- Nuestro kernel (recompilado — se había borrado su `out/` para liberar
  espacio antes del sync de Halium).
- El initramfs oficial de Halium
  ([initramfs-tools-halium releases](https://github.com/halium/initramfs-tools-halium/releases/tag/continuous),
  arm64).
- El mismo bloque de DTB (`DT_TABLE`) que extrajimos del `boot.img` stock en
  la Fase 1 (no cambia, es el mismo hardware).

**`/system` es una partición lógica (dynamic partitions), no física** —
`heimdall print-pit` solo muestra `super` como partición real. Hubo que:
1. Compilar `lpmake`/`lpunpack`/`lpdump` desde
   [LonelyFool/lpunpack_and_lpmake](https://github.com/LonelyFool/lpunpack_and_lpmake)
   (standalone, sin depender del árbol completo de AOSP) — necesitó un fix
   de una línea (`#include <algorithm>` faltante en `liblp/utility.cpp`,
   mismo tipo de problema que shockea código viejo contra libstdc++
   moderno).
2. Extraer `super.img.lz4` del firmware stock (**sí** está en el AP tar,
   ~4.2GB — hay que buscar el listado completo del tar, no asumir por un
   grep parcial).
3. `simg2img` (paquete `android-sdk-libsparse-utils`) para pasar de sparse a
   raw, `lpunpack` para separar `system`/`vendor`/`odm`/`product`/
   `system_ext`.
4. `lpmake` para reconstruir el `super.img` reemplazando solo `system` por
   el `system.img` de Halium (571MB, mucho más chico que el original de
   ~4GB — entra sin problema), manteniendo vendor/odm/product/system_ext
   **intactos** del stock.
5. `img2simg` para volver a sparse antes de flashear (el original venía en
   ese formato).

**Riesgo a tener en cuenta:** a diferencia de la Fase 1 (donde el
`boot.img` original quedó guardado y listo para reflashear al toque), acá
se borraron los intermedios del `super.img` original para hacer lugar en
disco. Si hace falta revertir, hay que re-extraer `super.img.lz4` del
`.zip` del firmware completo (que sí se conserva) — no es instantáneo,
pero es reproducible.

**Intento de flasheo fallido y recuperación (primer intento real, sin
éxito todavía):**

El flasheo de `super_halium_sparse.img` (3GB) con Heimdall falló de forma
consistente y **reproducible en el mismo punto** (~17-18% de la
transferencia), con `libusb error -7`, tanto en un solo archivo como
dividido en 6 chunks de ~500MB con `simg2simg`. El equipo terminó en un
estado `DOWNLOAD FAILED DETECTED: super` (recuperable, no es un brick) que
requirió reflashear `super` con éxito para salir.

**Pista clave para la próxima vez:** en la pantalla del equipo, la barra de
progreso de Odin/Download mode **nunca avanzaba** con nuestro
`super_halium_sparse.img`, pero sí avanzó con normalidad al reflashear el
`super.img` **original** de fábrica. Esto sugiere que el problema no era
solo inestabilidad de USB/Heimdall del lado de la PC, sino algo en cómo
`lpmake`/`img2simg` armaron nuestro archivo que hacía que el propio
bootloader del equipo se trabara procesándolo. Diferencia observada: nuestro
sparse reempaquetado quedó con **4760 chunks internos**, contra **168
chunks** en el sparse original de Samsung — probablemente porque los datos
de nuestro `system.img` (contenido totalmente distinto al original)
comprimen peor en el algoritmo de detección de bloques-cero de
`img2simg`. Antes de reintentar, vale la pena:
- Probar flashear el `super_halium.img` en **RAW** (sin convertir a sparse)
  en vez de sparse, ya que el problema puede estar específicamente en el
  formato sparse con muchos chunks, no en el tamaño del archivo.
- Si hay que usar sparse sí o sí, investigar si `lpmake`/`img2simg` tienen
  alguna opción para forzar chunks más grandes/menos numerosos.
- Considerar probar con **Odin real en Windows** en vez de Heimdall, ya que
  es la herramienta oficial y puede manejar mejor este caso.

**Recuperación realizada:** reflasheado `super.img` original de fábrica
(reconstruido desde el `.zip` del firmware) con éxito, después `boot.img`
original de fábrica también. Esto dejó el kernel stock corriendo de nuevo
contra un `/data` que había quedado formateado bajo nuestro kernel custom
de la Fase 1 (mismo problema de `CONFIG_F2FS_SEC_ENC_STRICT_MODE`, mirado
desde el otro lado) — resuelto con otro factory reset. El equipo quedó
100% en estado de fábrica limpio, listo para retomar el intento de Halium
en otra sesión.

**Segundo intento — confirma el fix del flasheo, pero el ramdisk de Halium
no completa el arranque:**

Se reempaquetó `super.img` con las mismas piezas pero **en RAW, sin
convertir a sparse**. Subió al 100% sin ningún error de `libusb`, en el
primer intento — **confirma que el problema real era el formato sparse
con demasiados chunks**, no el tamaño del archivo ni la conexión USB. Con
`super` (RAW) + `halium-boot.img` flasheados juntos:

- El equipo se queda trabado indefinidamente en la pantalla de warning de
  bootloader desbloqueado ("This phone is not running Samsung's official
  software..."), sin avanzar, sin exponer ninguna interfaz USB (ni `adb`
  ni download mode) mientras está en ese estado.
- No hay forma de distinguir, sin más información, entre "el ramdisk de
  Halium arrancó pero es headless y no dibuja nada en pantalla" y "el
  kernel/ramdisk colgó antes de hacer nada" — **sin puerto serie no hay
  logs**. Esto es exactamente el límite que ya anticipábamos en la sección
  de riesgos.
- Recuperado reflasheando `boot` + `super` originales de fábrica (sin
  necesitar otro factory reset esta vez).

**Para el próximo intento, en orden de lo más simple a lo más laborioso:**
1. Repetir el patrón "RAW, no sparse" también para el propio
   `halium-boot.img` si en algún momento se vuelve a generar con un tamaño
   grande o de forma reempaquetada (por ahora es chico y no tuvo este
   problema).
2. Buscar la forma de conseguir logs sin puerto serie físico: revisar si
   el conector USB-C del equipo soporta salida de video (algunos Samsung
   con DeX sí) para ver la consola del kernel por HDMI si `earlycon`/
   `console=` está en el cmdline; o revisar si hay pines de UART accesibles
   en la placa (mucho más invasivo, implica abrir el equipo).
3. Probar bootear el `halium-boot.img` de forma **temporal** (sin
   flashear) si Heimdall soporta algo equivalente a `fastboot boot` —
   revisar el flag `--resume`/comandos disponibles; esto evitaría el
   ciclo completo de flashear+recuperar en cada iteración de debug.
4. Revisar si el ramdisk de `initramfs-tools-halium` tiene algún modo de
   log persistente a partición (en vez de solo consola) que se pueda leer
   después reflasheando el kernel stock y montando esa partición vía adb.

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
