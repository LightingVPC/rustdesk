#!/usr/bin/env python3
"""Fast, non-secret-printing preflight checks for customized RustDesk builds."""

import base64
import binascii
import os
import pathlib
import py_compile
import re
import sys
import xml.etree.ElementTree as ET


def fail(message):
    raise SystemExit("Custom build preflight failed: " + message)


def main():
    root = pathlib.Path(__file__).resolve().parents[2]

    # Detect broken Python packaging edits before starting platform builds.
    py_compile.compile(str(root / "build.py"), doraise=True)

    name = os.environ.get("RS_APP_NAME", "").strip()
    if name and (
        len(name) > 64
        or any(ord(ch) < 32 or ch in '<>:"/\\|?*\'' for ch in name)
    ):
        fail("RS_APP_NAME must be at most 64 characters without reserved characters.")

    if os.environ.get("RUSTDESK_HIDE_CM_BUILD") == "true" and not os.environ.get(
        "RS_PRV_PWD", ""
    ).strip():
        fail("HideCM builds require the RS_PRV_PWD Actions secret.")

    # A self-hosted rendezvous endpoint must be paired with its own signing key.
    key = os.environ.get("RS_PUB_KEY", "").strip()
    host = os.environ.get("RENDEZVOUS_SERVER", "").strip()
    if bool(key) != bool(host):
        fail("Configure RS_PUB_KEY and RENDEZVOUS_SERVER together in Actions Secrets.")
    if host and "://" in host:
        fail("RENDEZVOUS_SERVER must be a host or host:port, not an HTTP URL.")
    if key:
        try:
            decoded = base64.b64decode(key, validate=True)
        except (ValueError, binascii.Error):
            fail("RS_PUB_KEY must be a valid base64-encoded Ed25519 public key.")
        if len(decoded) != 32:
            fail("RS_PUB_KEY must decode to exactly 32 bytes.")

    # The build.py custom display-name helper must match these platform assets.
    resource = (root / "flutter/windows/runner/Runner.rc").read_text(encoding="utf-8")
    for field in ("ProductName", "FileDescription"):
        pattern = rf'(?m)^(\s*VALUE "{field}", )"[^"]*"( "\\0")$'
        if re.search(pattern, resource) is None:
            fail(f"Windows resource field {field} cannot be customized.")

    plist = ET.parse(root / "flutter/macos/Runner/Info.plist")
    if plist.find(".//key[.='CFBundleDisplayName']") is None:
        fail("macOS CFBundleDisplayName is missing.")

    manifest = (root / "flutter/android/app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
    gradle = (root / "flutter/android/app/build.gradle").read_text(encoding="utf-8")
    if 'android:label="@string/app_name"' not in manifest:
        fail("Android application label does not use the generated resource.")
    if 'resValue "string", "app_name", rsAppName' not in gradle:
        fail("Android app_name Gradle resource is missing.")

    print("Preflight OK: Python, desktop/android branding, and server key configuration.")
    print("Self-hosted server defaults:", "configured" if host else "not configured")


if __name__ == "__main__":
    main()
