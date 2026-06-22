!define APP_NAME "PVE Center"
!define APP_PUBLISHER "PVE Center"
!define APP_URL "https://github.com/mcluremail/pvecenter"
!define APP_EXE "pvecenter.exe"
!define APP_REGKEY "Software\pvecenter"

Name "${APP_NAME}"
OutFile "pvecenter-setup.exe"
InstallDir "$PROGRAMFILES64\pvecenter"
InstallDirRegKey HKLM "${APP_REGKEY}" "InstallDir"
RequestExecutionLevel admin
ShowInstDetails show
ShowUnInstDetails show
SetCompressor /SOLID lzma
Unicode True

VIAddVersionKey "ProductName" "${APP_NAME}"
VIAddVersionKey "CompanyName" "${APP_PUBLISHER}"
VIAddVersionKey "FileDescription" "${APP_NAME} Installer"
VIAddVersionKey "LegalCopyright" "GPLv3"
VIProductVersion "${VERSION}.0"
VIFileVersion "${VERSION}.0"

Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

Section "Install"
  SetOutPath "$INSTDIR"
  File /r "pvecenter\*.*"

  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortCut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
  CreateShortCut "$SMPROGRAMS\${APP_NAME}\Uninstall ${APP_NAME}.lnk" "$INSTDIR\uninstall.exe"
  CreateShortCut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"

  WriteRegStr HKLM "${APP_REGKEY}" "InstallDir" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "UninstallString" "$\"$INSTDIR\uninstall.exe$\""
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "URLInfoAbout" "${APP_URL}"
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "NoRepair" 1
  WriteRegStr HKLM "Software\Classes\pve-center\shell\open\command" "" "$\"$INSTDIR\${APP_EXE}$\" $\"%1$\""

  WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section "Uninstall"
  Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
  Delete "$SMPROGRAMS\${APP_NAME}\Uninstall ${APP_NAME}.lnk"
  Delete "$DESKTOP\${APP_NAME}.lnk"
  RMDir "$SMPROGRAMS\${APP_NAME}"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
  DeleteRegKey HKLM "${APP_REGKEY}"
  DeleteRegKey HKLM "Software\Classes\pve-center"
SectionEnd

Function .onInit
  !insertmacro MUI_LANGDLL_DISPLAY
FunctionEnd

LangString WelcomeTitle ${LANG_ENGLISH} "Welcome to the PVE Center Setup Wizard"
LangString WelcomeTitle ${LANG_RUSSIAN} "Добро пожаловать в мастер установки PVE Center"
LangString WelcomeTitle ${LANG_ARABIC} "مرحبًا بكم في معالج إعداد PVE Center"
LangString WelcomeTitle ${LANG_FRENCH} "Bienvenue dans l'assistant d'installation de PVE Center"
LangString WelcomeTitle ${LANG_SPANISH} "Bienvenido al asistente de instalación de PVE Center"
LangString WelcomeTitle ${LANG_SIMPCHINESE} "欢迎使用 PVE Center 安装向导"

LangString WelcomeText ${LANG_ENGLISH} "This wizard will guide you through the installation of PVE Center.$\r$\n$\r$\nClick Next to continue or Cancel to exit the Setup Wizard."
LangString WelcomeText ${LANG_RUSSIAN} "Этот мастер поможет вам установить PVE Center.$\r$\n$\r$\nНажмите «Далее» для продолжения или «Отмена» для выхода."
LangString WelcomeText ${LANG_ARABIC} "سيقوم هذا المعالج بتوجيهك خلال تثبيت PVE Center.$\r$\n$\r$\nانقر التالي للمتابعة أو إلغاء للخروج."
LangString WelcomeText ${LANG_FRENCH} "Cet assistant vous guidera dans l'installation de PVE Center.$\r$\n$\r$\nCliquez sur Suivant pour continuer ou Annuler pour quitter."
LangString WelcomeText ${LANG_SPANISH} "Este asistente le guiará a través de la instalación de PVE Center.$\r$\n$\r$\nHaga clic en Siguiente para continuar o Cancelar para salir."
LangString WelcomeText ${LANG_SIMPCHINESE} "此向导将引导您完成 PVE Center 的安装。$\r$\n$\r$\n点击「下一步」继续或「取消」退出。"

LangString DirPageText ${LANG_ENGLISH} "Select the folder to install PVE Center in:"
LangString DirPageText ${LANG_RUSSIAN} "Выберите папку для установки PVE Center:"
LangString DirPageText ${LANG_ARABIC} "اختر المجلد لتثبيت PVE Center فيه:"
LangString DirPageText ${LANG_FRENCH} "Sélectionnez le dossier dans lequel installer PVE Center :"
LangString DirPageText ${LANG_SPANISH} "Seleccione la carpeta para instalar PVE Center:"
LangString DirPageText ${LANG_SIMPCHINESE} "选择安装 PVE Center 的文件夹："

LangString InstallProgress ${LANG_ENGLISH} "Installing..."
LangString InstallProgress ${LANG_RUSSIAN} "Установка..."
LangString InstallProgress ${LANG_ARABIC} "جارٍ التثبيت..."
LangString InstallProgress ${LANG_FRENCH} "Installation..."
LangString InstallProgress ${LANG_SPANISH} "Instalando..."
LangString InstallProgress ${LANG_SIMPCHINESE} "正在安装..."

LangString FinishedTitle ${LANG_ENGLISH} "Installation Complete"
LangString FinishedTitle ${LANG_RUSSIAN} "Установка завершена"
LangString FinishedTitle ${LANG_ARABIC} "اكتمل التثبيت"
LangString FinishedTitle ${LANG_FRENCH} "Installation terminée"
LangString FinishedTitle ${LANG_SPANISH} "Instalación completada"
LangString FinishedTitle ${LANG_SIMPCHINESE} "安装完成"

LangString FinishedText ${LANG_ENGLISH} "PVE Center has been installed on your computer.$\r$\n$\r$\nClick Finish to exit Setup."
LangString FinishedText ${LANG_RUSSIAN} "PVE Center установлен на ваш компьютер.$\r$\n$\r$\nНажмите «Готово» для выхода."
LangString FinishedText ${LANG_ARABIC} "تم تثبيت PVE Center على جهاز الكمبيوتر الخاص بك.$\r$\n$\r$\nانقر إنهاء للخروج."
LangString FinishedText ${LANG_FRENCH} "PVE Center a été installé sur votre ordinateur.$\r$\n$\r$\nCliquez sur Terminer pour quitter l'assistant."
LangString FinishedText ${LANG_SPANISH} "PVE Center se ha instalado en su computadora.$\r$\n$\r$\nHaga clic en Finalizar para salir."
LangString FinishedText ${LANG_SIMPCHINESE} "PVE Center 已安装到您的计算机。$\r$\n$\r$\n点击「完成」退出。"

LangString UninstallConfirm ${LANG_ENGLISH} "Are you sure you want to completely remove PVE Center and all of its components?"
LangString UninstallConfirm ${LANG_RUSSIAN} "Вы уверены, что хотите полностью удалить PVE Center и все его компоненты?"
LangString UninstallConfirm ${LANG_ARABIC} "هل أنت متأكد أنك تريد إزالة PVE Center وجميع مكوناته بالكامل؟"
LangString UninstallConfirm ${LANG_FRENCH} "Êtes-vous sûr de vouloir supprimer complètement PVE Center et tous ses composants ?"
LangString UninstallConfirm ${LANG_SPANISH} "¿Está seguro de que desea eliminar completamente PVE Center y todos sus componentes?"
LangString UninstallConfirm ${LANG_SIMPCHINESE} "您确定要完全移除 PVE Center 及其所有组件吗？"

!include "MUI2.nsh"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "Russian"
!insertmacro MUI_LANGUAGE "Arabic"
!insertmacro MUI_LANGUAGE "French"
!insertmacro MUI_LANGUAGE "Spanish"
!insertmacro MUI_LANGUAGE "SimpChinese"