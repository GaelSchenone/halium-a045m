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
- No hay ningún port de postmarketOS/mainline para el A04/M04 (MT6765).
  Este va a ser trabajo nuevo para el modelo puntual.

## Roadmap

### Fase 0 — Entorno de build
- [ ] Instalar toolchain aarch64 (`aarch64-linux-gnu-gcc` o clang, según
      `kernel/build.config.mtk.aarch64`).
- [ ] Instalar herramienta `repo` de Halium/AOSP.
- [ ] Bajar firmware stock completo del CSC exacto del equipo (para poder
      volver atrás con Odin ante cualquier bootloop).
- [ ] Confirmar espacio en disco: el árbol completo de Halium/AOSP puede pesar
      100GB+; el kernel solo son ~650MB.

### Fase 1 — Kernel propio, boot sanity check
- [ ] Compilar `kernel/` tal cual, sin modificar nada.
- [ ] Empaquetar boot.img con el ramdisk **stock** (extraído del firmware
      original) + el kernel recién compilado.
- [ ] Flashear por Odin/heimdall y confirmar que bootea Android normal.
      Esto valida el toolchain y la firma/formato de imagen antes de tocar
      nada del lado de Linux.

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
