"""
SCHRITT 1 von 2: Generiert nur das Quiz (Fragen + Antworten) und stoppt
dann. Läuft über den Workflow "1 - Quiz generieren" (manuell oder nach
Zeitplan, siehe .github/workflows/1_generate.yml).

Erstellt danach ein GitHub Issue zur Prüfung/Freigabe. Video-Erstellung
passiert NICHT automatisch, sondern erst in Schritt 2, nachdem du
pending_quiz.json geprüft/bearbeitet hast (siehe README.md).
"""

import generate_quiz

if __name__ == "__main__":
    generate_quiz.main()
