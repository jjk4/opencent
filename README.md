<div align="center">
  <a href="#-opencent-english">🇺🇸 Read in English</a> | 
  <a href="#-opencent-deutsch">🇩🇪 Auf Deutsch lesen</a>
</div>

---

<div id="-opencent-english"></div>

# 💸 OpenCent

**Your Finances. Your Data. Your Control.**

OpenCent is an **Open Source web application** for managing your personal finances. Similar to popular apps, but with one crucial difference: **Your data belongs to you.**

OpenCent runs on your own server (self-hosted), tracks your income and expenses across multiple accounts, and provides detailed analytics—without sharing any data with third parties.

## ✨ Features

OpenCent is designed to reflect real-world financial flows realistically:

* **📊 Comprehensive Transaction Management**
    * Easily record income and expenses.
    * Clearly distinguish between **real expenses** and **internal transfers** between your own accounts.
* **↩️ Smart Refunds**
    * Received a refund for a return? Mark transactions specifically as refunds.
    * OpenCent calculates this correctly: The refund does not artificially inflate your "Income," and the original transaction does not distort your expense statistics.
* **💳 Multi-Account & Cash**
    * Manage unlimited accounts (Checking, Savings, Credit Cards).
    * Maintain a dedicated **Cash Account** to keep track of physical spending.
* **📈 Powerful Analytics**
    * Visualize your money flow with interactive charts.
    * Integrated **Sankey Diagrams** show you at a glance where your money comes from and where it goes.
* **🛡️ Privacy First**
    * No trackers, no ads, no data sharing with banks or analytics firms.

## 🚀 Installation

You can run OpenCent quickly via Docker or install it manually.


### Option A: Docker (Recommended)

TBD

### Option B: Manual Installation (Django)

1.  **Clone and enter directory:**
    ```bash
    git clone [https://github.com/jjk4/opencent.git](https://github.com/jjk4/opencent.git)
    cd opencent
    ```
2.  **Create & activate virtual environment:**
    ```bash
    python -m venv .venv
    # Windows
    .venv\Scripts\activate
    # Mac/Linux
    source .venv/bin/activate
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Migrate database:**
    ```bash
    python manage.py migrate
    ```
5.  **Run Server:**
    ```bash
    python manage.py runserver
    ```

---
---

<div id="-opencent-deutsch"></div>

# 💸 OpenCent (Deutsch)

**Deine Finanzen. Deine Daten. Deine Kontrolle.**

OpenCent ist eine **Open Source Webanwendung** zur Verwaltung deiner persönlichen Finanzen. Ähnlich wie populäre Apps, aber mit einem entscheidenden Unterschied: **Deine Daten gehören dir.**

OpenCent läuft auf deinem eigenen Server (Self-Hosted), trackt deine Einnahmen und Ausgaben über mehrere Konten hinweg und bietet detaillierte Analysen – ganz ohne Datenweitergabe an Dritte.

## ✨ Funktionen

OpenCent wurde entwickelt, um echte Finanzströme realistisch abzubilden:

* **📊 Umfassendes Transaktionsmanagement**
    * Erfasse Einnahmen und Ausgaben mühelos.
    * Unterscheide klar zwischen **echten Ausgaben** und **Umbuchungen** zwischen deinen eigenen Konten.
* **↩️ Intelligente Rückerstattungen**
    * Habe eine Rückzahlung für eine Retoure erhalten? Markiere Transaktionen als Rückerstattung.
    * OpenCent verrechnet diese korrekt: Die Rückerstattung bläht dein "Einkommen" nicht künstlich auf und die ursprüngliche Ausgabe verfälscht deine Statistik nicht.
* **💳 Multi-Account & Bargeld**
    * Verwalte beliebig viele Konten (Girokonto, Tagesgeld, Kreditkarte).
    * Führe ein dediziertes **Bargeldkonto**, um auch physische Ausgaben im Blick zu behalten.
* **📈 Mächtige Analysen**
    * Visualisiere deine Geldflüsse mit interaktiven Diagrammen.
    * Integrierte **Sankey-Diagramme** zeigen dir auf einen Blick, woher dein Geld kommt und wohin es fließt.
* **🛡️ Privacy First**
    * Keine Tracker, keine Werbung, keine Datenweitergabe an Banken oder Analysefirmen.

## 🚀 Installation

Du kannst OpenCent entweder schnell via Docker starten oder manuell installieren.

### Option A: Docker (Empfohlen)

TBD

### Option B: Manuelle Installation (Django)

1.  **Repository klonen:**
    ```bash
    git clone [https://github.com/jjk4/opencent.git](https://github.com/jjk4/opencent.git)
    cd opencent
    ```
2.  **Virtuelle Umgebung erstellen & aktivieren:**
    ```bash
    python -m venv .venv
    # Windows
    .venv\Scripts\activate
    # Mac/Linux
    source .venv/bin/activate
    ```
3.  **Abhängigkeiten installieren:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Datenbank migrieren:**
    ```bash
    python manage.py migrate
    ```
5.  **Server starten:**
    ```bash
    python manage.py runserver
    ```

---

## 🛠️ Tech Stack

* **Backend:** Python, Django
* **Database:** PostgreSQL (Docker) / SQLite (Dev)
* **Frontend:** HTML5, CSS3, JavaScript, ApexCharts, Bootstrap5
* **Container:** Docker & Docker Compose

## 📄 License

Distributed under the GNU General Public License v3.0 License. See `LICENSE` for more information.