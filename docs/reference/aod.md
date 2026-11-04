# Always-On Display

Init forces `persist.sys.overlay.aod=true`; setup enables
`me.phh.treble.overlay.misc.aod_systemui`, then defaults `doze_always_on=1`
once. Subsequent user changes to Always-On Display are respected.

`hibreak-aod.sh` follows `debug.tracing.screen_state`: 3/4 are doze states,
2 is on. It turns Android accessibility color inversion on during doze, then
off on wake, using `persist.sys.hibreak.aod_inverted` to identify inversion it
owns. It leaves pre-existing user-enabled inversion alone and cleans up a
stale owned inversion marker during boot setup. This is a workaround through
global color inversion, not a new native AOD renderer.

**EInk Service Settings > Invert colours on Always-On Display** defaults on.
The app sends `aoi1`/`aoi0` to the root daemon, setting
`persist.sys.hibreak.aod_invert=true/false`. The daemon accepts only 0 or 1.
The preference is resent when the service connects. The next doze entry
applies the choice; normal wake removes any script-owned inversion.

The observed no-button reboot reached doze, enabled inversion, then removed
it after an ADB wake. Host build checks and app command tests cannot guarantee
the visual result for every theme, animation setting or third-party AOD.
The consolidated script exits nonzero and logs failed operations rather than
always returning success.
