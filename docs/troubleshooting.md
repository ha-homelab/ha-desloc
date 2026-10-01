# Troubleshooting

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

The cloud did not confirm a newer matching state in time, or a request failed.
The command may still have reached the lock. Check physical state and the DESLOC
app before deciding on another action. There are no automatic command retries.

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
