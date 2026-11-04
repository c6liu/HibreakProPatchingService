# Camera preview pauses

On 2026-10-26, the user reported intermittent multi-second freezes in the
live preview of Aperture (`org.lineageos.aperture`). Camera controls remain
responsive, and pressing an on-screen button immediately resumes the preview.
The user reproduced this in both **Fast** and **Hyper**; changing between
those modes is not a workaround.

During a separate five-second live sample, camera stream frames produced
advanced from 133 to 263. The preview uses a SurfaceView. These observations
show that frame production worked during that sample, not that it continued
during a confirmed freeze. The vendor composer also logged anti-flicker write
failures, but these are not established as the cause.

A redraw/presentation problem is a working hypothesis because UI interaction
resumes the preview. The cause remains unconfirmed; do not assume it is the
same failure as the [composer crash](composer-crash.md). No camera fix has been applied.
Logs and camera dumps are kept locally in `build/camera-20261026-0645/`.
The next diagnostic is to compare camera frame progression and SurfaceFlinger
preview timestamps during a confirmed pause, before touching any controls.
