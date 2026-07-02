"""Génération des documents PDF : accusé de réception et bordereau."""
import io

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

BLEU = colors.HexColor("#0F4C81")


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("Titre", parent=s["Title"], textColor=BLEU, fontSize=18, spaceAfter=6))
    s.add(ParagraphStyle("SousTitre", parent=s["Normal"], alignment=TA_CENTER,
                         textColor=colors.grey, fontSize=10, spaceAfter=16))
    s.add(ParagraphStyle("Petit", parent=s["Normal"], fontSize=9, textColor=colors.grey))
    return s


def _entete(styles, titre):
    return [
        Paragraph("ADMINISTRATION FISCALE", styles["Petit"]),
        Paragraph(titre, styles["Titre"]),
        Paragraph("Application de gestion des courriers — GesCourrier", styles["SousTitre"]),
    ]


def _table_infos(lignes):
    t = Table(lignes, colWidths=[55 * mm, 110 * mm])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#BBBBBB")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DDDDDD")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF3F8")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def generer_accuse(courrier):
    """Accusé de réception d'un courrier -> bytes PDF."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=22 * mm, bottomMargin=22 * mm,
                            leftMargin=22 * mm, rightMargin=22 * mm)
    styles = _styles()
    c = courrier
    el = _entete(styles, "ACCUSÉ DE RÉCEPTION")
    el.append(_table_infos([
        ["Référence", c.reference],
        ["Type", c.get_type_display()],
        ["Objet", c.objet],
        ["Contribuable", c.contribuable.raison_sociale],
        ["NIF", c.contribuable.nif],
        ["Date du courrier", c.date_courrier.strftime("%d/%m/%Y")],
        ["Enregistré le", timezone.localtime(c.date_enregistrement).strftime("%d/%m/%Y à %H:%M")],
        ["Enregistré par", str(c.enregistre_par) if c.enregistre_par else "—"],
    ]))
    el.append(Spacer(1, 14 * mm))
    el.append(Paragraph(
        "Nous accusons réception du courrier référencé ci-dessus, pris en charge par nos services "
        "pour traitement.", styles["Normal"]))
    el.append(Spacer(1, 18 * mm))
    el.append(Paragraph("Le service courrier", styles["Normal"]))
    el.append(Paragraph("Signature et cachet", styles["Petit"]))
    el.append(Spacer(1, 10 * mm))
    el.append(Paragraph(
        f"Document généré le {timezone.localtime().strftime('%d/%m/%Y à %H:%M')}.", styles["Petit"]))
    doc.build(el)
    return buf.getvalue()


def generer_bordereau(courriers, titre="Bordereau des courriers"):
    """Bordereau listant un ensemble de courriers -> bytes PDF."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm,
                            leftMargin=15 * mm, rightMargin=15 * mm)
    styles = _styles()
    el = _entete(styles, titre)

    entetes = ["#", "Référence", "Type", "Objet", "Contribuable (NIF)", "Statut"]
    donnees = [entetes]
    for i, c in enumerate(courriers, start=1):
        donnees.append([
            str(i), c.reference, c.get_type_display(),
            (c.objet[:38] + "…") if len(c.objet) > 38 else c.objet,
            f"{c.contribuable.raison_sociale}\n{c.contribuable.nif}",
            c.get_statut_display(),
        ])
    if len(donnees) == 1:
        donnees.append(["—", "Aucun courrier", "", "", "", ""])

    t = Table(donnees, colWidths=[8 * mm, 28 * mm, 18 * mm, 55 * mm, 42 * mm, 29 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLEU),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F6FA")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    el.append(t)
    el.append(Spacer(1, 8 * mm))
    el.append(Paragraph(
        f"Total : {max(len(donnees) - 1, 0)} courrier(s). "
        f"Édité le {timezone.localtime().strftime('%d/%m/%Y à %H:%M')}.", styles["Petit"]))
    doc.build(el)
    return buf.getvalue()
