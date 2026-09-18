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
