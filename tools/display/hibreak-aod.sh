#!/system/bin/sh
# Invert colours while dozing so the e-ink AOD is black-on-white, not a black panel.
# The app's AOD switch sets persist.sys.hibreak.aod_invert via the root daemon.
set -eu
trap 'status=$?; if [ "$status" -ne 0 ]; then log -p e -t hibreak-display "AOD operation failed (status=$status)"; fi' EXIT
KEY=accessibility_display_inversion_enabled
MARK=persist.sys.hibreak.aod_inverted

case "${1:-}" in
    doze)
        [ "$(getprop persist.sys.hibreak.aod_invert)" = "false" ] && exit 0
        [ "$(cmd settings get secure doze_always_on)" = "1" ] || exit 0
        # Leave inversion the user enabled themselves untouched.
        [ "$(cmd settings get secure $KEY)" = "1" ] && exit 0
        setprop $MARK 1
        cmd settings put secure $KEY 1
        log -t hibreak-display "AOD: colour inversion on"
        ;;
    wake)
        [ "$(getprop $MARK)" = "1" ] || exit 0
        cmd settings put secure $KEY 0
        setprop $MARK 0
        log -t hibreak-display "AOD: colour inversion off"
        ;;
    setup)
        cmd overlay enable me.phh.treble.overlay.misc.aod_systemui
        # Default AOD on once; afterwards respect the user's Settings choice.
        if [ "$(getprop persist.sys.hibreak.aod_setup)" != "1" ]; then
            cmd settings put secure doze_always_on 1
            setprop persist.sys.hibreak.aod_setup 1
        fi
        # Undo inversion left over from a reboot while dozing.
        if [ "$(getprop $MARK)" = "1" ]; then
            cmd settings put secure $KEY 0
            setprop $MARK 0
        fi
        log -t hibreak-display "AOD setup done"
        ;;
    *)
        log -p e -t hibreak-display "Expected AOD action: doze, wake or setup"
        exit 2
        ;;
esac
exit 0
