"""
SCHRITT 2 von 2: Erstellt das fertige Video aus pending_quiz.json.

Wird NICHT automatisch ausgeführt, sondern nur, wenn du ihn manuell über
den "Run workflow"-Button in GitHub Actions startest (Workflow
"2 - Video erstellen"). So hast du vorher die Chance, pending_quiz.json
im Repository zu prüfen und bei Bedarf zu bearbeiten.

ABLAUF (2 Schritte):
1. Audio-Schnipsel für Intro/Fragen/Antworten/Outro erzeugen (Azure TTS)
2. Hintergrundvideo vorbereiten + alle Text-Einblendungen + Ton
   zusammensetzen (ffmpeg)
"""

import json
import generate_voiceover
import compose_video


def main():
    with open("pending_quiz.json", encoding="utf-8") as f:
        daten = json.load(f)
    print(f"Erstelle Video für: {daten['titel']} ({daten['anzahl_fragen']} Fragen)")

    print("\n=== Schritt 1/2: Audio-Schnipsel erzeugen (Azure TTS) ===")
    generate_voiceover.main()

    print("\n=== Schritt 2/2: Hintergrund + Text-Overlays + Ton zusammensetzen ===")
    compose_video.video_zusammensetzen()

    print("\nFertig! Video liegt unter output/video_final.mp4")
    print("Lade es aus dem GitHub Actions Run als Artifact herunter und")
    print("poste es manuell in der TikTok-App.")


if __name__ == "__main__":
    main()
