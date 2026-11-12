# Tools

This directory contains the build, image, device, runtime, and test tools for
the HiBreak Pro E-Ink service. Use this page to find a workflow; the
[tools reference](../docs/reference/tools.md) describes individual scripts.

## Start by task

| Task | Start here |
| --- | --- |
| Build a supported release image | [Build guide](../docs/build/README.md) |
| Find a script or run a manual image operation | [Tools reference](../docs/reference/tools.md) |
| Run host or APK tests | [Test guide](../docs/build/tests.md) |
| Flash an image | [Flashing helper reference](../docs/reference/flashing.md) |

## Release build entry point

[`build/build-release.py`](build/build-release.py) is the supported end-to-end
builder. After preparing the inputs in the [build guide](../docs/build/build-image.md),
run it from the repository root:

```bash
python3 tools/build/build-release.py --help
python3 tools/build/build-release.py "$BASE"
```

It builds the APK from checked-in source, builds the daemon, patches the image,
and writes a manifest with input/output checksums and stage timings. It does
not flash a device. Tested-device defaults are restricted to the documented
GSI and stock vendor image; use `--compatibility` for other GSIs. Standalone
image scripts are manual alternatives, not extra stages to apply after a
completed release build.

## Directory map

| Workflow area | Directory | Contents |
| --- | --- | --- |
| Build | [`build/`](build/) | Release orchestration and APK, daemon, and IR build scripts |
| Build | [`android-system-api-stubs/`](android-system-api-stubs/) | Compile-time Android system API stub for the source APK |
| Image pipeline | [`image/`](image/) | Offline GSI patchers and optional IR, XRZ, and PHH overlays |
| Image pipeline | [`hibreak/`](hibreak/) | Shared image, policy, verification, and release-pipeline modules |
| Image pipeline | [`internal/`](internal/) | Helpers used by the patcher and release pipeline |
| Image pipeline | [`lib/`](lib/) | Shared shell build helpers |
| Device and diagnostics | [`device/`](device/) | Diagnostic collection and the system-image flashing helper |
| Device and diagnostics | [`diagnostics/`](diagnostics/) | Host-side policy checks and optional IR research tools |
| Runtime components | [`display/`](display/) | Display and e-ink scripts, init configuration, and policy |
| Runtime components | [`ir/`](ir/) | NEC transmit HAL sources, policies, and API test app assets |
| Validation | [`tests/`](tests/) | Host tests and native fixtures |

## Host tests

Run the Python host suite from the repository root:

```bash
python3 -m unittest discover -s tools/tests -v
```

For focused commands, APK checks, and device-verification guidance, see the
[test guide](../docs/build/tests.md). Passing host tests does not establish
firmware compatibility or replace physical-device validation.

## Safety boundaries

- Image patchers run offline and write new image files; no tool patches the
  vendor image automatically.
- The flashing helper previews by default. `--flash` is required to execute a
  flash; `--wipe-data` is a separate destructive option that erases shared
  userdata. Review the [flashing helper reference](../docs/reference/flashing.md)
  before using it.
