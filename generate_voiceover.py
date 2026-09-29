"""
Erzeugt alle Sprachschnipsel für das Quiz über die Azure Text-to-Speech
API: Intro, pro Frage ein "Frage"-Schnipsel und ein "Antwort"-Schnipsel,
sowie das Outro. Jeder Schnipsel wird als eigene mp3-Datei gespeichert -
compose_video.py berechnet daraus (über die tatsächliche Audio-Dauer via
ffprobe) das exakte Timing der Text-Einblendungen. Es gibt daher KEINE
Transkription/Whisper-Schritt wie im Original-Kanal - das Timing ist
hier von Anfang an exakt bekannt.

TEST-CACHE: Solange pending_quiz.json "testmodus": true enthält, wird
der gesamte output/audio/-Ordner in test_cache/quiz_audio/
zwischengespeichert und bei künftigen Testläufen von dort wiederverwendet
statt erneut bei Azure angefragt zu werden.
"""

import os
import json
import shutil
import subprocess
import requests

AZURE_SPEECH_KEY = os.environ["AZURE_SPEECH_KEY"]
AZURE_SPEECH_REGION = os.environ["AZURE_SPEECH_REGION"]

STIMME = "de-DE-FlorianMultilingualNeural"
TTS_URL = f"https://{AZURE_SPEECH_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"

AUDIO_ORDNER = "output/audio"

TEST_CACHE_ORDNER = "test_cache/quiz_audio"


def escape_fuer_ssml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def ssml_erstellen(text: str) -> str:
    return (
        f'<speak version="1.0" xml:lang="de-DE">'
        f'<voice xml:lang="de-DE" name="{STIMME}">'
        f'{escape_fuer_ssml(text)}'
        f'</voice></speak>'
    )


def schnipsel_generieren(text: str, ziel_pfad: str):
    ssml = ssml_erstellen(text)
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "audio-24khz-96kbitrate-mono-mp3",
        "User-Agent": "idiotentest-agent",
    }
    r = requests.post(TTS_URL, headers=headers, data=ssml.encode("utf-8"))
    if not r.ok:
        print(f"Azure TTS Antwort (Status {r.status_code}): {r.text}")
    r.raise_for_status()

    with open(ziel_pfad, "wb") as f:
        f.write(r.content)


def alle_schnipsel_erstellen(daten: dict):
    os.makedirs(AUDIO_ORDNER, exist_ok=True)

    print("Generiere Intro...")
    schnipsel_generieren(daten["intro"], os.path.join(AUDIO_ORDNER, "intro.mp3"))

    for i, frage in enumerate(daten["fragen"], start=1):
        print(f"Generiere Frage {i}/{len(daten['fragen'])}...")
        frage_text = f"Frage {i}: {frage['frage']}"
        schnipsel_generieren(frage_text, os.path.join(AUDIO_ORDNER, f"frage_{i}.mp3"))

        print(f"Generiere Antwort {i}/{len(daten['fragen'])}...")
        antwort_text = f"Die richtige Antwort: {frage['antwort']}."
        schnipsel_generieren(antwort_text, os.path.join(AUDIO_ORDNER, f"antwort_{i}.mp3"))

    print("Generiere Outro...")
    schnipsel_generieren(daten["outro"], os.path.join(AUDIO_ORDNER, "outro.mp3"))


def main():
    with open("pending_quiz.json", encoding="utf-8") as f:
        daten = json.load(f)

    testmodus = daten.get("testmodus", False)

    if testmodus and os.path.isdir(TEST_CACHE_ORDNER):
        print("⚠️  TEST-MODUS: nutze gecachte Audio-Schnipsel (keine neuen Azure-Anfragen).")
        if os.path.isdir(AUDIO_ORDNER):
            shutil.rmtree(AUDIO_ORDNER)
        shutil.copytree(TEST_CACHE_ORDNER, AUDIO_ORDNER)
    else:
        alle_schnipsel_erstellen(daten)
        if testmodus:
            os.makedirs("test_cache", exist_ok=True)
            if os.path.isdir(TEST_CACHE_ORDNER):
                shutil.rmtree(TEST_CACHE_ORDNER)
            shutil.copytree(AUDIO_ORDNER, TEST_CACHE_ORDNER)
            print("Test-Audio im Cache gespeichert für zukünftige Testläufe.")

    anzahl_dateien = len(os.listdir(AUDIO_ORDNER))
    print(f"Alle Audio-Schnipsel bereit ({anzahl_dateien} Dateien in {AUDIO_ORDNER}/).")


if __name__ == "__main__":
    main()
