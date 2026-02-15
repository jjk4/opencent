<!---<div align="center">
  <a href="#-opencent-english">🇺🇸 Read in English</a> | 
  <a href="#-opencent-deutsch">🇩🇪 Auf Deutsch lesen</a>
</div>--->

# 🚧 This Repo is currently under heavy development and not yet ready for production use! 🚧

<!---
<div id="-opencent-english"></div>

# 💸 OpenCent

**Your Finances. Your Data. Your Control.**

OpenCent is an **Open Source web application** for managing your personal finances. Similar to popular apps, but with one crucial difference: **Your data belongs to you.**

OpenCent runs on your own server (self-hosted), tracks your income and expenses across multiple accounts, and provides detailed analytics—without sharing any data with third parties.

## ✨ Features

TBD

---
---
--->
<div id="-opencent-deutsch"></div>

# 💸 OpenCent

**Deine Finanzen. Deine Daten. Deine Kontrolle.**

OpenCent ist eine **Open Source Webanwendung** zur Verwaltung deiner persönlichen Finanzen. Ähnlich wie populäre Apps, z.B. Finanzguru, aber mit einem entscheidenden Unterschied: **Deine Daten gehören dir.**

OpenCent läuft auf deinem eigenen Server (Self-Hosted), trackt deine Einnahmen und Ausgaben über mehrere Konten hinweg und bietet detaillierte Analysen – ganz ohne Datenweitergabe an Dritte.

## ✨ Funktionen

OpenCent wurde entwickelt, um echte Finanzströme realistisch abzubilden:

* **📊 Umfassendes Transaktionsmanagement**
    * Einfaches Erfassen von Einnahmen und Ausgaben
    * Unterscheide klar zwischen **echten Ausgaben** und **Umbuchungen** zwischen deinen eigenen Konten
* **↩️ Intelligente Rückerstattungen**
    * Du hast eine Rückzahlung für eine Retoure erhalten?
    * OpenCent verrechnet diese korrekt: Die Rückerstattung bläht dein "Einkommen" nicht künstlich auf und die ursprüngliche Ausgabe verfälscht deine Statistik nicht
* **💳 Multi-Account & Bargeld**
    * Verwalte beliebig viele Konten (Girokonto, Tagesgeld, Kreditkarte)
    * Führe ein dediziertes **Bargeldkonto**, um auch physische Ausgaben im Blick zu behalten
* **📈 Mächtige Analysen**
    * Visualisiere deine Geldflüsse mit interaktiven Diagrammen
    * Integrierte **Sankey-Diagramme** zeigen dir auf einen Blick, woher dein Geld kommt und wohin es fließt
* **🛡️ Privacy First**
    * Keine Tracker, keine Werbung, keine Datenweitergabe an Banken oder Analysefirmen

## 🚀 Installation

Du kannst OpenCent schnell und einfach via Docker installieren:

**1. Installiere Docker auf deinem System**

Folge dazu der Anleitung aus der Docker Dokumentation: https://docs.docker.com/engine/install/

**2. Lade die docker-compose.yml und .env Dateiherunter**

```bash
curl -O https://raw.githubusercontent.com/jjk4/opencent/refs/heads/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/jjk4/opencent/refs/heads/main/.env.docker.example -o .env
```

**3. Passe die .env Datei an**

Öffne die `.env` Datei und passe den Schlüssel `SECRET_KEY` an. Du kannst einen sicheren Schlüssel mit folgendem Befehl generieren:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```
Passe außerdem das Datenbankpasswort `DATABASE_PASSWORD` an.

**4. Starte die Anwendung**

```bash
docker-compose up -d
```

**5. Zugriff auf OpenCent**

Öffne deinen Browser und gehe zu `http://IP_DEINES_SERVERS:8000`. Du solltest den Einrichtungsassistent von OpenCent sehen.


---

## 🛠️ Tech Stack

* **Backend:** Python, Django
* **Database:** PostgreSQL (Docker) / SQLite (Dev)
* **Frontend:** HTML5, CSS3, JavaScript, ApexCharts, Bootstrap5
* **Container:** Docker & Docker Compose

## 📄 License

Distributed under the GNU General Public License v3.0 License. See `LICENSE` for more information.