; KUKANILEA Business OS - NSIS Installer Script (RC1)
; Standard-Konfiguration für den Handwerks-Rollout 2026

!include "MUI2.nsh"
!include "FileFunc.nsh"

; -- App-Details --
!define APP_NAME "KUKANILEA"
!define APP_VERSION "1.0.0"
!define APP_PUBLISHER "Tophandwerk"
!define APP_EXE "KUKANILEA.exe"

Name "${APP_NAME}"
OutFile "..\..\dist\KUKANILEA_Setup_v${APP_VERSION}.exe"

; -- Installations-Pfad --
; Wir installieren in LOCALAPPDATA, um Admin-Rechte-Hürden zu minimieren (User-Only Install)
InstallDir "$LOCALAPPDATA\${APP_NAME}"
InstallDirRegKey HKCU "Software\${APP_NAME}" ""

RequestExecutionLevel user

; -- UI Einstellungen --
!define MUI_ABORTWARNING
!define MUI_ICON "..\..\assets\icon.ico" ; Pfad muss zum Projekt passen
!define MUI_UNICON "..\..\assets\icon.ico"

; -- Installer-Seiten --
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; -- Uninstaller-Seiten --
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "German"

Section "Hauptinstallation" SecMain
    SetOutPath "$INSTDIR"
    
    ; Kopiere die Standalone-EXE aus dem dist-Ordner
    ; Hinweis: Das bundle_windows.ps1 Skript muss vorher gelaufen sein!
    File "..\..\dist\KUKANILEA.exe"
    
    ; Uninstaller schreiben
    WriteUninstaller "$INSTDIR\Uninstall.exe"
    
    ; Registry-Einträge für "Programme und Features"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayName" "${APP_NAME}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "UninstallString" "$INSTDIR\Uninstall.exe"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayIcon" "$INSTDIR\${APP_EXE}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayVersion" "${APP_VERSION}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "Publisher" "${APP_PUBLISHER}"

    ; Desktop & Startmenü Verknüpfungen
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
    CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
SectionEnd

Section "Uninstall"
    ; Dateien löschen
    Delete "$INSTDIR\KUKANILEA.exe"
    Delete "$INSTDIR\Uninstall.exe"
    
    ; Verzeichnis löschen (wenn leer)
    RMDir "$INSTDIR"
    
    ; Verknüpfungen löschen
    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    RMDir "$SMPROGRAMS\${APP_NAME}"
    Delete "$DESKTOP\${APP_NAME}.lnk"
    
    ; Registry löschen
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
    DeleteRegKey HKCU "Software\${APP_NAME}"
SectionEnd

Function .onInit
    ; Hier könnte ein Check auf Ollama implementiert werden (Zukünftiges Feature)
FunctionEnd
