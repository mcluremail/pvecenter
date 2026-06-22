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

_CONFIRM_ACTIONS = ("stop", "reset", "shutdown", "reboot", "suspend")

_CONFIRM_MESSAGES = {
    "stop": "Force stop VM {vmid}? Unsaved data will be lost.",
    "reset": "Force reset VM {vmid}?",
    "shutdown": "Send ACPI shutdown to VM {vmid}?",
    "reboot": "Send ACPI reboot to VM {vmid}?",
    "suspend": "Suspend VM {vmid}?",
}


def confirm_vm_action(action, vmid, parent=None):
    """Show confirmation dialog for destructive VM actions.
    Returns True if user confirmed, False if cancelled or action doesn't need confirmation.
    """
    if action not in _CONFIRM_ACTIONS:
        return True
    from PySide6.QtWidgets import QMessageBox
    msg_text = tr(_CONFIRM_MESSAGES[action]).format(vmid=vmid)
    msg = QMessageBox(QMessageBox.Warning, tr("Confirm"), msg_text, parent=parent)
    yes = msg.addButton(tr("Yes"), QMessageBox.YesRole)
    msg.addButton(tr("No"), QMessageBox.NoRole)
    msg.setDefaultButton(yes)
    msg.exec()
    return msg.clickedButton() == yes