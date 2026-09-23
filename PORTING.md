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
- [x] Reintentar el flasheo con el `super.img` corregido (RAW) — confirmado
      que sube sin errores.
- [x] Equipo rooteado (Magisk) para poder leer `/sys/fs/pstore/` y hacer
      diagnóstico sin puerto serie.
- [ ] Conseguir un shell/log real del cuelgue de Halium — pstore resultó no
      viable (ver detalle abajo), debug telnet de `hybris-boot` encontrado
      pero con un bug de `telnetd` sin resolver todavía. Ver plan para la
      próxima sesión al final de esta fase.
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

**Tercer intento — rooteo del equipo + pstore/ramoops para diagnosticar el
cuelgue sin puerto serie:**

Dado que no hay puerto serie físico accesible, se armó una estrategia de
varios pasos para poder leer algo del kernel de Halium sin abrir el equipo:

1. **Rooteo con Magisk (v30.7)** para poder leer `/sys/fs/pstore/` (requiere
   root; usuario `shell`/`system` no tiene permisos). Se parcheó
   `boot_pstore_read2.img` (kernel bueno + ramdisk stock + cmdline con
   `ramoops.*` explícitos) con `boot_patch.sh` de Magisk **corrido a mano
   por `adb shell`**, no con la app.
   - **Primer intento de parcheo (flags por default) causó bootloop**: el
     patch por default de Magisk modifica el fstab (saca las opciones
     `avb=...` y `fileencryption=...,keydirectory=...`), lo cual rompe el
     mount de `/data` en este equipo. Recuperado reflasheando el boot.img
     bueno conocido.
   - **Segundo intento con `KEEPFORCEENCRYPT=true KEEPVERITY=true`
     bootea sin problema** y da root funcional (`su -v` → `30.7:MAGISKSU`).
     Guardado como `firmware/boot_rooted2.img`, es el boot.img "seguro" de
     referencia para volver a Android normal desde ahora en adelante.
2. **Habilitado `CONFIG_VT`/`CONFIG_FRAMEBUFFER_CONSOLE` en el kernel** para
   intentar ver texto de consola en pantalla — **descartado como camino
   muerto**: `CONFIG_DRM_MEDIATEK` **no** está habilitado en este kernel, es
   decir Android en este equipo no usa el framebuffer/DRM estándar del
   kernel para la pantalla (usa un driver propietario de MediaTek a nivel
   HAL). Sin un driver DRM real detrás, fbcon no tiene nada que dibujar —
   pantalla negra sí o sí, sin importar qué tan bien configurado esté fbcon.
3. **Procedimiento de captura vía pstore**: flashear
   `halium-boot-ramoops.img` (kernel bueno + ramdisk **original** de Halium,
   sin modificar + cmdline con
   `ramoops.mem_address=0x47c90000 ramoops.mem_size=0xe0000
   ramoops.pmsg_size=0x10000 ramoops.console_size=0x40000 console=tty0` —
   estos valores salen de `/cache/recovery/last_kernel`, el log del propio
   bootloader/LK de Samsung, que ya reserva esa región de RAM para ramoops
   de fábrica) + `super_halium_raw.img`; dejar colgar ~90s; reset forzado
   **sin cortar batería** (para no perder la retención de la RAM reservada);
   reflashear `boot_rooted2.img` + `super_stock.img`; leer
   `/sys/fs/pstore/console-ramoops-0` con `adb shell su -c cat ...`
   inmediatamente, sin ningún boot de por medio.
   - **Primer intento**: pstore vino completamente vacío. Ningún archivo en
     `/sys/fs/pstore/`. Probable pérdida total de retención de RAM durante
     ese reset puntual (variabilidad de hardware/eléctrica, no algo que se
     pueda controlar desde software).
   - **Error propio a evitar**: flashear `--boot` y `--super` en comandos
     separados de Heimdall es un error — Heimdall **reinicia el equipo
     automáticamente** apenas termina de subir la partición, así que un
     `--boot` solo deja al equipo booteando de inmediato con una
     combinación cruzada (kernel nuevo + partición vieja) antes de poder
     flashear la otra mitad. **Siempre flashear `--boot` y `--super` juntos
     en el mismo comando** cuando se necesita que ambos cambien atómicamente
     antes del próximo boot.
   - **Segundo intento (con el fix de arriba)**: pstore sí trajo contenido
     (con corrupción de bits — bit-flips típicos de una región de RAM con
     retención parcial durante el reset), pero resultó ser un **hallazgo
     falso positivo**: un panic real, `kernel BUG at
     drivers/samsung/sec_hard_reset_hook.c:134`, con call trace mostrando
     que se disparó desde un `hrtimer` (`hard_reset_hook_callback`), **no**
     desde el cuelgue de Halium. Revisando el código fuente
     (`drivers/samsung/sec_hard_reset_hook.c`), es el propio mecanismo de
     Samsung para la combinación de teclas Power+VolDown mantenida 6+
     segundos: arma un timer, y si las teclas siguen apretadas al vencer,
     dispara un `BUG()` **a propósito** para forzar un reset duro (comentario
     en el código: "HQE team request hard reset key should guarantee 7
     seconds"). Es decir, **el propio combo de reset forzado que usamos para
     sacar al equipo del cuelgue se autodestruye y pisa el log real de
     Halium con su propio panic dump** (call trace + tabla completa de
     threads del kernel, bastante grande) en el buffer circular de pstore
     (256KB). **Conclusión: pstore no es viable para este diagnóstico
     mientras la única forma de salir del cuelgue sea ese combo de teclas.**
4. **Hallazgo del debug telnet de `hybris-boot`** (documentado en
   [docs.halium.org](https://docs.halium.org/en/latest/porting/debug-build/early-init.html)):
   cuando el sistema Halium falla al bootear, `initramfs-tools-halium`
   levanta automáticamente una interfaz de red USB (RNDIS) en
   `192.168.2.15` con un `telnetd` en el puerto 23 — **sin necesitar pstore
   ni resets**. Confirmado que esto sí ocurre en nuestro equipo: aparece en
   el host como un dispositivo USB separado (`18d1:d001`, fabricante
   "Halium initrd", producto "Failed to boot") y el string `iSerial` del
   descriptor USB literalmente dice
   `"Halium initrd Debug telnet on port 23 on rndis0 192.168.2.15 - also
   running udhcpd"` (visible con `dmesg`/`journalctl -k` del lado del host
   sin necesitar red configurada). El host recibe IP por DHCP del propio
   equipo (udhcpd corriendo del lado de Halium).
   - **Problema encontrado**: conectar por telnet (`telnet 192.168.2.15`,
     o un socket crudo con negociación IAC) resulta en conexión aceptada
     pero cerrada instantáneamente (0 bytes, EOF inmediato) — el shell
     interactivo nunca se llega a usar. Revisando
     `scripts/panic/telnet` dentro del propio initramfs de Halium (extraído
     de `halium-boot-artifacts/halium-initramfs.gz`), la línea responsable
     es `busybox telnetd -b $IP:$PORT -l /bin/sh` (BusyBox v1.22.1, del
     2013). Se descartó que sea un binario faltante (`/bin/sh` existe y es
     válido, hardlinkeado a `busybox`) o falta de `/dev/pts` (el `init` del
     ramdisk sí lo monta bien antes del punto donde correría este script).
     Causa más probable: un bug de auto-demonización de esa versión vieja de
     BusyBock en un entorno initramfs mínimo.
   - **Intento de fix**: cambiar la invocación a
     `telnetd -F -b $IP:$PORT -l /bin/sh &` (foreground explícito +
     backgrounding manual por el shell, evitando la lógica interna de
     daemonización de BusyBox) — **todavía sin confirmar si funciona**, un
     primer intento con 6 llamadas adicionales a `usb_info()` (cada una
     fuerza una re-enumeración del gadget USB al reescribir el string
     `iSerial`) desestabilizó el controlador USB del host ("Cannot enable,
     Maybe the USB cable is bad?", ciclos de disconnect/reconnect) y el
     equipo terminó reiniciándose solo. Se corrigió consolidando el
     diagnóstico extra en **una sola** llamada a `usb_info()`, pero el
     intento siguiente no volvió a mostrar la interfaz de debug dentro de
     varios minutos (vs. los ~90s habituales) — no está claro todavía si es
     por la propia fragilidad del puerto USB (ya venía dando errores) o por
     algo introducido en el script. **No confirmado, pendiente para la
     próxima sesión.**
   - **`nc` (netcat) no está compilado en este BusyBox** (`strings` sobre el
     binario no encuentra el applet), así que un enfoque alternativo sin pty
     (`nc -l -p PORT -e /bin/sh`) no es viable acá.
   - Ramdisk parcheado y boot.img resultantes en
     `halium-boot-artifacts/halium-boot-ramoops3.img` (kernel bueno +
     ramdisk con el fix de telnetd + mismo cmdline de ramoops). El ramdisk
     original sin modificar sigue en
     `halium-boot-artifacts/halium-initramfs.gz` por si hace falta
     comparar.

**Plan para la próxima sesión, en orden de preferencia:**
1. Confirmar si el fix de `telnetd -F ... &` funciona dándole más intentos
   con paciencia (o reintentando en un puerto/cable USB distinto, dado que
   esta sesión mostró señales de que el puerto/cable actual está marginal).
2. Si telnetd sigue fallando, compilar `hybris-recovery.img` (`mka
   hybris-recovery` dentro del árbol de Halium ya sincronizado) — una
   imagen de arranque separada, pensada específicamente como entorno de
   rescate/debug con un shell ya andando, en vez de depender del gancho de
   pánico del ramdisk normal (que es donde está el bug de telnetd).
3. Como alternativa más agresiva, agregar el `USB_FUNCTIONS="rndis
   mass_storage"` al mismo script de debug, respaldado por un archivo crudo
   con el diagnóstico volcado como texto plano — el host lo leería con
   `dd`/`strings` directo del dispositivo de bloque expuesto, sin depender
   de red ni de pty en absoluto. No implementado todavía, pendiente
   confirmar que el kernel tenga habilitado el gadget de mass storage por
   configfs.

**Cuarto intento — build de `hybris-recovery.img` en una segunda PC (evita el
crash por RAM):**

Al intentar el fix de telnetd de nuevo, `soong_build` volvió a comerse toda
la RAM de esta máquina y **crasheó la sesión de escritorio** — el mismo
problema de la Fase 2, porque el swapfile extra de 24GB que habíamos armado
antes existía en disco (`/swapfile_build`) pero **no estaba activado**
(`swapon` no persiste solo entre reinicios sin una entrada en `/etc/fstab`).
Recuperado sin pérdida de datos (el repo git y el árbol de Halium en el
disco externo quedaron intactos).

En vez de seguir peleando con los límites de RAM de esta máquina, se migró
todo el trabajo de Halium a una segunda PC en la misma red local (16GB RAM,
aunque con un HDD mecánico en vez de SSD) vía SSH/rsync:
- Se generó una clave SSH dedicada y se copió con `ssh-copy-id` para no
  tener que compartir contraseñas en ningún momento (las credenciales de
  sudo/SSH son responsabilidad exclusiva de quien las administra — nunca se
  las debe pedir ni procesar).
- Se copió el árbol completo de Halium (~89GB, sin `out/`) y por separado el
  `out/` del build anterior (~55GB, ya reducido de los ~224GB originales
  tras limpiezas de disco entre sesiones) por `rsync` sobre la LAN — mucho
  más rápido que un `repo sync` nuevo desde cero, y preserva los patches ya
  aplicados (`halium-patches/`).
- Verificado que los tamaños coincidieran exactamente entre origen y
  destino antes de borrar las copias locales (89GB + 55GB liberados en esta
  máquina).
- Armado un symlink `halium/out -> halium-build-out` en la máquina remota
  para reconstituir la misma estructura.

**Hallazgo real, no relacionado con la migración:** el primer intento de
`mka hybris-recovery` en la máquina nueva falló con ~995 errores, todos del
mismo patrón: `module source path "prebuilts/vndk/vXX/arm64/include/out/
soong/.intermediates/.../gen" does not exist`, en los snapshots VNDK v30 y
v31. La causa es que los `Android.bp` de esos snapshots VNDK referencian
rutas relativas tipo `"include/out/soong/.intermediates/..."`, que esperan
un symlink llamado `out` dentro de `prebuilts/vndk/vXX/<arch>/include/`
apuntando al `out/` real del árbol — **symlink que nunca existió ni en la
máquina original ni en la copia** (no es un artefacto de la migración por
rsync, es un gap real de este checkout de Halium que simplemente nunca se
había ejercitado porque el build de `system.img` no toca estos módulos VNDK
puntuales). Confirmado que el contenido generado que faltaba sí existe
dentro de `out/` (ya se había generado durante el build de `system.img`).

**Resolución completa del problema de VNDK (varias vueltas hasta cerrarlo
del todo):**

1. **Symlinks `include/out`**: crear el symlink a mano para cada
   arquitectura de v28-v31:
   ```sh
   for v in v30 v31; do
     for arch in arm64 arm x86_64 x86; do
       d="<ruta al árbol de halium>/prebuilts/vndk/$v/$arch/include"
       [ -d "$d" ] && [ ! -e "$d/out" ] && ln -s <ruta al árbol de halium>/out "$d/out"
     done
   done
   ```
   Esto redujo los errores de 995 a 7 — confirma que el symlink resuelve la
   mayoría de los casos, pero **7 rutas puntuales de `libbinder`/`libgui`/
   `libhidlallocatorutils` (variantes vendor de v31) no existían realmente
   dentro de `out/`**, porque nuestro build anterior de `system.img` nunca
   había compilado esas variantes vendor-side específicas.

2. **Intentar compilar esas 3 libs directamente (`mka libbinder libgui
   libhidlallocatorutils`) empeoró las cosas**: Soong evalúa **todo** el
   árbol de módulos antes de compilar cualquier cosa (no solo lo pedido), y
   esto hizo que se evaluara también el snapshot VNDK v30 completo, sacando
   a la luz decenas de rutas faltantes nuevas (wifi, radio, keymaster, cas,
   soundtrigger, automotive, etc. — básicamente toda la superficie HIDL/AIDL
   de `hardware/interfaces/`). **Lección clave: Soong analiza el grafo de
   módulos completo en cada invocación de `mka`, sin importar qué target se
   pida — un error de "path no existe" en CUALQUIER módulo del árbol bloquea
   la generación de `build.ninja` para TODO, incluso targets no
   relacionados.**

3. **v30 resultó no ser necesario en absoluto**: revisando
   `out/soong/soong.variables` generado, `ExtraVndkVersions = ['31']` — solo
   v31 hace falta para este producto. Intentar simplemente *renombrar* la
   carpeta `prebuilts/vndk/v30` no sirvió (Soong globa cualquier archivo
   literalmente llamado `Android.bp` en cualquier subdirectorio, sin
   importar el nombre de la carpeta padre) — hubo que **moverla fuera del
   árbol de Halium por completo** (`mv prebuilts/vndk/v30 /otro/lugar`).
   Esto reveló un segundo problema: `packages/modules/vndk/apex/Android.bp`
   (código genérico de la plataforma, no específico de Halium) define un
   módulo `apex_vndk` por cada versión (v28 a v31) con bloques hardcodeados,
   y esos bloques referencian por nombre módulos generados dentro de la
   propia carpeta `prebuilts/vndk/vXX/` (como `llndk.libraries.30.txt`) — si
   la carpeta desaparece pero el bloque `apex_vndk` sigue ahí, falla por
   "depends on undefined module" en vez de "path no existe". **Fix real**:
   truncar ese archivo (`packages/modules/vndk/apex/Android.bp`, se guardó
   backup como `Android.bp.orig`) dejando solo los bloques `current` y
   `v31`, y mover **v28, v29 y v30** fuera del árbol (`prebuilts/vndk/` solo
   con `v31` adentro).
4. Con eso, los errores bajaron a un puñado de rutas puntuales de v31
   (arquitectura `arm` de 32 bits además de `arm64`, y un par de libs
   nuevas: `libc`, `libmedia_omx`). Se resolvieron creando manualmente los
   directorios placeholder faltantes (vacíos, `mkdir -p`) bajo `out/`, ya
   que **Soong solo valida que el directorio exista, no su contenido, en
   esta fase de análisis** — el análisis completo (240/240 makefiles, Kati
   + Soong) terminó sin errores por primera vez.

**Resultado final de la sesión — `hybris-recovery` no es un target válido en
este checkout:** una vez pasado el análisis, `ninja` devolvió
`unknown target 'hybris-recovery'` — ese nombre de target simplemente no
está definido en ningún Makefile/Android.bp sincronizado. Se investigó:
- El manifest de Halium trae `bootable/recovery` = **LineageOS/
  android_bootable_recovery** (el recovery stock de LineageOS), no un fork
  de Halium. Se encontró y clonó a mano el fork correcto,
  [`ubports/halium_bootable_recovery`](https://github.com/ubports/halium_bootable_recovery)
  (rama `halium-12.0`, coincide exactamente con nuestra versión) — el
  `repo sync` con `remove-project` para reemplazarlo dentro del manifest
  dio error (`remove-project element specifies non-existent project`, sin
  resolver por qué); se resolvió clonándolo directo con `git clone` sobre
  `bootable/recovery`, sin pasar por `repo`.
- Ni ese repo ni `bootable/halium-boot` (que sí define el target
  `halium-boot`) definen `hybris-recovery` en ningún Makefile/Android.bp.
- Revisando la doc oficial (`docs.halium.org/.../early-init.rst`, fuente
  cruda en GitHub) que documenta este flujo, el texto menciona
  `lxc@android` y `systemctl` dentro de un `chroot target/` — es decir,
  describe la arquitectura **vieja** de Halium (9-11, basada en contenedor
  LXC para el rootfs), no la de Halium 12. Es muy probable que
  `hybris-recovery` haya sido **eliminado o rearmado de otra forma** al
  modernizar la arquitectura, y que la doc esté desactualizada para esta
  versión. Se rastreó el repo `Halium/hybris-patches` (parches que se
  aplican sobre el árbol synced, vía `apply-patches.sh`, nunca aplicados en
  este checkout) buscando si algún parche agregaba el target — no se
  encontró nada relacionado. **Conclusión: no resuelto, y probablemente no
  vale la pena seguir insistiendo con este camino puntual** salvo que
  aparezca un dato nuevo (foro/Matrix de Halium).

**Hallazgo importante sobre el fix de `telnetd` (invalida parte de lo que
se pensaba antes):** usando `qemu-user` (`qemu-aarch64-static`, binario
portátil bajado sin necesitar `sudo`/instalación de paquetes) se pudo correr
el `busybox` ARM64 real del ramdisk de Halium **en esta PC, sin el celular
para nada**, y probar `telnetd -F -b 127.0.0.1:PUERTO -l /bin/sh` en
aislamiento. **Funcionó perfecto**: conexión aceptada, shell interactivo
real, `ls` devolvió el listado correcto del ramdisk. Esto **descarta que el
binario de `telnetd` esté roto** — la teoría de "bug de BusyBox 1.22.1" de
la Fase 2 anterior era probablemente incorrecta. El fallo real en el
dispositivo es más probablemente la inestabilidad del puerto/cable USB que
veníamos sufriendo (mensajes "Cannot enable, Maybe the USB cable is bad?"),
no un problema del software del ramdisk. Intentar reproducir la condición
exacta del dispositivo (mount fresco de `/dev/pts` en un namespace privado,
en vez del `/dev/pts` ya configurado del host) quedó bloqueado por
`apparmor_restrict_unprivileged_userns=1` en esta PC (Ubuntu 26.04) — se
necesitaría `sudo` para deshabilitarlo temporalmente o probar directo en el
celular.

**RESUELTO — shell de debug real conseguido (el objetivo de toda esta
investigación):**

Con el cable USB cambiado (para descartar variables), se retomó el intento
de arreglar `telnetd`, y esta vez se aisló bien la causa real en varios
pasos:

1. **Bug real y grande encontrado, no relacionado con el script**: todos los
   intentos anteriores de esta sesión que "no mostraban nada en absoluto"
   (ni siquiera el banner USB inicial) resultaron tener la MISMA causa: el
   proceso de reempaquetado del ramdisk (`find . | cpio -o -H newc | gzip`)
   corrido como usuario normal graba los archivos con el **UID/GID del
   usuario actual** en vez de `root:root` (el `cpio` original del ramdisk
   de Halium sí los tiene como `root:root`). El kernel, al desempaquetar un
   initramfs, respeta literalmente esos UID/GID — un ramdisk entero
   "poseído" por un usuario no-root en vez de root rompe el arranque
   temprano por completo. **Fix**: usar `fakeroot` al reempaquetar
   (`fakeroot bash -c 'chown -R root:root . && find . | cpio -o -H newc |
   gzip -9 > ...'`), sin necesitar `sudo` real. Confirmado con una prueba de
   control: reempaquetar el script ORIGINAL sin ningún cambio de contenido,
   con este bug de ownership, también fallaba en cero; con `fakeroot`
   corregido, funcionó igual que el original sin tocar. **Este es un
   hallazgo reutilizable para cualquier ramdisk que se reempaquete de acá en
   adelante.**
2. Con el ownership arreglado, `telnetd -F ... &` seguía sin dar shell
   (conectaba y se quedaba mudo, o directamente rechazaba la conexión según
   el intento) — se agregó una línea extra de diagnóstico vía el string
   `iSerial` del USB (el mismo canal confiable de siempre) chequeando si
   `/dev/ptmx` existía. **Resultado: `/dev/ptmx` no existe en este
   ramdisk**, aunque `/dev/pts/ptmx` (el multiplexor interno de devpts) sí.
   Sin `/dev/ptmx`, ningún programa (telnetd incluido) puede abrir una
   pseudo-terminal nueva — exactamente la causa de que la conexión se
   aceptara pero nunca diera un shell utilizable, durante *todas* las
   sesiones anteriores con el ramdisk original también.
3. **Fix**: agregar `[ -e /dev/ptmx ] || ln -s pts/ptmx /dev/ptmx` en
   `scripts/panic/telnet`, antes de arrancar `telnetd`. **Con esto,
   `telnetd` dio un shell real y funcional por primera vez en toda la
   investigación** (`BusyBox v1.22.1 ... / #`, con negociación de protocolo
   telnet correcta, comandos ejecutándose de verdad).

**Diagnóstico obtenido del shell real (el objetivo original de Fase 2):**
`/proc/mounts` durante el cuelgue muestra únicamente `rootfs`, `sysfs`,
`proc`, `devpts`, `tmpfs` (`/run`) y `configfs` — **ninguna partición real
(`/system`, `/vendor`, `/data`, etc.) llega a montarse nunca**. `ps -ef`
solo muestra `/init` (PID 1, bloqueado en el `inject_loop` de nuestro
propio script de debug, como se espera) y threads del kernel (`kthreadd`,
`rcu_*`, `kworker/*`, `migration/*`, etc.) — ningún proceso de userspace
adicional llegó a arrancar. **Conclusión: el cuelgue de Halium pasa antes
de que `mountroot` intente siquiera montar las particiones lógicas del
`super`** — no es un problema de HALs, de sistema de archivos corrupto, ni
de algo tardío en el arranque; es un problema muy temprano en el script de
montaje (`scripts/local` / lo que sea que decida cómo montar `/system` para
este dispositivo).

**Limitación encontrada**: cada conexión nueva a `telnetd -F` solo permite
una interacción/comando útil antes de cortarse (no parece depender del
tamaño de la salida — hasta `cat /proc/cmdline`, una sola línea, se cortó a
mitad de camino en un intento) — hay que reconectar entre cada comando.
Suficiente para diagnóstico dirigido, molesto para una sesión exploratoria
larga.

**Investigación en vivo del mount de `/system`/`/vendor` (misma sesión,
usando ya el shell de debug funcional):**

Usando `halium-boot-ptmxfix.img`, con un comando por conexión (reflasheando
entre cada uno para minimizar la degradación de la sesión — ver
"Limitación encontrada" abajo), se fue acotando el problema:

- **`/dev/block` no existe en absoluto** en el momento del cuelgue — ningún
  nodo de dispositivo de bloque, ni siquiera vacío.
- **`/proc/devices` sí lista `179 mmc`** en la sección de "Block devices" —
  el subsistema/driver de bloque de MMC **sí se registró** en el kernel, no
  es un problema de driver faltante o mal compilado.
- **`/sys/class/mmc_host/` tiene `mmc0` y `mmc1`** — dos controladores host
  MMC/eMMC se inicializaron correctamente (probablemente eMMC interno +
  WiFi por SDIO, u otra combinación; no confirmado cuál es cuál).
- **`/sys/class/mmc_host/mmc0` tiene un hijo `mmc0:0001`** — es decir, **se
  detectó una tarjeta/dispositivo real conectado a `mmc0`** (respondió al
  protocolo MMC, se le asignó un RCA). Confirmado con el usuario que este
  equipo **no tiene bandeja de microSD física** ni tarjeta insertada, así
  que `mmc0` casi seguro es el eMMC interno real (no un lector de SD vacío
  que por alguna razón mostrara un dispositivo).
- Pendiente confirmar (no se llegó a leer antes de que la conexión se
  cortara): si `mmc0:0001` tiene una subcarpeta `block/` (que confirmaría
  que el driver `mmc_block` sí se enganchó al dispositivo mmc, y el
  problema sería solo la falta del nodo en `/dev`, no del bind del driver),
  o si directamente no la tiene (confirmando que `mmc_block` nunca llegó a
  bindearse a esta tarjeta en particular pese a que el protocolo MMC
  funcionó).

**Conclusión más probable a esta altura**: el hardware/protocolo MMC
funciona (el eMMC responde y se enumera), pero **el driver de bloque nunca
crea el nodo `/dev/mmcblk0`** — el problema está en algún punto entre la
detección de la tarjeta y el bind del driver `mmc_block`, no en el
controlador MMC en sí ni en el propio script de montaje de Halium (que ni
siquiera llega a intentar nada, porque nunca hay una partición para montar
en primer lugar).

**Limitación encontrada**: cada conexión nueva a `telnetd -F` solo permite
una interacción/comando útil antes de cortarse, y esto **empeora
notablemente con conexiones sucesivas dentro del mismo boot** (la primera
conexión después de un flasheo fresco suele funcionar bien — a veces con
una respuesta completa larga —, la segunda ya viene truncada, la tercera
casi no responde nada). Reflashear entre cada comando puntual da resultados
mucho más confiables que reutilizar la misma sesión de boot para varias
preguntas seguidas. No se investigó la causa raíz de este límite (podría
ser un problema de recursos del propio `telnetd -F`/pty, o alguna
degradación más general del sistema mientras el kernel sigue reintentando
algo en background relacionado al propio problema de storage).

**Quinto intento — canal de debug por HTTP/CGI (`debug-initramfs/`), y el
hallazgo real detrás de la fragilidad de `telnetd`:**

Dado que `telnetd` seguía siendo inservible para investigar (cada sesión se
cortaba a mitad del eco del comando, y empeoraba con cada conexión nueva en
el mismo boot — ver más arriba), se armó un tooling versionado en
`debug-initramfs/` (`panic-telnet`, `make_halium_boot.py`, `build.sh`,
cliente `hdbg`) para dejar de depender del scratchpad (que se borra entre
sesiones) y de un shell interactivo por pty.

**Diagnóstico del problema real de `telnetd`:** se probó servir el mismo
diagnóstico por HTTP (`busybox httpd` con CGI) en vez de por telnet, para
sacar la complicación de pty/negociación telnet/line-editing de en medio.
Resultado clave:
- Una respuesta **generada directamente por el proceso principal de
  `httpd`** (un 404 hardcodeado, sin leer ningún archivo) llega **perfecta
  e instantánea**, con headers y cuerpo completos.
- Servir el **contenido real de un archivo** (`diag.txt`, e incluso un
  archivo trivial de 28 bytes creado con un simple `echo > archivo`) se
  cuelga siempre: los headers HTTP llegan bien (`Content-Length` correcto,
  confirmado por un test de socket crudo), pero **cero bytes del cuerpo
  llegan nunca**, sin importar cuánto se espere.
- Lo mismo pasa con el CGI (ejecutar un comando y devolver su salida): se
  cuelga igual, a veces incluso antes de completar los propios headers.

**Conclusión: no es un problema de red/MTU** (se probó bajar el MTU de la
interfaz RNDIS del lado del host, sin efecto) **ni del protocolo** (HTTP no
tiene pty ni negociación telnet, y falla igual). El patrón real es:
*cualquier respuesta que dependa de un proceso hijo (`fork()`) leyendo o
escribiendo a través del socket de red heredado se cuelga*, mientras que
todo lo que el proceso **padre** hace directamente (el 404 de `httpd`, el
string `iSerial` del descriptor USB que usamos toda la noche) funciona
siempre. Esto es coherente con **todo** lo raro que vimos con `telnetd`
desde el principio: acepta la conexión (el padre lo hace bien), pero nunca
logra que el hijo forkeado (el shell interactivo) realmente hable a través
del socket.

**Intento de solucionarlo con mass storage (evita fork por completo, ya que
el kernel sirve el bloque directo sin proceso de usuario):** se corrigió un
bug real en el intento anterior de esta noche (`USB_FUNCTIONS` con espacio
en vez de coma — el camino `android_usb` de este equipo espera una lista
separada por comas, `"rndis,mass_storage"`, no por espacios) y se agregó el
LUN backing file (`/tmp/diag.img`) tanto para el camino `configfs` como
`android_usb`. Aun así, **la función mass_storage nunca se activó** (`lsusb
-v` solo muestra las 2 interfaces de RNDIS, ninguna de mass storage). Al
agregar un diagnóstico extra por `iSerial` para ver por qué (¿existe
`f_mass_storage`? ¿qué dice `.../functions`?), **el propio script de init
se quedó colgado leyendo alguno de esos atributos de sysfs** — el mismo
patrón exacto que ya habíamos visto con `/sys/class/mmc_host/mmc0/
mmc0:0001` en el intento anterior.

**Esto es el hallazgo más importante de la noche:** parece haber **lecturas
de atributos sysfs que cuelgan indefinidamente (estado D, ininterrumpible)
en este kernel/hardware**, y no está acotado a un solo subsistema (ya lo
vimos con MMC, y ahora con algo del lado de `android_usb`/`f_mass_storage`).
Dado que el propio `/init` (PID 1) es el que se cuelga leyendo esto, **es
muy probable que esta sea la causa raíz real de por qué Halium nunca monta
`/system`/`/vendor`** — no necesariamente porque el driver de storage nunca
termine de detectar la tarjeta, sino porque el script que decide cómo
montar las particiones lógicas del `super` intenta leer algún atributo de
sysfs (posiblemente relacionado a MMC/dynamic-partitions) que se cuelga de
la misma manera, y todo el arranque queda esperando ahí para siempre.

**Para la próxima sesión:**
1. Revisar el código fuente del kernel (`kernel/drivers/mmc/` y
   `kernel/drivers/usb/gadget/` o donde viva `f_mass_storage`/`android_usb`
   en este árbol) buscando `.show()`/attribute callbacks que puedan quedar
   esperando un mutex/completion que nunca se libera — es un bug de kernel
   real, no algo arreglable solo desde el ramdisk.
2. Confirmar la hipótesis de forma más controlada: usar el canal `iSerial`
   (el único 100% confiable) para reportar, **uno por uno y con mucho
   cuidado de no encadenar más de un `usb_info()` de diagnóstico por
   boot** (encadenar varios provoca re-enumeraciones USB que desestabilizan
   la sesión, ya visto antes), exactamente cuál lectura específica es la
   que cuelga — separar bien `f_mass_storage/lun/file` de
   `$ANDROID_USB/functions` de `$ANDROID_USB/enable` en intentos
   independientes.
3. Si se confirma que es un bug de kernel en una ruta de código que el
   propio `mountroot` de Halium también dispara, la solución probablemente
   pase por parchear ese driver/atributo específico (evitar el `.show()`
   problemático, o bindear el atributo de otra forma) en vez de seguir
   iterando desde el ramdisk.
4. El tooling en `debug-initramfs/` (script de pánico parcheado,
   `make_halium_boot.py`, `build.sh`, cliente `hdbg`) queda versionado y
   listo para seguir iterando sin depender del scratchpad. El canal HTTP
   quedó armado pero **no es fiable para contenido real** por el mismo bug
   de fork — solo sirve para respuestas chicas hardcodeadas, así que en la
   práctica seguimos dependiendo del canal `iSerial` (una línea, un dato
   por vez) hasta resolver el bug de fondo.
5. El fix de VNDK (symlinks + truncar `packages/modules/vndk/apex/
   Android.bp` a solo `current`+`v31` + mover v28/v29/v30 fuera del árbol +
   placeholders puntuales bajo `out/`) sigue siendo reutilizable si se
   retoma `hybris-recovery` más adelante.
6. El local_manifest quedó con un `<remove-project>` que rompe `repo sync`
   sin argumentos (tira el mismo error de "non-existent project") — si se
   necesita volver a correr `repo sync` completo en esa PC, revisar/sacar
   esa línea de `.repo/local_manifests/device.xml` primero.

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
