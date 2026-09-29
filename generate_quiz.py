"""
Generiert ein neues "Idiotentest"-Quiz (7-9 Trickfragen inkl. Antworten
und kurzer Erklärung) für den Kanal "BrainBuzz". Nutzt die Anthropic API
(Claude), analog zum bestehenden Psychologie-Kanal-Skript.

TEST-MODUS: Solange TESTMODUS = True ist, wird das Test-Quiz nur BEIM
ALLERERSTEN LAUF generiert. Existiert bereits ein pending_quiz.json mit
"testmodus": true, wird es unverändert wiederverwendet - kein erneuter
Claude-Aufruf. So bleibt der Text über mehrere Testläufe hinweg exakt
gleich, damit generate_voiceover.py / compose_video.py ihrerseits Ton
cachen können (siehe dort) und das Video-Timing fair vergleichbar bleibt.
Vor dem echten Start auf TESTMODUS = False umstellen.

FRAGEN-HISTORIE: Damit sich Fragen nicht wiederholen, werden bereits
verwendete Fragen in fragen_historie.json gesammelt und Claude bei jeder
neuen Generierung mitgeteilt, damit es diese vermeidet.
"""

import os
import json
import random
from datetime import datetime
from anthropic import Anthropic

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# ==========================================================================
# TEST-MODUS: Auf False stellen, sobald der Kanal richtig loslegt!
# ==========================================================================
TESTMODUS = True
# ==========================================================================

KANAL_NAME = "BrainBuzz"
FORMAT_NAME = "Idiotentest"

MIN_FRAGEN = 7
MAX_FRAGEN = 9

FRAGEN_HISTORIE_DATEI = "fragen_historie.json"
ZAEHLER_DATEI = "video_zaehler.json"
QUIZ_DATEI = "pending_quiz.json"

# Wie viele zuletzt verwendete Fragen Claude als "bitte nicht wiederholen"
# mitgeteilt bekommt, und wie viele insgesamt in der Historie-Datei
# aufgehoben werden (Datei wächst sonst unbegrenzt).
HISTORIE_KONTEXT_ANZAHL = 60
HISTORIE_MAX_LAENGE = 300

MAX_GENERIERUNGS_VERSUCHE = 3

SYSTEM_PROMPT = f"""Du erstellst Fragen für ein TikTok-Format namens "{FORMAT_NAME}"
(Kanal: "{KANAL_NAME}"). Das sind KEINE reinen Wissensfragen, sondern
Trickfragen / Denkfallen: Sie klingen auf den ersten Blick simpel
(Mathe, Logik, Wortspiel, Alltagswissen), aber die meisten Zuschauer
tippen trotzdem die FALSCHE Antwort, weil der Wortlaut geschickt in die
Irre führt. Ziel: Der Zuschauer soll denken "Ach verdammt, stimmt!" und
das Video kommentieren/teilen.

ANFORDERUNGEN AN JEDE FRAGE:
- Kurz und in einem Satz laut vorlesbar (max. ca. 25 Wörter)
- Hat GENAU EINE eindeutig richtige Antwort (kein Interpretationsspielraum)
- Die Antwort ist kurz (im Idealfall 1-6 Wörter oder eine Zahl)
- Die "erklaerung" ist ein einziger, knackiger und leicht humorvoller
  Satz, der erklärt, WARUM man leicht auf die falsche Antwort reinfällt
- Abwechslungsreiche Kategorien mischen: Rechen-Trickfragen, Logik-
  Rätsel, Wortbedeutungs-Fallen, klassische "Idiotentest"-Klassiker,
  Alltagswissen mit Überraschungseffekt
- Keine Fragen, die reines Spezialwissen ohne Trick abfragen (das wäre
  ein normales Quiz, kein Idiotentest)
- Keine anstößigen, politischen oder sensiblen Themen

STRUKTUR DER GESAMTEN AUSGABE:
- "titel": kurzer, reißerischer Arbeitstitel für das Video (z.B.
  "Idiotentest: Schaffst du alle {{anzahl}} Fragen?")
- "intro": EIN kurzer, gesprochener Anmoderations-Satz, der Lust aufs
  Mitraten macht und die Fragenanzahl nennt
- "fragen": Liste mit genau {{anzahl}} Objekten, je
  {{"frage": "...", "antwort": "...", "erklaerung": "..."}}
- "outro": Ein kurzer, humorvoller Abschluss-Satz + Like-und-Folgen-
  Einladung, angelehnt an: "Lass ein Like da und folge {KANAL_NAME} für
  mehr Idiotentests." (Wortlaut darf leicht variiert werden)

Antworte NUR mit validem JSON, keine Markdown-Codeblöcke, kein Vorspann.
Format:
{{
  "titel": "...",
  "intro": "...",
  "fragen": [
    {{"frage": "...", "antwort": "...", "erklaerung": "..."}}
  ],
  "outro": "..."
}}
"""

TEST_QUIZ = {
    "titel": "Idiotentest: Schaffst du alle 7 Fragen?",
    "intro": "Sieben Fragen, die easy aussehen - aber die meisten tippen die falsche Antwort. Bereit?",
    "fragen": [
        {
            "frage": "Ein Bäcker hat 10 Brötchen. Er verkauft alle bis auf 4. Wie viele hat er noch?",
            "antwort": "4",
            "erklaerung": "'Bis auf 4' heißt, dass genau 4 übrig bleiben - viele rechnen trotzdem 10 minus 4."
        },
        {
            "frage": "Wie viele Monate haben 28 Tage?",
            "antwort": "Alle 12",
            "erklaerung": "Jeder Monat hat mindestens 28 Tage - nur der Februar hat NICHT mehr als 28."
        },
        {
            "frage": "Wenn du in einem dunklen Raum eine Kerze, eine Lampe und ein Streichholz hast, was zündest du zuerst an?",
            "antwort": "Das Streichholz",
            "erklaerung": "Ohne das Streichholz kannst du weder Kerze noch Lampe anzünden - logisch, aber leicht übersehen."
        },
        {
            "frage": "Maria ist die Tochter von Herrn Schulz. Herr Schulz ist der Vater von 5 Töchtern: Lala, Lele, Lili, Lolo. Wie heißt die fünfte Tochter?",
            "antwort": "Maria",
            "erklaerung": "Die Frage nennt Maria bereits am Anfang als Tochter - im Reim-Rhythmus der anderen Namen übersieht man das."
        },
        {
            "frage": "Ein Flugzeug stürzt exakt auf der Grenze zwischen Deutschland und Österreich ab. Wo begräbt man die Überlebenden?",
            "antwort": "Nirgends, Überlebende begräbt man nicht",
            "erklaerung": "Das Wort 'Überlebende' wird beim schnellen Zuhören überhört - man denkt an die Opfer."
        },
        {
            "frage": "Du überholst beim Radrennen den Zweitplatzierten. Auf welchem Platz bist du jetzt?",
            "antwort": "Auf Platz 2",
            "erklaerung": "Du übernimmst seinen Platz, nicht den des Ersten - viele antworten reflexartig 'Platz 1'."
        },
        {
            "frage": "Wie viele Tiere von jeder Art nahm Mose mit auf die Arche?",
            "antwort": "Keine, das war Noah",
            "erklaerung": "Die Arche gehört zur Geschichte von Noah - der Name 'Mose' schleicht sich unbemerkt ein."
        },
    ],
    "outro": "Ganz schön viele Fallen für einen Idiotentest, oder? Lass ein Like da und folge BrainBuzz für mehr Idiotentests.",
}


def historie_laden() -> list:
    if os.path.exists(FRAGEN_HISTORIE_DATEI):
        with open(FRAGEN_HISTORIE_DATEI, encoding="utf-8") as f:
            return json.load(f)
    return []


def historie_speichern(historie: list):
    historie = historie[-HISTORIE_MAX_LAENGE:]
    with open(FRAGEN_HISTORIE_DATEI, "w", encoding="utf-8") as f:
        json.dump(historie, f, ensure_ascii=False, indent=2)


def naechste_folgen_nummer() -> int:
    if os.path.exists(ZAEHLER_DATEI):
        with open(ZAEHLER_DATEI, encoding="utf-8") as f:
            zaehler_daten = json.load(f)
        nummer = zaehler_daten.get("anzahl", 0) + 1
    else:
        nummer = 1

    with open(ZAEHLER_DATEI, "w", encoding="utf-8") as f:
        json.dump({"anzahl": nummer}, f)

    return nummer


def generiere_quiz(anzahl_fragen: int, vermeiden: list) -> dict:
    vermeiden_text = ""
    if vermeiden:
        letzte = vermeiden[-HISTORIE_KONTEXT_ANZAHL:]
        vermeiden_text = (
            "\n\nDiese Fragen wurden bereits verwendet - bitte NICHT "
            "wiederholen und auch keine zu ähnlichen Varianten davon "
            "verwenden:\n" + "\n".join(f"- {f}" for f in letzte)
        )

    nutzer_prompt = (
        f"Erstelle jetzt ein neues Quiz mit genau {anzahl_fragen} Fragen "
        f"(Feld 'anzahl' im Titel-Beispiel oben meint {anzahl_fragen})."
        + vermeiden_text
    )

    for versuch in range(1, MAX_GENERIERUNGS_VERSUCHE + 1):
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": nutzer_prompt}],
        )
        text = response.content[0].text.strip()
        text = text.replace("```json", "").replace("```", "").strip()

        try:
            daten = json.loads(text)
            fragen = daten.get("fragen", [])
            if len(fragen) < anzahl_fragen:
                raise ValueError(f"nur {len(fragen)} statt {anzahl_fragen} Fragen erhalten")
            for f in fragen:
                if not f.get("frage") or not f.get("antwort") or not f.get("erklaerung"):
                    raise ValueError("Frage mit fehlendem Feld erhalten")
            daten["fragen"] = fragen[:anzahl_fragen]
            print(f"Quiz mit {len(daten['fragen'])} Fragen generiert (Versuch {versuch}/{MAX_GENERIERUNGS_VERSUCHE}).")
            return daten
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Ungültige Antwort (Versuch {versuch}/{MAX_GENERIERUNGS_VERSUCHE}): {e} - generiere erneut...")

    raise ValueError(
        f"Konnte nach {MAX_GENERIERUNGS_VERSUCHE} Versuchen kein valides "
        f"Quiz generieren. Bitte manuell prüfen."
    )


def vorhandenes_test_quiz_pruefen() -> bool:
    if not os.path.exists(QUIZ_DATEI):
        return False
    with open(QUIZ_DATEI, encoding="utf-8") as f:
        vorhandene_daten = json.load(f)
    return vorhandene_daten.get("testmodus") is True


def main():
    if TESTMODUS:
        if vorhandenes_test_quiz_pruefen():
            with open(QUIZ_DATEI, encoding="utf-8") as f:
                vorhandene_daten = json.load(f)
            print("⚠️  TEST-MODUS AKTIV - bestehendes Test-Quiz wird wiederverwendet, keine neue Generierung.")
            print(f"Quiz bleibt: {vorhandene_daten.get('titel')} (Folge #{vorhandene_daten.get('folge_nummer')})")
            return

        print("⚠️  TEST-MODUS AKTIV - generiere Test-Quiz einmalig (wird danach wiederverwendet)...")
        daten = dict(TEST_QUIZ)
        folge_nummer = 0
    else:
        anzahl_fragen = random.randint(MIN_FRAGEN, MAX_FRAGEN)
        historie = historie_laden()
        daten = generiere_quiz(anzahl_fragen, historie)
        historie.extend(f["frage"] for f in daten["fragen"])
        historie_speichern(historie)
        folge_nummer = naechste_folgen_nummer()

    daten["folge_nummer"] = folge_nummer
    daten["datum"] = datetime.now().strftime("%Y-%m-%d")
    daten["anzahl_fragen"] = len(daten["fragen"])
    daten["testmodus"] = TESTMODUS

    with open(QUIZ_DATEI, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=2)

    print(f"Quiz erstellt: {daten['titel']} (Folge #{daten['folge_nummer']}, {daten['anzahl_fragen']} Fragen)")
    print(f"Gespeichert unter: {QUIZ_DATEI}")


if __name__ == "__main__":
    main()
