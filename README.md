# Gelato! Karlovy Vary — Odoo moduly

Moduly pro web gelatokv.cz. Celý obsah, který se mění, se spravuje v Odoo,
ne v kódu webu.

| Modul | K čemu je |
|---|---|
| `gelato_flavors` | Seznam příchutí a denní přepínač, co je zrovna v nabídce. |
| `gelato_delivery` | Stránka `/rozvoz`, objednávky, zóny, termoboxy, doplňky, slevové kódy, zákazníci. |
| `gelato_tracking` | Google Tag Manager a Meta Pixel včetně události o dokončené objednávce. |
| `theme_gelato` | Vzhled celého webu gelatokv.cz — hlavička, patička, domovská stránka. |

`gelato_delivery` závisí na `gelato_flavors`. `gelato_tracking` je nezávislý —
dá se nainstalovat i vynechat, nic jiného se tím nerozbije. `theme_gelato` je
Odoo téma, takže se po instalaci musí ještě **přiřadit webu** (Web → Vzhled),
jinak se nikde neprojeví.

### Co jde na ostrý web

Na gelatokv.cz **už web běží** a přidává se k němu jen rozvoz. Instaluje se
proto **jediný modul — `gelato_delivery`**; `gelato_flavors` si Odoo doplní
samo jako závislost. `theme_gelato` se znovu nenasazuje, `gelato_tracking`
zatím ne.

Postup je v [nasazeni/README.md](nasazeni/README.md), část A. Část B je jen
pro zakládání celého webu na prázdné databázi — na běžícím webu by přepsala,
co tam je.

---

## Lokální vývoj

Potřebujete jen Docker. Moduly leží přímo v kořeni tohoto repozitáře, takže
stačí tuhle složku přimountovat jako `/mnt/extra-addons` a přidat ji do
`addons_path`.

První spuštění — vytvoření databáze a instalace modulů:

```bash
docker compose exec odoo odoo -d gelato \
  -i theme_gelato,gelato_flavors,gelato_delivery,gelato_tracking \
  --stop-after-init --without-demo=all --load-language=cs_CZ
docker compose restart odoo
```

Přihlášení: `admin` / `admin` (nastavuje se ručně, viz níže).

### Když upravíte modul

| Co jste změnili | Co stačí udělat |
|---|---|
| XML šablonu nebo pohled | Nic. `--dev=xml,qweb` v override souboru to načte samo, jen obnovte stránku. |
| SCSS nebo JS | Obnovit stránku s Ctrl+Shift+R. |
| Python (modely, controllery) | `docker compose restart odoo` |
| Manifest, nová data, nové pole | `docker compose exec odoo odoo -d gelato -u <modul> --stop-after-init` a pak restart |

### Užitečné

```bash
# log
docker compose logs -f odoo

# Odoo shell
docker compose exec odoo odoo shell -d gelato --no-http

# nastavit heslo adminovi
docker compose exec odoo odoo shell -d gelato --no-http <<'EOF'
env.ref("base.user_admin").write({"login": "admin", "password": "admin"})
env.cr.commit()
EOF

# smazat databázi a začít znovu
docker compose exec db dropdb -U odoo gelato
```

> `docker-compose.override.yml` v kořeni repozitáře je jen pro lokální vývoj
> (jiný port, zapisovatelný mount, `--dev` režim) a je v `.gitignore`.

---

## Nasazení na server

Celý postup krok za krokem je v **[nasazeni/README.md](nasazeni/README.md)** —
kopírování modulů, instalace, přiřazení tématu, odchozí pošta, co nastavit
v Odoo a jak ověřit, že to jede.

---

## Co kde v Odoo najdete

Po instalaci přibude aplikace **Rozvoz**:

```
Rozvoz
├── Dnešní nabídka        ← denní přepínání příchutí + vypínač rozvozu a hodiny
├── Board objednávek      ← sloupce, karta se přetahuje mezi stavy
├── Všechny objednávky    ← dlouhý seznam včetně obsahu objednávky
├── Nastavení
│   ├── Příchutě          ← zakládání a úpravy seznamu
│   ├── Kategorie příchutí
│   ├── Štítky příchutí   ← vegan, bez lepku… přiřazují se k příchuti
│   ├── Sloupce boardu    ← stavy objednávky a e-mail/SMS, které posílají
│   ├── Zóny rozvozu      ← kreslí se na mapě, každá má svoje dopravné
│   ├── Termoboxy         ← velikosti a ceny
│   ├── Doplňky           ← prosecco, balíčky, vaječňák
│   └── Slevové kódy
└── Zákazníci             ← kontakty posbírané z objednávek
```

Ceny dopravy mimo zóny, e-mail pro objednávky a měřicí kódy jsou
v **Web → Nastavení**, protože patří konkrétnímu webu — v jedné databázi může
běžet víc webů a nesmí si do sebe vidět.

**Vypínač rozvozu a hodiny pro objednávky jsou schválně mimo Nastavení**,
přímo na Dnešní nabídce. Obsluha na pobočce nemá do Nastavení přístup a jsou
to přitom jediné dvě věci, které potřebuje přepnout sama. Metody na pozadí
proto píšou na web přes `sudo`.

### Zóny rozvozu

Zóna je obrys nakreslený na mapě (Leaflet nad OpenStreetMap, **bez API klíče
a bez účtu**). Adresa zákazníka se převede na souřadnice přes Nominatim a zóna,
do které bod padne, určí dopravné, hranici dopravy zdarma i minimální
objednávku.

* Zóny se můžou překrývat — vyhraje ta **výš v seznamu**, takže malá levná
  zóna může ležet uvnitř velké dražší.
* **Žádná zóna = žádná kontrola.** Projde každá adresa a platí paušální
  dopravné z nastavení webu.
* Adresu, kterou mapa nezná, **vrátíme zákazníkovi k opravě**. Jediná výjimka
  je nedostupná mapa — to je naše chyba, objednávka projde a v adminu na ní
  svítí upozornění, že dopravné je potřeba potvrdit telefonem.
* Odpovědi geokodéru se ukládají. Nález navždy, nenález na den, aby krátký
  výpadek neodmítal platnou adresu pořád dokola.

> Nakreslené zóny v datech jsou **hrubý začátek**. Před ostrým provozem je
> překreslete podle toho, kam se doopravdy jezdí.

### Zákazníci

Vznikají sami z objednávek, ručně se nic nevyplňuje. Vracející se člověk se
pozná **nejdřív podle telefonu** (porovnává se posledních devět číslic, takže
na zápisu nezáleží), pak podle e-mailu. Existující jméno ani telefon se
nepřepisují — doplní se jen to, co chybělo.

Přepínač **Můžeme oslovit** je ve výchozím stavu vypnutý. Adresa posbíraná
z objednávky sama o sobě není souhlas s posíláním nabídek; na formuláři zatím
žádné zaškrtávátko se souhlasem není.

### Práva

* **Obsluha** — přepíná příchutě a doplňky, vidí a zpracovává objednávky.
* **Správce** — navíc zakládá a maže příchutě, boxy, doplňky a slevové kódy.

### Pojmenovávání

Uvnitř Odoo se věci jmenují **podle funkce, ne podle značky**. Aplikace je
**Rozvoz**, ne „Gelato" — celá ta databáze patří Gelatu, takže značka v menu
nic neříká a jen zabírá místo vedle „Diskuze" a „Nastavení".

Značka zůstává jen tam, kde vedle sebe leží moduly víc projektů: v technickém
názvu (`gelato_delivery`) a v názvu modulu v Aplikacích („Gelato - Rozvoz").
Na dev serveru je to jediné, podle čeho je poznáte.

A **neopakujte název rodiče**: v aplikaci *Rozvoz* je položka *Objednávky*,
ne „Objednávky rozvozu". Popisný název patří tam, kde kontext chybí — model,
předmět e-mailu, název sekvence.

---

## Jazyky

**Web je jednojazyčný — všude čeština.** Aktivní jazyk je jen `cs_CZ`, žádné
`/en/` adresy neexistují a na stránce není přepínač jazyků.

Přesto je **kód psaný anglicky a čeština je překlad** v `i18n/cs.po`. Není to
nedodělek, je to jediný způsob, jak si nezavřít dveře: Odoo má zdroj vždycky
v `en_US`. Kdyby byl kód psaný česky, uložila by se čeština do `en_US` a při
pozdějším přidání němčiny nebo ruštiny by anglická verze navždy ukazovala
češtinu — přesně ta past, na kterou jsme narazili u Elite Vet.

Návštěvník ani obsluha angličtinu nikde neuvidí. Ověřeno projitím celé
stránky i administrace.

### Až bude potřeba další jazyk

1. Odoo → Nastavení → Překlady → Jazyky, aktivovat jazyk.
2. Web → Nastavení → přidat jazyk mezi jazyky webu.
3. **Restartovat kontejner** — bez toho nová jazyková adresa hodí 404.
4. Vyexportovat šablonu a přeložit:
   ```bash
   docker compose exec odoo odoo -d gelato \
     --i18n-export=/tmp/gelato_delivery.pot --modules=gelato_delivery --stop-after-init
   ```
5. Hotový `.po` uložit jako `i18n/<kod>.po` a udělat upgrade modulu.

Přeložitelné je úplně všechno: pole, hlášky ze serveru, texty stránky, e-mail
i hlášky, které píše JavaScript. Aby fungovaly i ty poslední, hlásí se modul
v `models/ir_http.py` do frontendových překladů — bez toho by Odoo
javascriptové texty na veřejný web vůbec neposlalo.

> Když přidáváte nový text do kódu, pište ho anglicky a doplňte překlad do
> `i18n/cs.po`. Bez překladu by se na webu ukázal anglicky.
>
> Dávejte pozor na stejná anglická slova v různém významu — jeden `msgid` má
> jen jeden překlad. Proto má zákazníkovo jméno v kódu `Customer name`
> a název produktu `Name`; kdyby obojí bylo `Name`, vyšlo by z toho
> „Jméno termoboxu“.

**Výjimka:** kategorie položek v měření (`Thermal box`, `Extra`) zůstávají
anglicky schválně. GA4 i Meta seskupují podle doslovného řetězce, takže
přeložená kategorie by jeden produkt rozsekala na řádek za každý jazyk.

---

## Na co si dát pozor

**U balíčku se zadává celková cena, ne příplatek.** „Balíček Dolce Vita“ má
`Cena balíčku celkem` = 799 Kč a `Balíček k termoboxu` = 1 l. Příplatek
(349 Kč) si Odoo dopočítá samo a **přepočítá ho, když se změní cena boxu** —
inzerovaná cena tedy nemůže odejít. Balíček jde objednat jen s tím boxem,
na který je nacenděný, a v jedné objednávce může být jen jeden.

**Hranice dopravy zdarma se dá počítat před slevou i po ní.** Nastavuje se
ve Web → Nastavení → *Hranici počítat*. Výchozí je **před slevou**, tedy
vstřícnější: kdo nakoupí nad 800 Kč, má dopravu zdarma i po uplatnění kódu.
Druhá volba počítá až z částky, kterou zákazník doopravdy zaplatí.

**Cenu vždycky počítá server.** Co pošle prohlížeč, se ignoruje — formulář
posílá jen ID boxu, příchutí, doplňků a kód. Souhrn ve formuláři je jen náhled.

**Vypnutou příchuť nejde objednat.** Kdyby ji obsluha vypnula ve chvíli, kdy
má někdo otevřený formulář, server objednávku odmítne a řekne který.

**Sloupce boardu posílají e-maily — pozor na hromadné úpravy.** Seznam je
schválně bez multi-editu: jeden klik na přepínač s označenými řádky by ho
zapsal do všech a zákazníkům by odešlo všechno ze všech sloupců.

**`noupdate="1"` platí jen při upgradu.** Při `-i` už nainstalovaného modulu
Odoo výchozí data přepíše. Na ostré databázi proto dělejte `-u`, ne `-i`.
