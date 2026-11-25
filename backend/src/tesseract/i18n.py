"""Übersetzungen für Texte, die das Backend selbst verschickt (Benachrichtigungen).

Quelle ist Deutsch, der deutsche Text ist der Schlüssel – wie im Frontend
(frontend/src/lib/i18n). Platzhalter {0}, {1} … wie bei str.format. Fehlermeldungen der API
übersetzt das Frontend (en.api.json), damit sie hier deutsch bleiben können.
"""

LANGUAGES = ("de", "en")

EN: dict[str, str] = {
    # Ereignisse
    "Node offline": "Node offline",
    "Node wieder online": "Node back online",
    "Dienst nicht erreichbar": "Service unreachable",
    "Dienst wieder erreichbar": "Service reachable again",
    "Config nicht übertragen": "Config not applied",
    "Node lokal geändert": "Node changed locally",
    "IP automatisch gesperrt": "IP banned automatically",
    "Fehlgeschlagene Anmeldung": "Failed sign-in",
    "Gerät möchte sich registrieren": "Device wants to register",
    "Agent möchte beitreten": "Agent wants to join",
    "Falscher Einladungscode": "Wrong invitation code",
    "Sicherung fehlgeschlagen": "Backup failed",
    "Gerätezertifikat läuft ab": "Device certificate expiring",
    "Zwischenzertifikat läuft ab": "Intermediate certificate expiring",
    "Node-Zertifikat läuft ab": "Node certificate expiring",
    "Eigenes Zertifikat läuft ab": "Custom certificate expiring",
    # Stufen
    "Info": "Info",
    "Warnung": "Warning",
    "Kritisch": "Critical",
    # Texte der Meldungen
    "… und {0} weitere": "… and {0} more",
    "{0} WAF-Treffer auf {1}": "{0} WAF hits on {1}",
    "von Hand": "by hand",
    "dauerhaft": "permanently",
    "{0} Std.": "{0} h",
    "{0} gesperrt ({1}), {2}": "{0} banned ({1}), {2}",
    "{0}: kein Kontakt seit {1}": "{0}: no contact since {1}",
    "{0} meldet sich wieder": "{0} is reporting again",
    "keine Verbindung": "no connection",
    "{0}: Ziel antwortet nicht ({1})": "{0}: target not answering ({1})",
    "{0} ist wieder erreichbar": "{0} is reachable again",
    "Fehler": "Error",
    "Die laufende Config auf {0} weicht vom Controller ab": (
        "The running config on {0} differs from the controller"
    ),
    "Benutzer „{0}“ von {1}": "User “{0}” from {1}",
    "{0} – im Controller freigeben": "{0} – approve in the controller",
    "Node {0} ({1}) – Fingerabdruck vergleichen": "Node {0} ({1}) – compare the fingerprint",
    "Gerät unter Geräte verlängern": "Renew the device under Devices",
    "Unter Zertifizierungsstelle auf ein neues wechseln": (
        "Switch to a new one under Certificate authority"
    ),
    "Der Agent erneuert es selbst – meldet er sich noch?": (
        "The agent renews it itself – is it still reporting?"
    ),
    "Unter Zertifikate erneuern": "Renew under Certificates",
    "{0}: noch {1} Tage – {2}": "{0}: {1} days left – {2}",
    "Sicherung fehlgeschlagen: {0}": "Backup failed: {0}",
    "Einladung für {0} von {1}": "Invitation for {0} from {1}",
    "Testmeldung": "Test message",
    "Wenn das ankommt, klappen die Benachrichtigungen.": (
        "If this arrives, notifications are working."
    ),
}

_DICTS = {"en": EN}


def tr(lang: str, text: str, *args: object) -> str:
    """Text in die Sprache `lang` übersetzen; {0}, {1} … einsetzen."""
    out = _DICTS.get(lang, {}).get(text, text)
    return out.format(*args) if args else out
