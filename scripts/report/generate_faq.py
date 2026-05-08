"""Generate structured FAQ content per product category with JSON-LD schema."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import click
import yaml
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()

console = Console()

# ── FAQ templates per category ─────────────────────────────────────────────
# Each entry: {"q": question, "a": answer}

_FAQ_TEMPLATES: dict[str, list[dict[str, str]]] = {
    "vetements_chien": [
        {
            "q": "Comment choisir la bonne taille de vêtement pour mon chien ?",
            "a": (
                "Mesurez le tour de poitrail, le tour de cou et la longueur du dos de votre chien. "
                "Nos guides des tailles sont disponibles sur chaque fiche produit. "
                "En cas de doute entre deux tailles, choisissez la plus grande pour préserver la liberté de mouvement. "
                "Nos vêtements pour chien sont conçus pour une morphologie naturelle sans comprimer les articulations."
            ),
        },
        {
            "q": "Quelles matières sont utilisées dans vos vêtements pour chien ?",
            "a": (
                "Nous sélectionnons des matières premium : laine d'alpaga (douce et hypoallergénique), "
                "soie naturelle, cachemire et cuir pleine fleur tanné végétal. "
                "Toutes nos matières sont testées sans produits chimiques nocifs et adaptées au contact avec la peau animale. "
                "Nos vêtements pour chien sont fabriqués à la main en France par nos couturières expertes."
            ),
        },
        {
            "q": "Comment habituer mon chien à porter un vêtement ?",
            "a": (
                "Introduisez le vêtement progressivement : posez-le près de votre chien quelques jours, "
                "puis enfilez-le quelques minutes en le récompensant. "
                "Augmentez la durée graduellement. "
                "Nos modèles sont conçus pour être enfilés facilement et ne pas stresser l'animal — "
                "fermoirs magnétiques ou velcro pour une mise en place sans effort."
            ),
        },
        {
            "q": "Comment entretenir les vêtements pour chien Léonie Delacroix ?",
            "a": (
                "Lavage à la main à l'eau froide ou cycle délicat à 30°C maximum. "
                "Séchage à plat, à l'abri de la lumière directe. "
                "Évitez l'essorage pour préserver les matières nobles comme l'alpaga et la soie. "
                "Un entretien soigneux garantit une durée de vie longue et un confort constant."
            ),
        },
        {
            "q": "Vos vêtements pour chien sont-ils adaptés à toutes les saisons ?",
            "a": (
                "Nos manteaux et pardessus sont conçus pour les saisons froides (automne et hiver). "
                "Les tours de cou et pulls légers conviennent aux demi-saisons. "
                "Chaque fiche produit indique la saison recommandée. "
                "La laine d'alpaga régule naturellement la température corporelle, ce qui en fait un choix idéal pour les variations de temps."
            ),
        },
    ],
    "vetements_chat": [
        {
            "q": "Mon chat peut-il vraiment porter des vêtements sans stress ?",
            "a": (
                "Oui, à condition de choisir des pièces légères, non-restrictives et adaptées à sa morphologie. "
                "Nous travaillons avec des comportementalistes félins pour concevoir des modèles qui respectent "
                "les besoins sensoriels du chat. "
                "Les signes d'acceptation : le chat continue de se déplacer normalement, mange et se toilette. "
                "Interrompez si vous observez immobilité, halètement ou tentatives répétées de retrait."
            ),
        },
        {
            "q": "Comment prendre les mesures de mon chat pour commander le bon modèle ?",
            "a": (
                "Mesurez le tour de cou, le tour de poitrail (juste derrière les pattes avant) et la longueur du dos. "
                "Reportez-vous au guide des tailles sur chaque fiche produit. "
                "Nos vêtements pour chat sont coupés pour ne pas gêner les sauts, "
                "le toilettage ou les passages dans les chatières."
            ),
        },
        {
            "q": "Quelles matières utilisez-vous pour les vêtements pour chat ?",
            "a": (
                "Nous privilégions la laine d'alpaga ultra-douce (hypoallergénique et thermorégulante), "
                "le jersey de soie naturelle et le coton biologique certifié. "
                "Ces matières évitent l'accumulation d'électricité statique et ne retiennent pas les poils. "
                "Toutes sont fabriquées sans substances irritantes pour la peau féline sensible."
            ),
        },
        {
            "q": "Comment laver les vêtements pour chat ?",
            "a": (
                "Lavage à la main à l'eau froide, avec un savon doux sans parfum. "
                "Séchage à plat à l'ombre. "
                "Évitez la machine à laver pour les pièces en alpaga ou soie. "
                "Le coton biologique peut passer en machine à 30°C en cycle délicat."
            ),
        },
    ],
    "fontaines": [
        {
            "q": "Pourquoi mon chat devrait-il boire dans une fontaine plutôt qu'un bol ?",
            "a": (
                "Les chats sont instinctivement attirés par l'eau en mouvement — un réflexe de survie. "
                "Une fontaine filtrante peut augmenter leur consommation d'eau de 50 % par rapport à un bol statique. "
                "Une meilleure hydratation réduit les risques d'insuffisance rénale, de calculs urinaires et d'infections. "
                "Recommandée par les vétérinaires pour les chats prédisposés aux maladies rénales."
            ),
        },
        {
            "q": "À quelle fréquence faut-il changer l'eau et nettoyer la fontaine ?",
            "a": (
                "Changez l'eau tous les 2 à 3 jours et nettoyez le bac hebdomadairement. "
                "Le filtre charbon actif doit être remplacé toutes les 2 à 4 semaines selon le nombre d'animaux et la dureté de l'eau. "
                "Un entretien régulier garantit une eau fraîche, propre et sans odeur désagréable."
            ),
        },
        {
            "q": "La fontaine fait-elle du bruit ? Peut-elle déranger mon chat ?",
            "a": (
                "Nos fontaines sont équipées d'un moteur ultra-silencieux (< 40 dB). "
                "La majorité des chats s'y habituent en 24 à 48 heures. "
                "Le bruit de l'eau qui coule est justement attractif pour les félins — c'est ce qui les incite à boire davantage. "
                "Si votre chat semble méfiant au début, placez la fontaine loin de sa litière et près de son zone de repos."
            ),
        },
        {
            "q": "La fontaine fonctionne-t-elle sans fil ?",
            "a": (
                "Oui, notre modèle Fontaine Smart est sans fil et rechargeable par USB. "
                "L'autonomie varie de 7 à 15 jours selon le débit choisi. "
                "L'installation sans câble vous permet de la placer partout dans votre intérieur sans contrainte esthétique. "
                "Compatible avec tous les filtres de remplacement disponibles dans notre boutique."
            ),
        },
        {
            "q": "La fontaine est-elle sans danger pour les chats et les chiens ?",
            "a": (
                "Toutes nos fontaines sont fabriquées en matériaux certifiés alimentaires : inox 304, plastique sans BPA, "
                "céramique de qualité. "
                "Les filtres charbon actif utilisés respectent les normes européennes de qualité alimentaire. "
                "Aucun composant chimique nocif ne risque de contaminer l'eau de votre animal."
            ),
        },
    ],
    "filtres": [
        {
            "q": "À quelle fréquence faut-il changer les filtres ?",
            "a": (
                "En règle générale, changez les filtres toutes les 2 à 4 semaines. "
                "Si vous avez plusieurs animaux ou si votre eau est calcaire, remplacez-les toutes les 2 semaines. "
                "Un filtre saturé perd son efficacité et peut développer des bactéries — un changement régulier est essentiel."
            ),
        },
        {
            "q": "Comment savoir que le filtre doit être changé ?",
            "a": (
                "Signes à surveiller : eau avec une légère odeur, dépôts visibles sur le filtre, "
                "débit de la fontaine réduit. "
                "Certains chats refusent de boire à la fontaine quand le filtre est trop usé — c'est un signal fiable. "
                "Nos packs économiques permettent d'avoir toujours un filtre de rechange disponible."
            ),
        },
        {
            "q": "Ces filtres sont-ils compatibles avec toutes les fontaines Léonie Delacroix ?",
            "a": (
                "Oui, nos filtres sont conçus pour être compatibles avec l'ensemble des fontaines et abreuvoirs Léonie Delacroix. "
                "Consultez la fiche produit pour vérifier la compatibilité avec votre modèle. "
                "Chaque filtre est emballé individuellement pour préserver sa fraîcheur jusqu'à utilisation."
            ),
        },
    ],
    "accessoires": [
        {
            "q": "Vos accessoires sont-ils fabriqués avec des matériaux sans danger pour mon animal ?",
            "a": (
                "Oui. Nous sélectionnons exclusivement des matériaux certifiés alimentaires ou sûrs au contact animal : "
                "céramique de qualité, inox 304, bois naturel non traité, cuir tanné végétal. "
                "Aucun produit chimique, peinture ou vernis nocif n'est utilisé dans notre fabrication. "
                "Chaque accessoire est testé avant mise en vente."
            ),
        },
        {
            "q": "Comment entretenir les accessoires Léonie Delacroix ?",
            "a": (
                "Les bols en céramique ou inox passent au lave-vaisselle. "
                "Les griffoirs et arbres à chat s'entretiennent avec un chiffon humide. "
                "Évitez les produits ménagers agressifs — un savon doux suffit. "
                "La durabilité de nos matériaux premium garantit un usage intensif sans dégradation prématurée."
            ),
        },
        {
            "q": "Vos griffoirs réduisent-ils vraiment les dégâts sur les meubles ?",
            "a": (
                "Oui, à condition que le griffoir soit positionné là où votre chat griffe habituellement. "
                "Le sisal naturel que nous utilisons offre la résistance idéale pour satisfaire l'instinct de griffage. "
                "Nous recommandons de placer le griffoir près du lieu de repos du chat, "
                "car les chats griffent souvent en s'étirant au réveil."
            ),
        },
        {
            "q": "Le bol surélevé est-il vraiment meilleur pour la santé de mon chat ?",
            "a": (
                "Oui. Un bol surélevé réduit la pression sur la colonne cervicale du chat pendant le repas, "
                "améliore la posture et facilite la digestion. "
                "Recommandé par les vétérinaires pour les chats âgés ou ceux souffrant d'arthrose. "
                "Notre Bol Félin Raffiné est incliné à l'angle optimal pour la posture naturelle féline."
            ),
        },
    ],
}


def load_keywords(path: str) -> dict[str, list[str]]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def generate_faq(category: str) -> list[dict[str, str]]:
    """Return the FAQ list for a given category."""
    return _FAQ_TEMPLATES.get(category, [])


def build_json_ld(faq: list[dict[str, str]]) -> dict[str, Any]:
    """Build a schema.org/FAQPage JSON-LD object."""
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["q"],
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": item["a"],
                },
            }
            for item in faq
        ],
    }


def render_markdown(
    faqs_by_category: dict[str, list[dict[str, str]]],
    date: str,
) -> str:
    """Render all FAQs as a Markdown document."""
    total = sum(len(v) for v in faqs_by_category.values())
    lines = [
        f"# FAQ Structurée — leoniedelacroix.com — {date}",
        "",
        f"**{total} questions** réparties sur {len(faqs_by_category)} catégories",
        "",
        "> Ces FAQ sont prêtes à intégrer sur les pages produits et articles de blog.",
        "> Le JSON-LD associé est disponible dans `data/raw/faq_suggestions.json`",
        "> pour injection via metafield Shopify ou theme Liquid.",
        "",
        "---",
        "",
    ]

    _CATEGORY_LABELS = {
        "vetements_chien": "Vêtements pour chien",
        "vetements_chat": "Vêtements pour chat",
        "fontaines": "Fontaines & Abreuvoirs",
        "filtres": "Filtres & Accessoires fontaines",
        "accessoires": "Accessoires maison",
    }

    for category, faq in faqs_by_category.items():
        label = _CATEGORY_LABELS.get(category, category)
        lines += [f"## {label}", ""]
        for item in faq:
            lines += [
                f"**Q : {item['q']}**",
                "",
                item["a"],
                "",
            ]
        lines += ["---", ""]

    lines.append("*Généré automatiquement par le pipeline SEO leoniedelacroix.com*")
    return "\n".join(lines)


@click.command()
@click.option("--keywords", default="config/keywords.yaml", show_default=True)
@click.option("--output-dir", default="reports", show_default=True)
@click.option("--json-output", default="data/raw/faq_suggestions.json", show_default=True)
def main(keywords: str, output_dir: str, json_output: str) -> None:
    """Generate structured FAQ content per product category with JSON-LD schema."""
    console.print("[bold cyan]► Generating structured FAQ[/bold cyan]")

    categories = list(_FAQ_TEMPLATES.keys())
    faqs_by_category: dict[str, list[dict[str, str]]] = {}
    json_output_data: dict[str, Any] = {}

    for category in categories:
        faq = generate_faq(category)
        faqs_by_category[category] = faq
        json_output_data[category] = {
            "faq": faq,
            "json_ld": build_json_ld(faq),
        }
        console.print(f"  {category}: {len(faq)} questions")

    # Save JSON-LD
    Path(json_output).parent.mkdir(parents=True, exist_ok=True)
    with open(json_output, "w", encoding="utf-8") as f:
        json.dump(json_output_data, f, ensure_ascii=False, indent=2)

    # Save Markdown report
    date = datetime.utcnow().strftime("%Y-%m-%d")
    out_dir = Path(output_dir) / date
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "faq_suggestions.md"
    out_path.write_text(render_markdown(faqs_by_category, date), encoding="utf-8")

    total = sum(len(v) for v in faqs_by_category.values())
    console.print(f"  [green]✓[/green] {total} Q/R → {out_path}")
    console.print(f"  [green]✓[/green] JSON-LD → {json_output}")


if __name__ == "__main__":
    main()
