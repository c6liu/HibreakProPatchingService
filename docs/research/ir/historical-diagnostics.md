# Historical diagnostic results (v1-v6; not release features)

These experiments established a few controller facts, but their old
commands, image recipes and troubleshooting steps are omitted: they describe
superseded test images and are not needed to build or use the current
adapter. The standalone capture tool, fixed-packet transmit test and
privileged TCL test app have since been removed from the repository; they
remain in git history only.

- **Learning did not work on the tested stock 3.1.6 device.** The user
  subsequently reported that the phone has no IR receiver hardware, which
  explains this result. In both short
  and extended modes, a button attempt returned the same bytes as its
  no-button control. A nonempty record or successful controller read was
  therefore not evidence of optical reception. No learning/receive feature
  is claimed or exposed as a supported user feature.
- **A fixed manufacturer sample produced visible IR-camera flashes** in an
  explicitly authorized test. This established optical output for that
  sample only, not its carrier accuracy, appliance meaning, or support for
  arbitrary waveforms.
- **A fixed TCL Volume Up packet controlled the user's TV** through the
  v6 private-path diagnostic app. This established the tested packet and
  device path, not a general Android API or arbitrary-code capability.
- **The v4/v5 private test app needed SELinux/ART startup corrections.**
  The v6 policy fixed the observed JIT-memory and Android service-discovery
  failures. These fixes apply only to the optional diagnostic app; ordinary
  apps use the separate [HAL adapter](../../reference/ir-adapter.md).

See [the build guide](../../build/ir-overlay.md#overlay-details-and-development-options)
for the current HAL overlay.
Do not use the historical test procedures as a production setup guide.
