# Idiotentest-TikToks (Kanal "BrainBuzz")

Automatisierte Pipeline für Quiz-/"Idiotentest"-Kurzvideos, im gleichen
2-Schritte-Prinzip wie euer bestehender Psychologie-Kanal:

1. **Quiz generieren** (automatisch/manuell) → landet als GitHub Issue
   zur Prüfung/Freigabe
2. **Video erstellen** (nur manuell, nach deiner Freigabe) → fertiges
   Video als Download-Artifact

Es passiert **nichts automatisch auf TikTok** - der Upload bleibt
bewusst ein manueller letzter Schritt.

---

## Wie das Video aussieht

- Hintergrund: ein Video-Loop (von dir bereitgestellt, z.B. Drohnen-
  aufnahmen, Zeitraffer, o.ä.)
- Oben: Badge mit dem Format-Namen ("Idiotentest")
- Links: nummerierte Liste 1-N, die aktuelle Frage wird farblich
  hervorgehoben
- Mitte: die jeweilige Frage als Text, danach ein 3-2-1-Countdown,
  dann die Auflösung (grün eingeblendet)
- Unten: Logo/Kanalname
- Tonspur: KI-Stimme liest Intro, jede Frage und jede Antwort/Erklärung
  vor

---

## Einmalige Einrichtung

### 1. Neues GitHub-Repository anlegen

Ich kann selbst kein Repository in deinem GitHub-Account erstellen (dafür
fehlt mir der Zugriff). Du legst es in 2 Minuten selbst an:

1. Auf github.com → "New repository" → Name vergeben (z.B.
   `brainbuzz-idiotentest`) → "Create repository" (leer lassen, ohne
   README/License, die kommen gleich mit).
2. Diesen kompletten Ordner (den du gerade heruntergeladen hast) in das
   leere Repo pushen:
   ```bash
   cd idiotentest-tiktok
   git init
   git add .
   git commit -m "Initiales Setup"
   git branch -M main
   git remote add origin https://github.com/DEIN-NAME/brainbuzz-idiotentest.git
   git push -u origin main
   ```
   (Alternativ, falls installiert: `gh repo create brainbuzz-idiotentest --private --source=. --push`)

### 2. Secrets hinterlegen

Im neuen Repo unter **Settings → Secrets and variables → Actions → New
repository secret**:

| Secret | Wofür |
|---|---|
| `ANTHROPIC_API_KEY` | Claude generiert die Fragen/Antworten |
| `AZURE_SPEECH_KEY` | Azure Text-to-Speech (Sprachausgabe) |
| `AZURE_SPEECH_REGION` | z.B. `westeurope` |

### 3. Eigene Hintergrundvideos ergänzen

Lege deine Clips in `assets/backgrounds/` ab (siehe
`assets/backgrounds/README.md` für Details/Lizenzhinweise). Ohne
eigene Clips läuft die Pipeline trotzdem (einfarbiger Ersatz-
Hintergrund), das siehst du dem fertigen Video aber deutlich an.

### 4. Optional: eigenes Logo

`assets/logo.png` ablegen (transparentes PNG) für ein Logo-Overlay -
siehe `assets/LOGO_README.md`. Ohne Logo wird automatisch der
Kanalname als Text eingeblendet.

---

## Täglicher Ablauf

1. Workflow **"1 - Quiz generieren"** läuft automatisch (oder manuell
   über "Run workflow") und erstellt ein GitHub Issue mit allen Fragen,
   Antworten und Erklärungen zur Prüfung.
2. `pending_quiz.json` im Browser prüfen/anpassen (z.B. eigene
   Formulierung einbauen - das ist wichtig, damit der Content nicht als
   reiner unbearbeiteter KI-Output gilt).
3. Workflow **"2 - Video erstellen"** manuell starten.
4. Nach ein paar Minuten: fertiges Video unter "Artifacts" im
   Workflow-Lauf herunterladen.
5. Video manuell in der TikTok-App hochladen.
6. Issue schließen.

---

## Lokal testen

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # echte Keys eintragen
export $(cat .env | xargs) # oder python-dotenv verwenden
sudo apt-get install ffmpeg fonts-dejavu-core   # oder via brew/choco

python 1_generate.py       # erstellt/aktualisiert pending_quiz.json
python 2_create_video.py   # erstellt output/video_final.mp4
```

Solange `TESTMODUS = True` in `generate_quiz.py` gesetzt ist, wird
immer dasselbe Test-Quiz verwendet (kein Claude-Call) und Audio wird
in `test_cache/` zwischengespeichert - so lässt sich das Video-Timing/
Layout beliebig oft neu rendern, ohne API-Kosten oder wechselnden Text.
**Vor dem echten Start `TESTMODUS = False` setzen.**

---

## Anpassungen

Alles Wichtige steckt in wenigen Konstanten:

- `generate_quiz.py`: `KANAL_NAME`, `FORMAT_NAME`, `MIN_FRAGEN`/
  `MAX_FRAGEN`, der komplette `SYSTEM_PROMPT` (Stil der Fragen)
- `compose_video.py`: Farben (`FARBE_AKZENT`, `FARBE_COUNTDOWN`,
  `FARBE_RICHTIG`), Timing (`COUNTDOWN_DAUER`, Pausen), Layout der
  Nummern-Liste (`LISTE_X`, `LISTE_Y_START`, `LISTE_ZEILENHOEHE`)
- `generate_voiceover.py`: `STIMME` (Azure-Stimmenname)

## Struktur

```
1_generate.py          Schritt 1: nur Quiz generieren
generate_quiz.py        Claude-Aufruf, Historie, Test-Modus
2_create_video.py      Schritt 2: Audio + Video erstellen
generate_voiceover.py   Azure TTS pro Frage/Antwort/Intro/Outro
compose_video.py        Zeitleiste berechnen, ffmpeg-Overlay-Video bauen
assets/backgrounds/     Deine Hintergrund-Clips (nicht mitgeliefert)
assets/logo.png         Dein optionales Logo (nicht mitgeliefert)
pending_quiz.json       Aktuelles/Beispiel-Quiz
fragen_historie.json    Bereits verwendete Fragen (Wiederholungsschutz)
video_zaehler.json      Fortlaufende Folgen-Nummer
```
