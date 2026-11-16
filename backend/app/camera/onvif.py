"""ONVIF camera discovery using WS-Discovery (UDP multicast probe).

Finds ONVIF-compatible devices on the SAME network segment as the server. It returns device
service addresses only; the RTSP stream URL and credentials are then entered by an administrator.
Multicast is often blocked across VLANs, in containers and in the cloud — see docs/CAMERA_SETUP.md.
"""
import re
import socket
import uuid

_PROBE = """<?xml version="1.0" encoding="UTF-8"?>
<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope" xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"
 xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery" xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
 <e:Header><w:MessageID>uuid:{id}</w:MessageID>
 <w:To e:mustUnderstand="true">urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>
 <w:Action e:mustUnderstand="true">http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action></e:Header>
 <e:Body><d:Probe><d:Types>dn:NetworkVideoTransmitter</d:Types></d:Probe></e:Body></e:Envelope>"""


def discover(timeout: float = 3.0) -> list[dict]:
    found: dict[str, dict] = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.settimeout(timeout)
        sock.sendto(_PROBE.format(id=uuid.uuid4()).encode(), ("239.255.255.250", 3702))
        while True:
            try:
                data, addr = sock.recvfrom(65535)
            except (TimeoutError, socket.timeout):
                break
            text = data.decode("utf-8", "ignore")
            xaddrs = re.search(r"<[^>]*XAddrs[^>]*>([^<]+)<", text)
            scopes = re.search(r"<[^>]*Scopes[^>]*>([^<]+)<", text)
            name = ""
            if scopes:
                m = re.search(r"onvif://www\.onvif\.org/name/([^\s]+)", scopes.group(1))
                name = m.group(1).replace("%20", " ") if m else ""
            found[addr[0]] = {"ip": addr[0], "name": name or "ONVIF device",
                              "service_urls": xaddrs.group(1).split() if xaddrs else []}
    except OSError:
        return []
    finally:
        sock.close()
    return sorted(found.values(), key=lambda d: d["ip"])
