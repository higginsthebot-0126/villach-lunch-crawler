# menu-crawler (prototype)

Prototype de crawler pour **menus déjeuner à Villach (centre)**.

Objectifs:
- récupérer des menus "du jour" / "de la semaine" depuis des sources hétérogènes (HTML / PDF / images)
- extraire des plats par date (ou par jour de semaine)
- normaliser en structure JSON
- détecter:
  - allergènes, avec focus sur **lactose (allergène UE: lait = code G)**
  - présence de **curry** (mot-clé)

> Remarque: ce repo est un squelette minimal, prévu pour être enrichi restaurant par restaurant.

## Cibles Villach (exemples testés)

### HTML (facile)
- Hotel Seven / Restaurant Milo – page "Milo´s Mittagsmenüs"
  - URL: https://www.hotel-seven.at/speisekarte-mittagsmenues/
  - Format: texte HTML avec sections `Montag 23.02.2026` etc.

- Chickis Villach – page "Mittagsmenü"
  - URL: https://www.chickis.at/chickis-mittagsmenue-schnell-gut-guenstig/
  - Format: texte HTML avec sections `MONTAG, 23.02.` etc.

### PDF (à gérer)
- Cotidiano Villach Hauptplatz (plutôt carte fixe, mais utile pour tester PDF)
  - page: https://www.cotidiano.de/villach-hauptplatz
  - PDFs repérés (à parser):
    - https://www.cotidiano.de/_files/ugd/ace4c0_7aa95331c4504201a522005db651e408.pdf

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Utilisation

```bash
python -m menu_crawler.crawl --config sources.example.yml --out out.json
```

### Générer la page GitHub Pages (manuel)

Le front-end lit `docs/data.json`.

```bash
python -m menu_crawler.build_docs --restaurants docs/restaurants.yml --out docs/data.json
```

Le JSON contient des entrées normalisées (restaurant, date/jour, items, tags, allergènes détectés).

## Stratégie d’extraction (recommandée)

1. **Découverte / sélection**
   - lister les restos (centre Villach) et identifier où le menu est publié (site, PDF, Facebook/Instagram, Google post, etc.)
2. **Fetch**
   - HTML: `requests` + `readability`/`BeautifulSoup` (dans ce prototype on fait simple: texte brut)
   - PDF: télécharger, extraire texte (`pdfplumber`) ; fallback OCR si PDF scanné
   - Réseaux sociaux: idéalement via RSS/endpoint officiel; sinon scraping headless + snapshots (fragile)
3. **Extraction**
   - règles spécifiques par restaurant (regex) + un extracteur "générique" pour les cas simples
4. **Normalisation**
   - items (entrée/plat/dessert) + attributs (allergènes, tags curry, lactose)
5. **QA**
   - conserver le HTML/PDF brut et la sortie JSON pour comparer lors de changements de template

## Notes allergènes (Autriche / UE)

Beaucoup de menus utilisent des codes (A–N). Pour **lait / lactose**, le code est souvent **G**.
Ce prototype détecte:
- explicitement `(G)` / `G` près d’un plat
- heuristiquement via mots-clés (rahm, käse, milch, parmesan, etc.)

## TODO
- ajouter un module "source: facebook/instagram" (avec consentement / conformité)
- un moteur de règles par restaurant (YAML -> regex)
- meilleure segmentation entrée/plat/dessert
- déduplication et gestion des semaines (lundi..vendredi)

## Front-end (GitHub Pages)

Après activation de GitHub Pages (branch `main`, dossier `/docs`), le front-end est servi ici :
`https://higginsthebot-0126.github.io/villach-lunch-crawler/`
