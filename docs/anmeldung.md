# Anmeldung der Admins und LDAP

Einstellungen › **Anmeldung** und › **LDAP**. Die Anmeldung betrifft nur die Admins der
Oberfläche. Personen mit Zugriff auf Hosts melden sich nicht an – sie haben Gerätezertifikate.

Das **Admin-Gerätezertifikat** (Einstellungen › Allgemein › Zugang zur Oberfläche) bleibt bei
jedem Anmeldeweg die erste Hürde: Ohne Admin-Gerät kommt niemand bis zur Anmeldeseite.

## Passkeys

Anmelden per Fingerabdruck, Gesicht, PIN des Geräts oder Sicherheitsschlüssel (YubiKey …) –
ohne Benutzername und Passwort, nicht phishbar.

- Anlegen: Einstellungen › Anmeldung › *Passkey hinzufügen* (angemeldet, für das eigene Konto).
  Mehrere Passkeys pro Konto sind möglich (z. B. Laptop und Sicherheitsschlüssel als Ersatz).
- Anmelden: *Mit Passkey anmelden* auf der Anmeldeseite.
- Passkeys gelten nur für die Controller-Domain (`TESSERACT_DOMAIN`). Nach einem Umzug auf
  eine andere Domain neu anlegen. Sie brauchen HTTPS (lokal geht auch `localhost`).
- Gespeichert wird nur der öffentliche Schlüssel; Nutzerprüfung am Gerät ist Pflicht.

## SSO über OpenID Connect

Beim Anbieter einen **Client** (vertraulich, „Authorization Code“) anlegen und als
Weiterleitungs-Adresse eintragen, was die Seite anzeigt:

```
https://<TESSERACT_DOMAIN>/api/auth/sso/callback
```

In Tesseract: Aussteller (Issuer), Client-ID, Client-Secret und **wer Admin wird** – Mitglied
einer Gruppe (Claim `groups`) oder eine der freigegebenen E-Mail-Adressen. Beim Speichern prüft
Tesseract die Discovery des Anbieters.

| Anbieter | Issuer | Hinweise |
|---|---|---|
| Authelia | `https://auth.beispiel.de` | Client unter `identity_providers.oidc.clients`, `scopes: [openid, profile, email, groups]`, `token_endpoint_auth_method: client_secret_basic` |
| Keycloak | `https://sso.beispiel.de/realms/<realm>` | Client-Scope mit „Group Membership“-Mapper (Claim `groups`, ohne vollen Pfad) |
| Authentik | `https://auth.beispiel.de/application/o/<slug>/` | OAuth2/OpenID-Provider, Scope `groups` liefert die Gruppen |
| Dex | `https://dex.beispiel.de/dex` | Scope `groups`; Gruppen kommen aus dem Connector (z. B. LDAP) |

- Ablauf: Authorization Code mit PKCE, `state` und `nonce`; das ID-Token wird über die JWKS des
  Anbieters geprüft (Signatur, Aussteller, Empfänger, Ablauf, Nonce). Fehlen die Gruppen im
  ID-Token, fragt Tesseract den Userinfo-Endpunkt.
- Beim ersten Anmelden entsteht ein Admin-Konto ohne Passwort (Benutzername aus
  `preferred_username`). Es meldet sich nur über SSO an – oder über einen Passkey, den es
  selbst anlegt.
- Jede Anmeldung steht im Audit-Log (`login` mit Methode, abgelehnte als `login_failed`).

## Passwort-Anmeldung abschalten

Sind SSO oder ein Passkey eingerichtet, lässt sich die Anmeldung mit Passwort abschalten.
Tesseract verhindert, dass der letzte Weg hinein verschwindet. Notausgang auf dem Controller,
falls der SSO-Anbieter ausfällt:

```bash
docker compose exec tesseract tesseract admin password-login on
```

## LDAP-Abgleich für Personen und Gruppen

Personen und Gruppen aus LDAP übernehmen und regelmäßig abgleichen (Standard: stündlich).

- **Übernommen werden:** Name, E-Mail, Sperre und die Mitglieder der LDAP-Gruppen. Freigaben
  können dann an LDAP-Gruppen hängen. Geräte und Zertifikate verwaltet weiter Tesseract.
- **Wer in LDAP deaktiviert ist** (Filter, z. B. `(nsAccountLock=TRUE)` oder bei AD
  `(userAccountControl:1.2.840.113556.1.4.803:=2)`) **oder aus LDAP verschwindet**, wird
  gesperrt; mit „Geräte widerrufen“ (Standard) auch alle Zertifikate – endgültig. Wird die Person
  in LDAP wieder aktiv, ist sie in Tesseract entsperrt, braucht aber neue Geräte.
- **Schutz vor Fehlkonfiguration:** Liefert LDAP keine einzige Person, obwohl schon welche
  verknüpft sind (falscher Filter, falsche Suchbasis), ändert der Abgleich nichts.
- **Vorschau** zeigt vorher, was neu, geändert oder gesperrt würde.
- Eine von Hand angelegte Person mit gleichem Namen wird verknüpft statt doppelt angelegt.
  Die eingebaute Gruppe „Admin“ und Tesseract-eigene Gruppen bleiben unberührt.
- Vorlagen für OpenLDAP/lldap, Active Directory und FreeIPA/389ds. Verbindung per `ldaps://`
  oder `ldap://` mit STARTTLS; das Bind-Passwort liegt verschlüsselt in der Datenbank.

## Schnittstelle

| Methode & Pfad | Zweck |
|---|---|
| `GET /api/auth/methods` | Anmeldewege für die Login-Seite (öffentlich) |
| `GET /api/auth/sso/start` · `GET /api/auth/sso/callback` | SSO-Anmeldung |
| `POST /api/auth/passkey/options` · `POST /api/auth/passkey/login` | Anmelden mit Passkey |
| `GET/POST /api/auth/passkeys` · `POST /api/auth/passkeys/options` · `DELETE /api/auth/passkeys/{id}` | eigene Passkeys |
| `GET/PUT /api/settings/admin-auth` | SSO und Passwort-Anmeldung |
| `GET/PUT /api/settings/ldap` · `POST /api/settings/ldap/sync[?dry_run=true]` | LDAP |
