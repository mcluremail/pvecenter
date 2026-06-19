from .i18n import tr

VM_ACTION_BUTTON_LABELS = {
    "start": tr("Start"),
    "shutdown": tr("Shutdown"),
    "reboot": tr("Reboot"),
    "reset": tr("Reset"),
    "stop": tr("Stop"),
    "resume": tr("Resume"),
}

VM_ACTION_MESSAGE_LABELS = {
    "start": tr("Start"),
    "shutdown": tr("Shutdown"),
    "stop": tr("Force stop"),
    "reboot": tr("Reboot"),
    "reset": tr("Reset"),
    "resume": tr("Resume"),
}

VM_ACTION_ICONS = {
    "start": "start",
    "shutdown": "shutdown",
    "reboot": "reboot",
    "reset": "reset",
    "stop": "stop",
    "resume": "resume",
}

VM_ACTION_TOOLTIPS = {
    "start": tr("Start VM"),
    "shutdown": tr("Send ACPI shutdown signal to VM"),
    "reboot": tr("Send ACPI reboot signal to VM"),
    "reset": tr("Hard reset VM (unsaved data will be lost)"),
    "stop": tr("Force stop VM (kill process, unsaved data lost)"),
    "resume": tr("Resume suspended VM"),
}