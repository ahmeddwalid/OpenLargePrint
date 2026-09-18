; NSIS Hooks for OpenLargePrint (PKG-001)
; Registers Windows Explorer right-click shell context menu on install
; Unregisters on uninstall

!macro customInstall
  ; Context menu for PDF files
  WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.pdf\Shell\OpenLargePrint" "" "Enlarge with OpenLargePrint"
  WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.pdf\Shell\OpenLargePrint" "Icon" "$INSTDIR\OpenLargePrint.exe,0"
  WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.pdf\Shell\OpenLargePrint\Command" "" '"$INSTDIR\OpenLargePrint.exe" "%1"'

  ; Context menu for Word (.docx) files
  WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.docx\Shell\OpenLargePrint" "" "Enlarge with OpenLargePrint"
  WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.docx\Shell\OpenLargePrint" "Icon" "$INSTDIR\OpenLargePrint.exe,0"
  WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.docx\Shell\OpenLargePrint\Command" "" '"$INSTDIR\OpenLargePrint.exe" "%1"'

  ; Context menu for Word (.doc) files
  WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.doc\Shell\OpenLargePrint" "" "Enlarge with OpenLargePrint"
  WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.doc\Shell\OpenLargePrint" "Icon" "$INSTDIR\OpenLargePrint.exe,0"
  WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.doc\Shell\OpenLargePrint\Command" "" '"$INSTDIR\OpenLargePrint.exe" "%1"'

  ; Context menu for PowerPoint (.pptx) files
  WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.pptx\Shell\OpenLargePrint" "" "Enlarge with OpenLargePrint"
  WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.pptx\Shell\OpenLargePrint" "Icon" "$INSTDIR\OpenLargePrint.exe,0"
  WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.pptx\Shell\OpenLargePrint\Command" "" '"$INSTDIR\OpenLargePrint.exe" "%1"'

  ; Context menu for PowerPoint (.ppt) files
  WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.ppt\Shell\OpenLargePrint" "" "Enlarge with OpenLargePrint"
  WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.ppt\Shell\OpenLargePrint" "Icon" "$INSTDIR\OpenLargePrint.exe,0"
  WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.ppt\Shell\OpenLargePrint\Command" "" '"$INSTDIR\OpenLargePrint.exe" "%1"'

  ; Generic fallback context menu
  WriteRegStr HKCU "Software\Classes\*\shell\OpenLargePrint" "" "Enlarge with OpenLargePrint"
  WriteRegStr HKCU "Software\Classes\*\shell\OpenLargePrint" "Icon" "$INSTDIR\OpenLargePrint.exe,0"
  WriteRegStr HKCU "Software\Classes\*\shell\OpenLargePrint\command" "" '"$INSTDIR\OpenLargePrint.exe" "%1"'
!macroend

!macro customUnInstall
  DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.pdf\Shell\OpenLargePrint"
  DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.docx\Shell\OpenLargePrint"
  DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.doc\Shell\OpenLargePrint"
  DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.pptx\Shell\OpenLargePrint"
  DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.ppt\Shell\OpenLargePrint"
  DeleteRegKey HKCU "Software\Classes\*\shell\OpenLargePrint"
!macroend
