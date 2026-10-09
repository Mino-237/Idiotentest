"""
Setzt das finale Quiz-Video zusammen aus:
1. Einem Hintergrundvideo (aus assets/backgrounds/, zufällig gewählt,
   auf die Gesamtlänge geloopt und auf 1080x1920 zugeschnitten). Liegt
   dort keine Datei, wird ersatzweise ein einfarbiger Hintergrund erzeugt
   (Video-Pipeline bricht also nicht ab, Qualität leidet aber sichtbar -
   siehe README.md für Bezugsquellen).
2. Einem Titel-Badge ("Idiotentest", dauerhaft eingeblendet)
3. Einer nummerierten Liste (1..N) am linken Rand, deren aktuelle Nummer
   während der jeweiligen Frage farblich hervorgehoben wird
4. Pro Frage: Fragetext, ein 3-2-1 Countdown und die Antwort-Einblendung
5. Einem Logo/Kanalnamen-Overlay unten (assets/logo.png, optional)
6. Der Tonspur aus output/audio/*.mp3, exakt zusammengesetzt aus den
   echten Audio-Längen (ffprobe) - kein Schätzen, kein Transkribieren.

WICHTIG: Die Zeiten für alle Text-Einblendungen werden AUSSCHLIESSLICH
aus den tatsächlichen Audiolängen berechnet (siehe zeitleiste_berechnen).
Ändert sich z.B. die Stimme/Sprechgeschwindigkeit, passt sich das Timing
automatisch an.
"""

import os
import json
import random
import subprocess
import textwrap

BREITE, HOEHE = 1080, 1920
FONT_PFAD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

HINTERGRUND_ORDNER = "assets/backgrounds"
LOGO_PFAD = "assets/logo.png"
AUDIO_ORDNER = "output/audio"
HINTERGRUND_VIDEO = "output/background.mp4"
FERTIGES_VIDEO = "output/video_final.mp4"

FORMAT_NAME = "Idiotentest"
KANAL_NAME = "BrainBuzz"

FARBE_AKZENT = "0x9B5DE5"      # Lila-Badge/Highlight (wie Vorlage)
FARBE_COUNTDOWN = "0xFFD24D"   # Gelb-orange
FARBE_RICHTIG = "0x2ECC71"     # Grün für Antwort-Reveal

# --- Timing-Konstanten (alle in Sekunden) ---
PAUSE_NACH_INTRO = 0.5
PAUSE_VOR_COUNTDOWN = 0.3
COUNTDOWN_DAUER = 3.0          # 3 Ziffern à 1 Sekunde
PAUSE_VOR_ANTWORT = 0.2
ANTWORT_HALTE_DAUER = 1.4      # wie lange die Antwort nach Sprechende noch stehen bleibt
PAUSE_NACH_ANTWORT = 0.5

# Nach dieser Fragen-Nummer wird (falls im Quiz vorhanden) der
# "Zwischen-CTA" eingeblendet (z.B. "Wenn du bis hier geschafft hast,
# lass ein Like da").
ZWISCHEN_CTA_NACH_FRAGE = 4
PAUSE_VOR_ZWISCHEN_CTA = 0.3
PAUSE_NACH_ZWISCHEN_CTA = 0.5

# Mindestlänge des fertigen Videos in Sekunden. Wird die durch Intro,
# Fragen, Antworten & Pausen berechnete Gesamtdauer unterschritten (z.B.
# weil wenige/kurze Fragen generiert wurden), wird automatisch pro Frage
# etwas mehr "Antwort bleibt stehen"-Zeit ergänzt, um diese Länge zu
# erreichen. 60s = Mindestvorgabe für TikTok Creator Rewards. Auf 0
# setzen, um die Auto-Verlängerung zu deaktivieren.
MINDEST_GESAMTDAUER = 60.0

# --- Layout ---
# Von oben nach unten: Titel-Badge -> Fragetext (FRAGE_Y) -> Nummern-
# Liste. Die Antwort jeder Frage wird neben ihrer Nummer eingeblendet und
# bleibt bis zum Videoende stehen. Der 3-2-1-Countdown läuft in der Zeile
# der aktuellen Frage, genau dort, wo danach die Antwort erscheint.
FRAGE_Y = 250
LISTE_X = 55
LISTE_Y_START = 720
LISTE_ZEILENHOEHE = 90
LISTE_SCHRIFT = 54
ANTWORT_X = 190
ANTWORT_MAX_BREITE = 830       # verfügbare Pixelbreite für die Antwort
ANTWORT_MAX_SCHRIFT = 54
ANTWORT_MIN_SCHRIFT = 30
COUNTDOWN_SCHRIFT = 66


def audio_dauer(pfad: str) -> float:
    befehl = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        pfad,
    ]
    ergebnis = subprocess.run(befehl, capture_output=True, text=True, check=True)
    return float(ergebnis.stdout.strip())


def text_fuer_drawtext_escapen(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\u2019")
        .replace("%", "\\%")
    )


def antwort_schriftgroesse(text: str) -> int:
    """Wählt die größte Schrift (bis ANTWORT_MAX_SCHRIFT), bei der die
    Antwort noch in eine Zeile neben der Nummer passt. DejaVu Sans Bold
    ist im Schnitt ca. 0.65 x Schriftgröße pro Zeichen breit."""
    laenge = max(1, len(text))
    passend = int(ANTWORT_MAX_BREITE / (0.65 * laenge))
    return max(ANTWORT_MIN_SCHRIFT, min(ANTWORT_MAX_SCHRIFT, passend))


def text_umbrechen_und_escapen(text: str, breite: int = 26) -> str:
    zeilen = textwrap.wrap(text, width=breite)
    return "\n".join(text_fuer_drawtext_escapen(z) for z in zeilen)


# ---------------------------------------------------------------------
# 1. Zeitleiste berechnen
# ---------------------------------------------------------------------

def zeitleiste_berechnen(anzahl_fragen: int, zusatz_halte_dauer: float = 0.0):
    """Liefert (fenster_pro_frage, audio_segmente, gesamt_dauer).

    fenster_pro_frage: Liste von dicts mit den Start-/End-Zeitpunkten
    jeder Einblendung (frage_start, countdown_start, countdown_ende,
    antwort_start, fenster_ende).

    audio_segmente: Liste von (typ, wert) - typ ist "datei" (wert = Pfad)
    oder "stille" (wert = Dauer in Sekunden), in der Reihenfolge, in der
    sie später zur finalen Tonspur zusammengesetzt werden.

    zusatz_halte_dauer: wird zusätzlich zu ANTWORT_HALTE_DAUER pro Frage
    als Stille eingefügt - genutzt, um die Gesamtdauer bei Bedarf auf
    MINDEST_GESAMTDAUER zu strecken (siehe video_zusammensetzen).
    """
    halte_dauer = ANTWORT_HALTE_DAUER + zusatz_halte_dauer
    audio_segmente = []
    fenster_liste = []
    zwischen_cta_fenster = None
    t = 0.0

    intro_pfad = os.path.join(AUDIO_ORDNER, "intro.mp3")
    if os.path.exists(intro_pfad):
        dauer = audio_dauer(intro_pfad)
        audio_segmente.append(("datei", intro_pfad))
        t += dauer
        audio_segmente.append(("stille", PAUSE_NACH_INTRO))
        t += PAUSE_NACH_INTRO

    for i in range(1, anzahl_fragen + 1):
        frage_pfad = os.path.join(AUDIO_ORDNER, f"frage_{i}.mp3")
        antwort_pfad = os.path.join(AUDIO_ORDNER, f"antwort_{i}.mp3")

        frage_start = t
        frage_dauer = audio_dauer(frage_pfad)
        audio_segmente.append(("datei", frage_pfad))
        t += frage_dauer

        audio_segmente.append(("stille", PAUSE_VOR_COUNTDOWN))
        t += PAUSE_VOR_COUNTDOWN

        countdown_start = t
        audio_segmente.append(("stille", COUNTDOWN_DAUER))
        t += COUNTDOWN_DAUER
        countdown_ende = t

        audio_segmente.append(("stille", PAUSE_VOR_ANTWORT))
        t += PAUSE_VOR_ANTWORT

        antwort_start = t
        antwort_dauer = audio_dauer(antwort_pfad)
        audio_segmente.append(("datei", antwort_pfad))
        t += antwort_dauer

        audio_segmente.append(("stille", halte_dauer))
        t += halte_dauer
        fenster_ende = t

        audio_segmente.append(("stille", PAUSE_NACH_ANTWORT))
        t += PAUSE_NACH_ANTWORT

        fenster_liste.append({
            "frage_start": frage_start,
            "countdown_start": countdown_start,
            "countdown_ende": countdown_ende,
            "antwort_start": antwort_start,
            "fenster_ende": fenster_ende,
        })

        if i == ZWISCHEN_CTA_NACH_FRAGE:
            zwischen_cta_pfad = os.path.join(AUDIO_ORDNER, "zwischen_cta.mp3")
            if os.path.exists(zwischen_cta_pfad):
                audio_segmente.append(("stille", PAUSE_VOR_ZWISCHEN_CTA))
                t += PAUSE_VOR_ZWISCHEN_CTA

                zwischen_cta_start = t
                audio_segmente.append(("datei", zwischen_cta_pfad))
                t += audio_dauer(zwischen_cta_pfad)
                zwischen_cta_fenster = {"start": zwischen_cta_start, "ende": t}

                audio_segmente.append(("stille", PAUSE_NACH_ZWISCHEN_CTA))
                t += PAUSE_NACH_ZWISCHEN_CTA

    outro_pfad = os.path.join(AUDIO_ORDNER, "outro.mp3")
    if os.path.exists(outro_pfad):
        audio_segmente.append(("datei", outro_pfad))
        t += audio_dauer(outro_pfad)

    return fenster_liste, audio_segmente, t, zwischen_cta_fenster


# ---------------------------------------------------------------------
# 2. Hintergrundvideo vorbereiten
# ---------------------------------------------------------------------

def hintergrund_vorbereiten(gesamt_dauer: float) -> str:
    kandidaten = []
    if os.path.isdir(HINTERGRUND_ORDNER):
        kandidaten = [
            os.path.join(HINTERGRUND_ORDNER, f)
            for f in os.listdir(HINTERGRUND_ORDNER)
            if f.lower().endswith((".mp4", ".mov", ".webm", ".m4v"))
        ]

    if not kandidaten:
        print(
            "⚠️  Kein Hintergrundvideo in assets/backgrounds/ gefunden - "
            "erzeuge ersatzweise einen einfarbigen Hintergrund. Bitte "
            "eigene Clips ergänzen (siehe README.md)!"
        )
        befehl = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c=0x1a1a2e:s={BREITE}x{HOEHE}:d={gesamt_dauer:.3f}:r=30",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            HINTERGRUND_VIDEO,
        ]
        subprocess.run(befehl, check=True)
        return HINTERGRUND_VIDEO

    quelle = random.choice(kandidaten)
    print(f"Nutze Hintergrundvideo: {quelle}")

    befehl = [
        "ffmpeg", "-y",
        "-stream_loop", "-1",
        "-i", quelle,
        "-t", f"{gesamt_dauer:.3f}",
        "-vf",
        f"scale={BREITE}:{HOEHE}:force_original_aspect_ratio=increase,"
        f"crop={BREITE}:{HOEHE},fps=30,setsar=1",
        "-an",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        HINTERGRUND_VIDEO,
    ]
    subprocess.run(befehl, check=True)
    return HINTERGRUND_VIDEO


# ---------------------------------------------------------------------
# 3. Video-Filtergraph (Text-Overlays) bauen
# ---------------------------------------------------------------------

def video_filter_bauen(fragen: list, fenster_liste: list, logo_vorhanden: bool,
                        zwischen_cta_text: str = None, zwischen_cta_fenster: dict = None) -> tuple:
    filter_teile = []
    label = "0:v"

    # Titel-Badge, dauerhaft sichtbar
    filter_teile.append(
        f"[{label}]drawtext=fontfile={FONT_PFAD}:text='{FORMAT_NAME}':"
        f"fontsize=56:fontcolor=white:x=(w-text_w)/2:y=110:"
        f"box=1:boxcolor={FARBE_AKZENT}:boxborderw=22[vtitel]"
    )
    label = "vtitel"

    n = len(fragen)

    # Nummern-Liste (Grundzustand, immer weiß sichtbar)
    for i in range(1, n + 1):
        y = LISTE_Y_START + (i - 1) * LISTE_ZEILENHOEHE
        neues_label = f"vnum{i}"
        filter_teile.append(
            f"[{label}]drawtext=fontfile={FONT_PFAD}:text='{i}.':"
            f"fontsize={LISTE_SCHRIFT}:fontcolor=white@0.8:x={LISTE_X}:y={y}[{neues_label}]"
        )
        label = neues_label

    # Nummern-Hervorhebung während der jeweiligen Frage aktiv ist
    for i, fenster in enumerate(fenster_liste, start=1):
        y = LISTE_Y_START + (i - 1) * LISTE_ZEILENHOEHE
        neues_label = f"vnumh{i}"
        filter_teile.append(
            f"[{label}]drawtext=fontfile={FONT_PFAD}:text='{i}.':"
            f"fontsize={LISTE_SCHRIFT}:fontcolor={FARBE_AKZENT}:x={LISTE_X}:y={y}:"
            f"enable='between(t,{fenster['frage_start']:.2f},{fenster['fenster_ende']:.2f})'"
            f"[{neues_label}]"
        )
        label = neues_label

    # Fragetext + Countdown + Antwort pro Frage
    for i, (frage, fenster) in enumerate(zip(fragen, fenster_liste), start=1):
        zeile_y = LISTE_Y_START + (i - 1) * LISTE_ZEILENHOEHE

        # Fragetext: oben zwischen Titel und Liste, nur solange die
        # jeweilige Frage aktiv ist
        frage_text = text_umbrechen_und_escapen(frage["frage"], breite=26)
        neues_label = f"vfrage{i}"
        filter_teile.append(
            f"[{label}]drawtext=fontfile={FONT_PFAD}:text='{frage_text}':"
            f"fontsize=48:fontcolor=white:line_spacing=14:"
            f"x=(w-text_w)/2:y={FRAGE_Y}:box=1:boxcolor=black@0.45:boxborderw=26:"
            f"enable='between(t,{fenster['frage_start']:.2f},{fenster['fenster_ende']:.2f})'"
            f"[{neues_label}]"
        )
        label = neues_label

        # Countdown 3-2-1: in der Zeile der aktuellen Frage, genau dort,
        # wo danach die Antwort erscheint
        for k, ziffer in enumerate(["3", "2", "1"]):
            ziffer_start = fenster["countdown_start"] + k * 1.0
            ziffer_ende = ziffer_start + 1.0
            neues_label = f"vcd{i}_{k}"
            filter_teile.append(
                f"[{label}]drawtext=fontfile={FONT_PFAD}:text='{ziffer}':"
                f"fontsize={COUNTDOWN_SCHRIFT}:fontcolor={FARBE_COUNTDOWN}:"
                f"x={ANTWORT_X}:y={zeile_y - 6}:"
                f"enable='between(t,{ziffer_start:.2f},{ziffer_ende:.2f})'"
                f"[{neues_label}]"
            )
            label = neues_label

        # Antwort: neben ihrer Nummer, bleibt ab dem Reveal bis zum
        # Videoende stehen
        antwort_roh = frage["antwort"]
        antwort_text = text_fuer_drawtext_escapen(antwort_roh)
        antwort_schrift = antwort_schriftgroesse(antwort_roh)
        antwort_y = zeile_y + (LISTE_SCHRIFT - antwort_schrift) // 2
        neues_label = f"vantwort{i}"
        filter_teile.append(
            f"[{label}]drawtext=fontfile={FONT_PFAD}:text='{antwort_text}':"
            f"fontsize={antwort_schrift}:fontcolor={FARBE_RICHTIG}:"
            f"x={ANTWORT_X}:y={antwort_y}:"
            f"enable='gte(t,{fenster['antwort_start']:.2f})'"
            f"[{neues_label}]"
        )
        label = neues_label

    # Zwischen-CTA nach Frage 4 (z.B. "Wenn du es bis hier geschafft hast...")
    if zwischen_cta_text and zwischen_cta_fenster:
        cta_text = text_umbrechen_und_escapen(zwischen_cta_text, breite=26)
        neues_label = "vzwischencta"
        filter_teile.append(
            f"[{label}]drawtext=fontfile={FONT_PFAD}:text='{cta_text}':"
            f"fontsize=48:fontcolor=white:line_spacing=14:"
            f"x=(w-text_w)/2:y={FRAGE_Y}:box=1:boxcolor={FARBE_AKZENT}@0.85:boxborderw=26:"
            f"enable='between(t,{zwischen_cta_fenster['start']:.2f},{zwischen_cta_fenster['ende']:.2f})'"
            f"[{neues_label}]"
        )
        label = neues_label

    # Logo/Kanalname unten
    if logo_vorhanden:
        finaler_video_output = "[vout]"
        filter_teile.append(f"[{label}][logoimg]overlay=40:H-h-70[vout]")
    else:
        neues_label = "vkanal"
        filter_teile.append(
            f"[{label}]drawtext=fontfile={FONT_PFAD}:text='{KANAL_NAME}':"
            f"fontsize=48:fontcolor=white:x=40:y=h-110:"
            f"box=1:boxcolor=black@0.35:boxborderw=14[{neues_label}]"
        )
        label = neues_label
        finaler_video_output = f"[{label}]"

    return ";".join(filter_teile), finaler_video_output


# ---------------------------------------------------------------------
# 4. Alles zusammensetzen
# ---------------------------------------------------------------------

def video_zusammensetzen():
    with open("pending_quiz.json", encoding="utf-8") as f:
        daten = json.load(f)

    fragen = daten["fragen"]
    fenster_liste, audio_segmente, gesamt_dauer, zwischen_cta_fenster = zeitleiste_berechnen(len(fragen))

    if MINDEST_GESAMTDAUER > 0 and gesamt_dauer < MINDEST_GESAMTDAUER:
        fehlend = MINDEST_GESAMTDAUER - gesamt_dauer
        zusatz_pro_frage = fehlend / len(fragen)
        print(
            f"Video wäre nur {gesamt_dauer:.1f}s lang (< {MINDEST_GESAMTDAUER:.0f}s "
            f"Mindestlänge) - verlängere jede Antwort-Anzeige um "
            f"{zusatz_pro_frage:.2f}s..."
        )
        fenster_liste, audio_segmente, gesamt_dauer, zwischen_cta_fenster = zeitleiste_berechnen(
            len(fragen), zusatz_halte_dauer=zusatz_pro_frage
        )

    print(f"Berechnete Gesamtdauer: {gesamt_dauer:.1f}s ({len(fragen)} Fragen)")

    hintergrund_vorbereiten(gesamt_dauer)

    logo_vorhanden = os.path.exists(LOGO_PFAD)

    inputs = ["-i", HINTERGRUND_VIDEO]
    if logo_vorhanden:
        inputs += ["-i", LOGO_PFAD]

    audio_input_labels = []
    for typ, wert in audio_segmente:
        if typ == "datei":
            inputs += ["-i", wert]
        else:
            inputs += [
                "-f", "lavfi",
                "-t", f"{wert:.3f}",
                "-i", "anullsrc=channel_layout=mono:sample_rate=24000",
            ]

    # Input-Indizes zuordnen: 0 = Hintergrund, ggf. 1 = Logo, danach Audio
    naechster_index = 1
    if logo_vorhanden:
        naechster_index = 2
    for _ in audio_segmente:
        audio_input_labels.append(f"{naechster_index}:a")
        naechster_index += 1

    video_filter, finaler_video_output = video_filter_bauen(
        fragen, fenster_liste, logo_vorhanden,
        zwischen_cta_text=daten.get("zwischen_cta"),
        zwischen_cta_fenster=zwischen_cta_fenster,
    )

    filter_complex_teile = []
    if logo_vorhanden:
        # Logo klein skalieren, damit es nicht das ganze Bild einnimmt
        filter_complex_teile.append("[1:v]scale=140:-1[logoimg]")
    filter_complex_teile.append(video_filter)

    audio_concat_inputs = "".join(f"[{l}]" for l in audio_input_labels)
    filter_complex_teile.append(
        f"{audio_concat_inputs}concat=n={len(audio_input_labels)}:v=0:a=1[aout]"
    )

    filter_complex = ";".join(filter_complex_teile)

    os.makedirs("output", exist_ok=True)
    befehl = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", finaler_video_output,
        "-map", "[aout]",
        "-t", f"{gesamt_dauer:.3f}",
        "-c:v", "libx264", "-c:a", "aac",
        FERTIGES_VIDEO,
    ]
    subprocess.run(befehl, check=True)
    print(f"Finales Video erstellt: {FERTIGES_VIDEO}")


if __name__ == "__main__":
    video_zusammensetzen()
