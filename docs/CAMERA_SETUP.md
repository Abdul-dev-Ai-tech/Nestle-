# Camera setup

| Camera | Read by | How to add |
|---|---|---|
| Laptop webcam | Browser (`getUserMedia`) | Nothing to configure — *Live AI Monitoring › Laptop webcam › Start camera* |
| Mobile phone camera | Browser on the phone | Open the app on the phone over **HTTPS**, choose *Mobile rear camera* |
| USB webcam on an operator PC | Browser | Appears in the camera list after permission is granted |
| USB webcam on the server | Backend (OpenCV) | *Camera Management › Add camera › USB webcam*, device number `0`, `1`, … |
| IP camera (RTSP) | Backend (OpenCV/FFmpeg) | *Add camera › IP camera (RTSP)*, address + credentials |
| ONVIF camera | Backend | *Find ONVIF cameras*, then enter its RTSP address and credentials |

## Why browsers cannot open RTSP

Browsers only expose cameras attached to the device through the MediaDevices API. They cannot open
`rtsp://` streams or cameras attached to another machine. The backend therefore reads those cameras and
relays them: `GET /api/v1/cameras/{id}/snapshot` (one frame) and `/stream` (MJPEG, shown in an `<img>`).
For PPE checks the backend grabs the frame itself.

## HTTPS and permissions

`getUserMedia` works on `http://localhost` and on any `https://` address. Opening the app from a phone by
IP over plain HTTP will **not** offer the camera. In production the app is served over HTTPS (see `docs/DEPLOYMENT.md`).
The UI explains blocked permission, missing camera, busy camera and a disconnected camera.

## RTSP cameras

1. Find the stream path in the camera manual (examples: `rtsp://<ip>:554/Streaming/Channels/101`,
   `rtsp://<ip>:554/cam/realmonitor?channel=1&subtype=0`, `rtsp://<ip>:554/stream1`).
2. Enter the address **without** `user:password@` — the form rejects it. Enter credentials in their own
   fields; they are encrypted in the database and never shown again.
3. Press **Test**. The status becomes *Online* or *Offline* with the reason. An alert is raised when a camera goes offline.
4. The stream reader reconnects automatically with a growing delay (1 s → 30 s).

Create a dedicated read-only camera account for this application. Prefer the camera's sub-stream
(e.g. 1280×720) for monitoring.

## USB cameras on the server

Device `0` is the first camera Windows/Linux reports. In Docker on Linux pass the device through
(`devices: ["/dev/video0:/dev/video0"]` on the backend service). Docker Desktop on Windows cannot pass USB
cameras into containers — run the backend natively on Windows for USB cameras.

## ONVIF discovery

Uses WS-Discovery (UDP multicast 239.255.255.250:3702). It only finds devices on the **same network
segment as the backend**; it will find nothing from a cloud server or, usually, from inside a Docker bridge
network (use `network_mode: host` on Linux). Discovery returns the device address; the RTSP path still has
to be entered.

## Not verified here

The USB, RTSP, MJPEG-relay and ONVIF code paths were written against the OpenCV/ONVIF specifications but
could not be exercised against physical cameras in the build environment (only the failure path — an
unreachable camera — is covered by an automated test). Test each camera model on site.
