#!/usr/bin/env bash
# KUKANILEA Comp-Stream Backup
# Erstellt stark komprimierte, mandantengetrennte Backups auf dem ZimaBoard NAS.
# Voraussetzung: zstd muss auf dem Host installiert sein (brew install zstd / apt install zstd)

set -e

# Konfiguration
SOURCE_DIR=${KUKANILEA_USER_DATA_ROOT:-"../instance/tenants"}
BACKUP_TARGET="/Volumes/KUKANILEA-BACKUP" # SMB Mountpoint des ZimaBoards (smb://192.168.0.2)
DATE_STR=$(date +"%Y%m%d_%H%M%S")

echo "=== KUKANILEA COMP-STREAM BACKUP ==="
echo "Starte Backup-Prozess: $DATE_STR"

# Prüfe, ob ZimaBoard erreichbar/gemountet ist
if [ ! -d "$BACKUP_TARGET" ]; then
    echo "[FEHLER] ZimaBoard NAS ist nicht unter $BACKUP_TARGET gemountet."
    echo "Bitte stelle sicher, dass smb://192.168.0.2/KUKANILEA-BACKUP verbunden ist."
    exit 1
fi

# Prüfe ob zstd verfügbar ist
if ! command -v zstd &> /dev/null; then
    echo "[FEHLER] zstd ist nicht installiert. Bitte installieren (z.B. apt install zstd)."
    exit 1
fi

if [ ! -d "$SOURCE_DIR" ]; then
    echo "[INFO] Kein Mandanten-Verzeichnis gefunden unter $SOURCE_DIR. Nichts zu sichern."
    exit 0
fi

# Iteriere über alle Mandanten-Ordner und archiviere sie strikt getrennt
for tenant_dir in "$SOURCE_DIR"/*; do
    if [ -d "$tenant_dir" ]; then
        tenant_name=$(basename "$tenant_dir")
        
        # Erstelle Mandanten-Zielverzeichnis auf dem NAS
        target_dir="$BACKUP_TARGET/$tenant_name"
        mkdir -p "$target_dir"
        
        archive_name="$target_dir/${tenant_name}_backup_${DATE_STR}.tar.zst"
        
        echo "--> Sichere Mandant: $tenant_name"
        # Nutze zstd Level 19 (Ultra) für maximale Kompression
        tar -I 'zstd -19 -T0' -cf "$archive_name" -C "$SOURCE_DIR" "$tenant_name"
        
        echo "    Erfolgreich gesichert: $archive_name"
    fi
done

echo "=== BACKUP ABGESCHLOSSEN ==="
