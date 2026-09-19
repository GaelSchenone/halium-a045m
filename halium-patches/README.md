# halium-patches

El árbol de Halium (`./halium`, ~88GB, 1159 proyectos vía `repo`) no se versiona
en este repositorio — es demasiado grande y es reproducible desde
`vendor/halium/manifest` (Halium/android, rama `halium-12.0`). Estos parches
documentan los cambios que hicimos ahí, para poder reaplicarlos si algún día
hay que rehacer el `repo sync` desde cero.

## libhybris-android12-compat-fixes.patch

Corrige/deshabilita partes de `vendor/halium/libhybris` que no compilan contra
Android 12 porque ese proyecto está pineado en `halium-11.0` (no existe una
rama `halium-12.0` de libhybris). Ver `PORTING.md`, sección Fase 2, para el
detalle de cada cambio.

Para reaplicar tras un sync limpio:

```sh
cd halium/vendor/halium/libhybris
git apply /ruta/a/halium-patches/libhybris-android12-compat-fixes.patch
```

## lpunpack_and_lpmake-libstdcxx-fix.patch

Fix de una línea (`#include <algorithm>` faltante en `liblp/utility.cpp`)
para poder compilar [LonelyFool/lpunpack_and_lpmake](https://github.com/LonelyFool/lpunpack_and_lpmake)
con un `clang`/libstdc++ moderno (el código original asumía que `<algorithm>`
se incluía transitivamente, cosa que las versiones nuevas de libstdc++ ya no
hacen). Necesario para armar `lpmake`/`lpunpack`/`lpdump` — herramientas para
manipular `super.img` (dynamic partitions), que no vienen empaquetadas en
Ubuntu ni conviene compilar desde el árbol completo de AOSP solo para esto.

```sh
git clone https://github.com/LonelyFool/lpunpack_and_lpmake.git
cd lpunpack_and_lpmake
git apply /ruta/a/halium-patches/lpunpack_and_lpmake-libstdcxx-fix.patch
bash make.sh   # requiere clang/clang++ instalados
# binarios en bin/: lpmake, lpunpack, lpdump, lpflash, lpadd
```
