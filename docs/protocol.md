# Observed protocol

Observed on C100 Plus and DESLOC iOS 1.2.1. Examples use synthetic IDs. This is
not an official API specification.

## Authentication

The business API `https://appadmin.desloc.com` requires `authorization`,
`deviceid`, `appversion`, and `systype` headers. Removing any one caused rejection.
The opaque authorization token is sent verbatim. Its lifetime and renewal
mechanism remain unknown.

The app separately posts to `https://iot.desloc.com/oauth/token` with a URL-encoded
form containing `appId` and `biz_token`. That returns an access token, refresh
token, and expiry. Neither the access token nor the form's business token matched
the business API authorization in the captured session. This exchange does not
establish a refresh mechanism for this integration.

Signed requests to `xsgateway.desloc.com` were also observed; this integration
does not require that interface or reproduce its signatures.

## Status

`POST /api/device/list` uses `{"groupId":0,"size":20}`. Success has `status: 200`,
`success: true`, and a device list in `data`. Fields used:

- `id`: numeric cloud identity; commands send its string representation.
- `mac`: Bluetooth MAC, used for stable config-entry identity.
- `deviceName`, `model`, `firmwareVersion`: metadata.
- `doorState`: 1 unlocked, 2 locked; other values remain unknown.
- `doorStateUpdateTime`: reported state timestamp in milliseconds.
- `batteryValue`: percentage, accepted only within 0–100.
- `networkSignal`: RSSI in dBm.
- `onlineStatus`: unverified enum, exposed only as a raw diagnostic.

Authentication failure can arrive as HTTP 200 with business `status: 401` and
`success: false`. HTTP success alone is insufficient.

## Commands

`POST /api/device/remoteSwitchLock` uses
`{"deviceId":"123","unlock":true}` to unlock, or `false` to lock. Success
returns `data.commandId`, which acknowledges acceptance rather than bolt state.

`POST /api/device/fecommand/result/<commandId>` with `{}` reads progress:

- 2206 with `success: false`: pending.
- 200 with `success: true`: completed according to the cloud.
- 2104: expired or timed-out result.
- Other failures end the operation; authentication errors require reauth.

```mermaid
sequenceDiagram
    actor User
    participant HA as Home Assistant
    participant Cloud as DESLOC cloud
    participant Lock as C100 Plus
    User->>HA: Lock or unlock
    HA->>Cloud: remoteSwitchLock (once)
    Cloud-->>HA: commandId
    Cloud->>Lock: Vendor command delivery
    loop Every 2 seconds while pending
        HA->>Cloud: fecommand/result/commandId
        Cloud-->>HA: 2206 pending or 200 completed
    end
    Lock-->>Cloud: Updated bolt state
    HA->>Cloud: device/list
    Cloud-->>HA: State and newer timestamp
    alt Fresh state matches requested target
        HA-->>User: Confirmed reported state
    else Timeout, error, or stale state
        HA-->>User: Error and unconfirmed state
    end
```

The total deadline is 45 seconds. After acknowledgement, up to six status reads
allow for delayed telemetry. Physical commands are never automatically resubmitted;
concurrent commands for one entry are rejected.

```mermaid
stateDiagram-v2
    [*] --> Reported
    Reported --> InProgress: User requests operation
    InProgress --> Reported: New matching state report
    InProgress --> Unknown: No fresh confirmation
    Unknown --> Reported: New state timestamp
    Reported --> Unavailable: Read fails or device disappears
    Unavailable --> Reported: Reads recover
```

Redirects are refused, keeping credentials on the fixed HTTPS origin. Errors
omit raw response bodies and credentials. Unknown values are not guessed.
