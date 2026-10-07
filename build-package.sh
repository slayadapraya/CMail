#!/usr/bin/env bash
set -euo pipefail
aster_source="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
aster_build="$(mktemp -d)"
trap 'rm -rf -- "$aster_build"' EXIT
chmod 755 "$aster_build"
mkdir -p "$aster_build/DEBIAN" "$aster_build/usr/share/aster-mail/aster" "$aster_build/usr/share/aster-mail/assets" "$aster_build/usr/bin" "$aster_build/usr/share/applications" "$aster_build/usr/share/icons/hicolor/scalable/apps" "$aster_build/usr/share/doc/aster-mail"
cp "$aster_source"/aster/*.py "$aster_build/usr/share/aster-mail/aster/"
cp "$aster_source/assets/cmail-icon.svg" "$aster_build/usr/share/aster-mail/assets/"
cp "$aster_source/launcher.py" "$aster_build/usr/share/aster-mail/"
cp "$aster_source/assets/org.aster.Mail.svg" "$aster_build/usr/share/icons/hicolor/scalable/apps/"
cp "$aster_source"/*.md "$aster_source/LICENSE" "$aster_build/usr/share/doc/aster-mail/"
cat > "$aster_build/usr/bin/cmail" <<'LAUNCH'
#!/usr/bin/env bash
exec /usr/bin/python3 /usr/share/aster-mail/launcher.py "$@"
LAUNCH
chmod 755 "$aster_build/usr/bin/cmail"
ln -s cmail "$aster_build/usr/bin/aster-mail"
cat > "$aster_build/usr/share/applications/org.aster.Mail.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=CMail
Comment=Mail, contacts and calendar for Microsoft and Gmail
Exec=cmail
Icon=org.aster.Mail
Terminal=false
Categories=Network;Email;Office;Calendar;
StartupNotify=true
DESKTOP
cat > "$aster_build/DEBIAN/control" <<'CONTROL'
Package: cmail
Replaces: aster-mail
Conflicts: aster-mail
Version: 0.8.2
Architecture: all
Maintainer: CMail contributors <aster-maintainers@example.invalid>
Depends: python3 (>= 3.10), python3-gi, python3-gi-cairo, python3-requests, gir1.2-gtk-4.0 (>= 4.12), gir1.2-adw-1, gir1.2-gdkpixbuf-2.0, gir1.2-secret-1, gir1.2-webkit-6.0
Recommends: gnome-keyring
Section: mail
Priority: optional
Description: Native Linux client for Microsoft and Gmail mail and calendar
 A free, MIT-licensed GTK4 client with a demo workspace, Microsoft Graph
 and Gmail integration, rich drafts, theme/layout controls and optional AI help.
CONTROL
chmod -R go-w "$aster_build"
dpkg-deb --root-owner-group --build "$aster_build" "${1:-$aster_source/../cmail_0.8.2_all.deb}"
