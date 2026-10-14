# iOS 27 instrument-cluster capture plan

This branch investigates why Apple Maps on the BYD instrument cluster can remain in an overview / north-up presentation and which current CarPlay state selects a detail / heading-up presentation.

## Why capture first

DiPlay 0.2.20 already negotiates CarPlay `altScreen` and accepts the Type-111 auxiliary screen. Current iOS 27 sender research also retains the classic instrument-cluster URL family:

```text
maps:/car/instrumentcluster
maps:/car/instrumentcluster/map
maps:/car/instrumentcluster/instructioncard
```

The missing behavior may live in a separate control/state layer (`suggestUI`, display mode, ViewArea, navigation ownership, or a related current-iOS field), not in the H.264 transport itself. Hard-coding a guessed mode before observing the phone risks breaking a working Type-111 path.

DiPlay already writes raw AirPlay binary-plist bodies into its diagnostic TRACE log as `bodyHex=...`. `tools/cluster_protocol_report.py` decodes those existing traces without modifying the transport path on the car.

## Capture sequence on the Seal

Use an iPhone on iOS 27 and keep the same CarPlay session for the whole sequence when possible.

1. Connect CarPlay with the instrument-cluster map enabled in DiPlay.
2. Open Apple Maps without starting guidance and create a diagnostic marker by noting the clock time.
3. Start a real route and drive only when safe to do so. Record whether the cluster is north-up or heading-up.
4. On the center display, switch Apple Maps between Detail and Overview if that control is available.
5. If Apple Maps offers a dual-display / display-swap control, switch the map presentation between the center display and instrument cluster, then switch it back.
6. Stop guidance cleanly.
7. Export DiPlay's diagnostic report.

For the first vehicle test, do not modify vehicle CAN/HUD settings and do not combine this capture with the planned DL3 windshield-HUD injection experiment. Keeping the variables separate makes the trace useful.

## Decode the report

On a PC with Python 3:

```bash
python3 tools/cluster_protocol_report.py /path/to/diplay-diagnostic.txt
```

If that produces no events, verify that the report contains TRACE data:

```bash
python3 tools/cluster_protocol_report.py /path/to/diplay-diagnostic.txt --all
```

Machine-readable output:

```bash
python3 tools/cluster_protocol_report.py /path/to/diplay-diagnostic.txt --json > cluster-events.jsonl
```

The tool has no external Python dependencies.

## Events of interest

The first pass highlights:

```text
suggestUI
showUI
stopUI
requestUI
modesChanged
changeModes
updateViewArea
requestViewArea
forceKeyFrame
changeMapZoomLevel
setSecondDisplayMode / SecondDisplayMode-like commands
uiAppearanceUpdate
mapAppearanceUpdate
```

It also surfaces decoded plists that contain keys related to:

```text
altScreen
cluster / instrument
SecondDisplay / displayMode
ViewArea
mapsPresentation
maneuverLayout
showETA / showSpeedLimit / showCompass
```

and any SETUP plist containing a Type-111 stream.

## What would prove the heading-up control

The strongest result is a reproducible difference immediately before and after a visible presentation change. Examples:

```diff
- secondDisplayMode: 0
+ secondDisplayMode: 1
```

or:

```diff
- maps:/car/instrumentcluster/map
+ maps:/car/instrumentcluster
```

or a `modesChanged` / ViewArea payload whose value changes at the same moment that Apple Maps moves from overview/north-up to detail/heading-up.

Do not assume any numeric enum meaning until it is correlated with a visible vehicle result.

## After the capture

Once the exact iOS 27 state transition is known, implement the smallest receiver-side change needed to request or preserve that state. Keep Type 111 alive across ordinary navigation/provider changes unless a real AirPlay transport generation change is observed.

The DL3 windshield-HUD CAN work remains a separate branch/phase after the cluster presentation control is understood.
