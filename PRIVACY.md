# Privacy Policy — Leave Me to My Own Devices

_Last updated: 2026-05-31_

## Summary

The **Leave Me to My Own Devices** Apple Vision Pro app does not collect,
store, transmit, or share any personal data. It does not use analytics,
advertising, tracking, or any third-party SDKs. All communication happens
between the app and devices on **your own local network** — nothing is sent
to the app developer, to Apple, or to any third party.

## What the app does on your network

When you grant **Local Network** permission, the app uses Apple's standard
Bonjour discovery (service type `_shopwidget._tcp`) to find compatible
"shop-agent" services on the LAN you are connected to.

For each device you choose to add:

- The app fetches a small JSON **widget manifest** from that device over
  HTTP.
- The app subscribes to a **WebSocket stream** of live data from that
  device.
- When you interact with a widget (toggle, slider, button), the app sends
  the action back to that same device over HTTP.

The list of devices on the network is built dynamically from what your
LAN advertises. No background scanning happens off-LAN, and no destination
outside your local network is ever contacted by the app.

## What we store on your device

The following information is kept locally on your Apple Vision Pro and
never leaves it:

- The list of devices you add (hostname, port, label, your chosen
  short id).
- The widgets you've placed into your space.
- Any bearer tokens you paste in to authenticate against a device.

This data is removed when you delete the app from your Vision Pro.

## What we do NOT collect

To be explicit:

- No user account, no email address, no name.
- No location data, no contacts, no photos, no health data.
- No analytics, telemetry, crash reporting, or "anonymous usage data."
- No advertising identifiers (no IDFA, no fingerprinting).
- No third-party SDKs of any kind.

## Children

The app does not collect data from anyone, including children. It is
suitable for users of all ages and is rated **4+** on the App Store.

## Changes to this policy

If this policy ever changes, the updated version will be published in this
file in the public repository, and the "Last updated" date at the top
will reflect the change. The app store page links to this file directly,
so the policy you see is always the current one.

## Contact

For questions or to report a privacy concern, open an issue at
<https://github.com/gcullie/lmToMyOwnDevices-public/issues> or use the
support contact listed on the app's App Store page.
