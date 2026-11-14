#!/system/bin/sh
# The tested-image migration selects its verified AIDL transaction explicitly.
if [ "$#" -gt 1 ]; then
    log -p e -t hibreak-display "Expected at most one disable-HW-overlays mode argument"
    exit 1
fi
case "${1-}" in
    "")
        composer=SurfaceFlinger
        transaction=1008
        ;;
    --aidl)
        composer=SurfaceFlingerAIDL
        transaction=65
        ;;
    *)
        log -p e -t hibreak-display "Unknown disable-HW-overlays mode: $1"
        exit 1
        ;;
esac
log -t hibreak-display "Requesting forced GPU composition via $composer/$transaction"
i=0
while [ $i -lt 30 ]; do
    probe="$(service check "$composer" 2>&1)"
    if printf '%s\n' "$probe" | grep -q ': found'; then
        result="$(service call "$composer" "$transaction" i32 1 2>&1)"
        status=$?
        if [ "$status" -eq 0 ] &&
                printf '%s\n' "$result" | grep -Eq 'Parcel\([[:space:]]*(00000000|NULL)'; then
            state="$(dumpsys SurfaceFlinger 2>&1)"
            state_status=$?
            state_line="$(printf '%s\n' "$state" | grep -E '^[[:space:]]*h/w composer (enabled|disabled)$')"
            if [ "$state_status" -eq 0 ] &&
                    printf '%s\n' "$state_line" | grep -q 'h/w composer disabled$'; then
                log -t hibreak-display "Verified forced GPU composition via $composer/$transaction"
                exit 0
            fi
            log -p e -t hibreak-display "Forced GPU composition not confirmed (dumpsys status=$state_status, state=$state_line)"
        else
            log -p e -t hibreak-display "Disable-HW-overlays transaction failed (status=$status): $result"
        fi
    else
        log -p e -t hibreak-display "$composer unavailable: $probe"
    fi
    i=$((i + 1))
    sleep 1
done
log -p e -t hibreak-display "Unable to disable HW overlays within 30 seconds"
exit 1
