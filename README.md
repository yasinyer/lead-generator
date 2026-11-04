# Lead Generator

Vindt lokale zaken in Limburg (kappers, schoonheidssalons, kinesisten, aannemers,
schoonmaakbedrijven, restaurants, garages, …) met **geen website, alleen een
Facebookpagina, of een site die op gsm niet werkt**. Elke lead krijgt een score,
en het dashboard maakt meteen een gepersonaliseerde pitch en een belscript.

## Wat het doet

1. **Zoeken** in twee bronnen:
   - **OpenStreetMap** (gratis, geen key): naam, adres, telefoon, website.
   - **Google Places API**: rating, aantal reviews, telefoon, website, Maps-link.
   - Dubbels worden samengevoegd (op telefoon, domein, of naam + locatie).
     Zaken die alleen in OSM staan, worden aangevuld met Google-reviews.
2. **Website checken**:
   - Geen site / alleen Facebook of Instagram / alleen een gids (Gouden Gids, TripAdvisor, Treatwell…)
   - Gratis sitebouwer-adres (wixsite.com, business.site, …)
   - Offline, foutcode, ongeldig SSL-certificaat, "binnenkort online"-placeholder
   - **Mobiel:** geen viewport-tag, echte gsm-test in Chromium (zijwaarts scrollen, te kleine tekst)
   - **Verouderd:** geen HTTPS, oude copyright-datum, Flash, frames, tabel-layout, FrontPage…
   - **Traag:** mobiele PageSpeed-score
   - **E-mailadres** zoeken op de homepage en de contactpagina (ook adressen die door Cloudflare verborgen worden)
   - **Gsm-screenshot** van de huidige site, handig om naast jouw mockup te tonen
3. **Score 0-100** = nood aan een site (max 60) + "draait goed" op basis van rating en aantal reviews (max 40).
   ≥ 70 = topper.
4. **Dashboard** met filters, opvolgstatus (nieuw → mockup → gecontacteerd → klant),
   notities, pitch-mail, belscript en CSV-export (opent correct in Excel).

## Mac-app (aanbevolen)

Je hoeft niets te installeren, ook geen Python.

1. Ga naar **[Releases → Lead Generator voor Mac](https://github.com/yasinyer/lead-generator/releases/tag/mac-latest)**
   en download **Lead-Generator-mac.zip**.
2. Dubbelklik op de ZIP en sleep **Lead Generator** naar je map **Programma's**.
3. **Eerste keer openen:** de app is niet door Apple ondertekend, dus macOS houdt hem eerst tegen.
   - Dubbelklik op Lead Generator. Je krijgt een melding dat de app niet gecontroleerd kan worden. Klik op **Gereed**.
   - Open **Systeeminstellingen → Privacy en beveiliging** en scrol naar beneden.
     Bij "Lead Generator werd geblokkeerd" klik je op **Open toch** en bevestig je met je wachtwoord.
   - Op macOS 14 of ouder kan het ook zo: rechtermuisklik op de app, kies **Open** en daarna nog eens **Open**.

   Dat hoeft maar één keer. Daarna open je de app gewoon met een dubbelklik.
4. Het dashboard opent in je browser. Klik op **⚙ Instellingen** en vul je gegevens in.

**Hoe de app werkt**
- De app opent in een eigen venster met een icoon in het Dock, zoals elk ander programma.
  Afsluiten doe je met **⌘Q** of door het venster te sluiten. Het venster onthoudt zijn plaats en grootte.
- Sneltoetsen (ook in de menubalk): **⌘N** nieuwe scan, **⌘F** zoeken, **⌘E** exporteer CSV,
  **⌘,** instellingen.
- Links naar Google Maps, websites of e-mailadressen openen in je gewone browser of mail-app.
- **⬇ Export CSV** zet het bestand in je map **Downloads** en toont het in de Finder.
- Een scan kun je onderbreken met **■ Stoppen**. Gevonden zaken worden meteen bewaard,
  ook als je stopt of de app afsluit; alleen de site-checks die nog niet klaar waren ontbreken dan.
- Begin met kleine scans (1 à 2 sectoren, 1 à 3 gemeenten). Het scanvenster toont vooraf of
  je Google-budget volstaat; bij een te klein budget krijgen de grootste gemeenten voorrang.
- Voor de gsm-check gebruikt de app Google Chrome als je dat hebt.
  Zo niet, dan downloadt hij eenmalig een eigen browser van ongeveer 150 MB.
- Je leads en instellingen staan in `~/Library/Application Support/Lead Generator/`
  en blijven bewaard als je de app bijwerkt. Loopt er iets mis, dan staat er ook een `leadgen.log` in
  die je kunt doorsturen.
- De app is gebouwd voor Macs met een Apple-chip (M1 of nieuwer). Heb je een oudere Intel-Mac,
  gebruik dan het startbestand hieronder.

## Starten met het startbestand (Windows, Intel-Mac)

**Eenmalig:** installeer Python 3.10 of nieuwer via <https://www.python.org/downloads/>.
Op Windows vink je tijdens de installatie **"Add python.exe to PATH"** aan.

1. Download deze code: op GitHub klik je op de groene knop **Code** en dan op **Download ZIP**.
   Pak de ZIP uit, bijvoorbeeld in je map Documenten.
2. Dubbelklik op het startbestand:
   - **Windows:** `Start Lead Generator.bat`. Toont Windows "Uw pc is beveiligd"?
     Klik dan op **Meer info** en daarna op **Toch uitvoeren**.
   - **Mac:** `Start Lead Generator.command`. Wordt het tegengehouden, gebruik dan dezelfde stappen als bij de app.
3. De eerste keer installeert het venster alles zelf. Dat duurt een paar minuten.
   Daarna opent het dashboard vanzelf in je browser.

Laat het zwarte venster open zolang je het dashboard gebruikt. Wil je stoppen, sluit dan het venster.
Je leads staan dan in de map `data/` en je instellingen in `.env`, naast de code.

### Google API-key (aanbevolen)

Zonder key werkt alles ook, maar dan alleen met OpenStreetMap: dan heb je geen reviews
en ratings, en geen PageSpeed-check.

1. Ga naar <https://console.cloud.google.com/> en maak een project aan.
2. Zet facturatie aan. Dat is verplicht, ook voor het gratis gebruik.
3. Ga naar **APIs & Services → Library** en zet deze twee aan:
   - **Places API (New)**
   - **PageSpeed Insights API**
4. Ga naar **APIs & Services → Credentials → Create credentials → API key**.
   Beperk de key tot de twee API's hierboven.
5. Plak de key in het dashboard onder **⚙ Instellingen**.
6. **Zet een budgetalert** (Billing → Budgets & alerts), bijvoorbeeld op €5.

Google geeft elke maand een gratis gebruiksvolume per API. Kijk op de
[prijspagina](https://developers.google.com/maps/billing-and-pricing/pricing) wat er nu geldt.
De tool doet per scan nooit meer dan het ingestelde aantal Google-calls (standaard 150).
Ter indicatie: één sector in één gemeente kost 1 tot 3 calls, en elke OSM-zaak die je
aanvult kost er 1.

### Voor wie toch de terminal wil

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium

python -m leadgen serve                                     # dashboard
python -m leadgen list                                      # sectoren en gemeenten
python -m leadgen scan -s kapper -s schoonheid -c Hasselt   # één of meer sectoren en steden
python -m leadgen scan -s all -c Hasselt -c Genk --radius 4000
python -m leadgen scan -s garage --limburg --max-places-calls 300
python -m leadgen export leads.csv --min-score 60
```

Je kunt een scan opnieuw draaien wanneer je wilt: jouw status en notities blijven behouden.

## Werkwijze die goed werkt

1. Scan één of twee sectoren per avond, bijvoorbeeld kappers en schoonheidssalons in Hasselt.
2. Filter op **min. score 70** en **min. reviews 20**. Dat zijn zaken die goed draaien maar online zwak staan.
3. Zet je beste 5 kandidaten op *Interessant*. Maak voor elk een homepage-mockup en zet ze op *Mockup gemaakt*.
4. Gebruik de **pitch** uit het detailpaneel. Die noemt hun reviews en wat er concreet mis is met hun site.
   Voeg je mockup toe en, als je hebt, het gsm-screenshot van hun huidige site.
5. Bellen of langsgaan werkt lokaal vaak nog beter. Daarvoor staat er een **belscript** klaar.
6. Noteer wat er gezegd is en zet de status op *Opvolgen*. Na een week opnieuw contact opnemen.

## Aanpassen

- **Sectoren en gemeenten:** `leadgen/config.py` (`SECTORS` en `CITIES`). Voor een
  nieuwe sector geef je een Google-zoekterm en de OSM-tags op (zie
  [OSM wiki](https://wiki.openstreetmap.org/wiki/Map_features)).
- **Score:** de gewichten staan in `leadgen/scoring.py`.
- **Pitch- en beltekst:** `leadgen/pitch.py`.

## Goed om te weten

- De tool scrapet Google Maps **niet** rechtstreeks, want dat mag niet volgens de
  voorwaarden van Google. Ze gebruikt de officiële Places API. Facebookpagina's worden
  ook niet gescrapet: e-mailadressen komen alleen van de eigen website van de zaak of uit OSM.
- OpenStreetMap gebruikt publieke Overpass-servers. Die zijn gratis, maar scan niet
  tientallen keren per uur.
- **Koude e-mails (GDPR):** naar een algemeen bedrijfsadres (info@…) mag je in België een
  relevante, eenmalige zakelijke boodschap sturen, als je erbij vermeldt hoe ze kunnen
  laten weten dat ze niets meer willen ontvangen. Die zin staat al in de pitch.
  Bij eenmanszaken met een persoonlijk adres moet je voorzichtiger zijn.
  Bellen of langsgaan is dan vaak de betere keuze.
- Krijgt Chromium het niet gestart? Zet `CHROMIUM_PATH=` in `.env` naar je eigen
  Chrome, of zet bij een scan het vinkje "Gsm-check + screenshot" uit.

## Tests en de app bouwen

```bash
pytest
pyinstaller packaging/leadgen.spec --noconfirm   # op een Mac: maakt dist/Lead Generator.app
```

Bij elke push bouwt GitHub Actions de Mac-app (`.github/workflows/mac-app.yml`).
Die doet daarbij een echte testscan en zet het resultaat klaar onder Releases.
