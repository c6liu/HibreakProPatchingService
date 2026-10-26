#!/system/bin/sh
# Equivalent to Developer options > Disable HW overlays (SurfaceFlinger 1008).
i=0
while [ $i -lt 30 ]; do
    if service check SurfaceFlinger | grep -q ': found'; then
        result="$(service call SurfaceFlinger 1008 i32 1 2>&1)"
        status=$?
        case "$result" in
            *"Parcel(00000000"*|*"Parcel(NULL)"*)
                if [ "$status" -eq 0 ]; then
                    log -t hibreak-display "SurfaceFlinger accepted disable-HW-overlays transaction: $result"
                    exit 0
                fi
                ;;
        esac
        log -p e -t hibreak-display "Disable-HW-overlays transaction failed (status=$status): $result"
    fi
    i=$((i + 1))
    sleep 1
done
log -p e -t hibreak-display "Unable to disable HW overlays within 30 seconds"
exit 1
