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

## No devices offered

Only the reported model `C100 Plus` is accepted. Check the account's device list
in DESLOC. Other models and device lists beyond the observed 20-entry request
need further verification.

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
