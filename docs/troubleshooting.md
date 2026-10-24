# Troubleshooting

## The DESLOC update dialog shows "icon not available"

HACS 2.0.5 loads the update entity's picture from an external brands service,
even though DESLOC includes local icon files. Use the optional
[local update-entity picture customization](branding.md) to show the bundled
icon. This requires a small Home Assistant configuration change; installing a
DESLOC release alone does not apply it. The HACS catalog listing is separate.

## The phone app repeatedly returns to login

Version 0.2.0 could automatically sign in after the phone had displaced HA's
session, which in turn displaced the phone's session. Temporarily disable the
DESLOC integration, sign in to the app, and update to 0.2.1. Import the current
app session through **Reconfigure → Use a captured app session** before enabling
the integration again. Version 0.2.1 saves the session token across restarts and
stops after rejection instead of signing in again. A separate installation ID
alone did not isolate concurrent logins on the tested account.

## Devices became unavailable after signing out of DESLOC

App logout was observed to revoke the session copied into HA. Sign back into the
app, capture its new session, and complete the integration's reauthentication
flow. The lock identity, entity IDs, and dashboard configuration are retained.
Email/password login is interactive and may revoke the phone session. It is not
an automatic renewal mechanism. Version 0.2.0 digest entries require
reauthentication or a session import when updating to 0.2.1.

## Invalid session

Use the business API `authorization` value unchanged and its `deviceid` header.
The lock ID, Bluetooth MAC, and IoT token are different values. Do not prepend
`Bearer`. Match the app version/system type. Capture again after expiry or revocation.

## A lock is missing

Version 0.3.0 adds every lock returned by the authenticated DESLOC account;
there is no C100 Plus model filter. Check the account's list in the DESLOC app.
For a lock paired after setup, use **Reconfigure** on an existing DESLOC entry.
Reconfiguration adds missing entries and updates the shared session for returned
locks; it preserves entity IDs and disabled entries. Normal state polling does
not add entries automatically. The device-list response must contain a valid
numeric device ID and MAC; an unfamiliar or malformed response is reported as a
protocol error rather than inventing an identity.

## An experimental model does not work

C100 Plus is physically tested. Other model names are admitted for testing and
have `model_validation: experimental` on their entities. State codes, remote
control, and PIN support may differ. Download diagnostics from the entry menu and
report the model/firmware, HA/app versions, affected feature, and sanitized error.
Do not repeatedly send a command after an uncertain result. Compatibility fixes
or explicit model exclusions will follow evidence from community reports.

## App device list disappears during capture

Install the CA profile **and** enable full trust. Disable the iPhone's Wi-Fi proxy
to restore direct connectivity. Do not factory-reset or re-pair the lock to fix
a certificate problem.

## Command timeout or unknown state

An accepted request does not prove that the bolt moved. DESLOC result code
`2104` means the cloud no longer provides a confirmed result for that command;
it can arrive before the integration's 45-second deadline. The command may
still have reached the lock. This is distinct from an authentication error.
Check physical state and the DESLOC app before deciding on another action.
There are no automatic command retries.

After an attempted command, HA suppresses the previous bolt report until the
cloud supplies a newer state timestamp. `Unknown` can therefore coexist with
successful polling, battery/RSSI readings, and a raw bolt code. Those readings
can be cached; the unverified `onlineStatus` enum is not proof of a live device
connection. A fresh report restores the reported state automatically. Do not
reload the integration just to remove `Unknown`, because that does not confirm
the physical bolt position.

During a supervised C100 Plus test, the cloud expired the result roughly
11 seconds after accepting an unlock request, but the lock opened later. The
previous implementation then waited for its next minute-based poll before
displaying the new state. This confirms that result expiry does not cancel an
accepted command or prove that it will not execute.

The 0.4.3 late-confirmation update stops polling an expired result and continues
read-only state checks every two seconds within the original 45-second command
deadline. The operation remains pending during this interval. A successful
read with a strictly newer timestamp and the requested bolt state confirms the
reported state; diagnostics still distinguish this from a successful command
acknowledgement. An unchanged or opposite report cannot confirm the request.
If the deadline expires, HA reports uncertainty and resumes normal polling.
The integration never resends the command automatically, and delivery can still
occur after the deadline.

### Collect useful diagnostics

1. Open **Settings → Devices & services → DESLOC** and use the affected lock
   entry's menu to **Download diagnostics** before reloading or restarting HA.
   The command snapshot is kept in memory only and records the most recent
   lock/unlock attempt, not PIN operations or a persistent activity history.
2. Check the command phase, outcome, elapsed time, result poll count, and
   acceptance/acknowledgement flags alongside state freshness. Successful
   polling with `awaiting_fresh_state` explains why HA may still show `Unknown`.
   Acceptance means a result ID was returned; acknowledgement means the cloud
   returned a successful command result. Neither is independent bolt sensing.
   `result_expired` and `state_confirmed` are separate flags: a late matching
   report can confirm the requested state even when acknowledgement is missing.
   `state_poll_count` counts confirmation reads during that command attempt.
3. If more evidence is needed, enable **debug logging** from the DESLOC
   integration menu. Capture only a deliberate, supervised operation, then
   disable debug logging and save the offered log. Do not repeatedly operate
   the lock simply to produce more logs. See Home Assistant's
   [debug logging instructions](https://www.home-assistant.io/docs/configuration/troubleshooting/#debug-logs-and-diagnostics).

DESLOC's command diagnostics and log messages use fixed categories and counters;
they do not include account credentials, PINs, names, MACs, device IDs, command
IDs, HTTP payloads, or absolute command timestamps. Review the complete HA
download before sharing, because it can also contain platform metadata and
messages from other components. Include whether the bolt actually moved and
whether the app, keypad, or manual thumb turn was used after the error.

## Unavailable entities or slow updates

Check internet access, DESLOC service availability, session validity, and whether
the lock remains in the account. Reads resume after connection failures; expired
credentials require reauth. Normal polling is once per minute, with faster reads
after commands. A sleeping/disconnected device may leave old cloud telemetry.

## Reporting

Include model, app version, HA version, operation, and sanitized errors. Never
attach raw captures, tokens, CA keys, account emails, serials, device IDs, Wi-Fi
SSIDs, or full config-entry data.

## Account login requests verification

DESLOC checks new installations with an email code. Use the most recent code in
the HA setup form. The installation ID is retained for subsequent logins.
A changed password or a new security challenge can require reauthentication.
If sending a code is rate-limited, wait before restarting setup.

## Clock error or CAPTCHA

Synchronize the HA host clock when DESLOC reports a time error. The login payload
contains the current Unix time. For CAPTCHA, complete the challenge in the
DESLOC app; the integration does not solve or bypass it. Captured-session setup
remains available as an alternative.
