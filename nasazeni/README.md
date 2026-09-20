# Nasazení Gelato! na server

Postup pro Odoo 18 běžící v Dockeru.

**Jsou to dva různé případy a plete se to snadno:**

| Situace | Kam jít |
|---|---|
| Na serveru **už web Gelato! běží** a přidává se jen rozvoz | Část A ← tohle je ostrý případ |
| Zakládá se **celý web od nuly** na prázdné databázi | Část B |

Na běžícím webu se **nikdy** nedělají kroky z části B. Přiřazení tématu a
mazání homepage by přepsalo stránky, které tam už jsou.

---

# Část A — přidat rozvoz k běžícímu webu

Instaluje se **jediný modul: `gelato_delivery`**. Přinese s sebou stránku
`/rozvoz` a jednu aplikaci v adminu. Nic jiného se na webu nezmění.

Odhad času: **20 minut**, z toho většinu zabere překreslení zón.

## A1. Co se instaluje a co ne

```
extra-addons/
├── gelato_delivery/     ← instaluje se
└── gelato_flavors/      ← Odoo si ho doinstaluje samo (závislost)
```

`gelato_flavors` je povinná závislost — je v něm seznam příchutí, ze kterého
si zákazník vybírá, a zakládá kořenové menu aplikace Rozvoz. Není to nic
navíc, bez něj se `gelato_delivery` nenainstaluje.

**Neinstaluje se:**

| Modul | Proč ne |
|---|---|
| `theme_gelato` | vzhled webu už na serveru je, znovu se nenasazuje |
| `gelato_tracking` | GTM a Meta Pixel, zatím se neměří |

## A2. Moduly na server

Moduly musí ležet **jednu úroveň** pod addons cestou. Ne
`extra-addons/gelato_delivery/` — tak je Odoo nenajde.

Kopírují se jen tyhle dvě složky, nic dalšího z repozitáře:

```bash
scp -r gelato_delivery gelato_flavors root@SERVER:/cesta/extra-addons/
ssh root@SERVER 'ls /cesta/extra-addons/gelato_delivery/__manifest__.py'
ssh root@SERVER 'docker restart NAZEV_KONTEJNERU'
```

Ta prostřední řádka musí vypsat cestu k souboru. Když vypíše chybu, leží
modul o úroveň hlouběji a Odoo ho neuvidí.

Restart je nutný — Odoo si skládá `addons_path` při startu a bez něj nový
modul nenajde ani po aktualizaci seznamu aplikací.

## A3. Instalace

```bash
docker exec -it NAZEV_KONTEJNERU odoo \
  -d NAZEV_DB \
  --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons \
  -i gelato_delivery \
  --without-demo=all --stop-after-init
docker restart NAZEV_KONTEJNERU
```

Ve výpisu se musí objevit `Module gelato_delivery loaded in ...`.

**Čeština se natáhne sama**, protože na webu Gelato! už aktivní je —
instalace bere překlady pro jazyky, které v databázi jsou. Ověřeno na
čisté české databázi: popisky polí, poznámky u termoboxů i názvy příchutí
naskočí česky.

**`--i18n-overwrite` sem nepatří** — Odoo ho s `-i` rovnou odmítne
(`cannot be used without the i18n-import option or without the update
option`). Přidává se až k `-u` při pozdější aktualizaci.

**`-i` jen napoprvé.** Při další aktualizaci se použije
`-u gelato_delivery --i18n-overwrite`. Druhé `-i` na ostré databázi by
přepsalo výchozí data — termoboxy, ceny, texty e-mailů — a smazalo by, co
si obsluha nastavila.
## A4. Co po instalaci přibylo

Na webu:

* stránka **`/rozvoz`** (je to route, ne stránka v editoru — v seznamu
  stránek ji nehledej)
* položka **Rozvoz** v horním menu, přišitá ke konkrétnímu webu přes
  `website_id`, takže se na jiných webech v téže databázi neukáže

V adminu **jedna aplikace Rozvoz**:

| Menu | K čemu |
|---|---|
| Dnešní nabídka | co se dnes míchá, hodiny pro objednávky, vypínač rozvozu |
| Objednávky | board, každá objednávka s obsahem a adresou |
| Zákazníci | kontakty, sbírají se automaticky z objednávek |
| Nastavení | zóny, termoboxy, balíčky, doplňky, slevové kódy |

Na homepage ani na žádnou existující stránku modul nesahá. Z cizích pohledů
dědí jen formulář nastavení webu, kam si přidá svoje pole.

## A5. Hero na /rozvoz

Hero nahoře na `/rozvoz` kreslí **téma**, ne tenhle modul — modul jen připraví
místo. Fotky se berou ze slidů v backendu.

Když je téma na serveru starší než tenhle git, hero na `/rozvoz` ukáže slidy
z homepage. Vypadá to dobře, jen si tam nejde dát vlastní fotku. Aby šlo slide
namířit na `/rozvoz`, musí se téma aktualizovat:

```bash
docker exec -it NAZEV_KONTEJNERU odoo -d NAZEV_DB \
  --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons \
  -u theme_gelato --stop-after-init
```

**U tématu se `--i18n-overwrite` nepoužívá** — přepsalo by to texty, které si
obsluha na webu upravila přes překlady.

Slide se pak nasměruje v **Web → Gelato → Hero slidy**, do pole
*Jen na těchto adresách* se napíše `/rozvoz`.

Aktualizace tématu je nepovinná. Rozvoz funguje i bez ní.

## A6. Co nastavit

| Kde | Co |
|---|---|
| Web → Nastavení → E-mail pro objednávky | kam chodí nové objednávky |
| Web → Nastavení → Doprava | paušální dopravné pro adresy mimo zóny |
| Rozvoz → Dnešní nabídka | hodiny pro objednávky a vypínač rozvozu |
| Rozvoz → Nastavení → Zóny rozvozu | **překreslit**, viz níže |
| Rozvoz → Nastavení | projít ceny termoboxů, balíčků a doplňků |

### Zóny je potřeba překreslit

V datech jsou dva **hrubé prstence okolo Karlových Varů**, jen aby mapa nebyla
prázdná. Otevřít každou zónu, dát **Nakreslit zónu** a poklikat skutečnou
hranici. Pak zkontrolovat ceny, hranici dopravy zdarma a minimální objednávku.

Zóny se můžou překrývat, vyhrává ta výš v seznamu. **Žádná zóna znamená žádnou
kontrolu** — projde každá adresa a platí paušální dopravné z nastavení.

Zóny potřebují ven na internet. Když je firewall zavře, adresy se nepřevedou
na souřadnice a objednávky projdou bez zóny s paušálním dopravným.

| Adresa | K čemu |
|---|---|
| `nominatim.openstreetmap.org` | převod adresy na souřadnice (server) |
| `*.tile.openstreetmap.org` | dlaždice mapy při kreslení zón (prohlížeč) |

### Sloupce boardu

Rozvoz → Nastavení → Sloupce boardu. Ve výchozím stavu posílá e-mail
**Přijatá** (potvrzení zákazníkovi) a **Na cestě**. Potvrzená a Doručená mají
text připravený, ale vypnutý.

SMS jsou všude vypnuté a bez připojeného operátora stejně neodejdou. Text pro
Na cestě je nachystaný.

## A7. Odchozí pošta

Web už nejspíš e-maily posílá, ale stojí za to to ověřit — **bez funkční pošty
se objednávky vytvoří, ale potvrzení zákazníkovi ani přehled do obchodu
neodejde**.

Nastavení → Technické → **Odchozí poštovní servery** → *Otestovat spojení*.

Odesílatele bere Odoo z e-mailu firmy, proto Nastavení → Uživatelé a firmy →
**Firmy** musí mít vyplněný e-mail.

**Jak poznáte, že server chybí:** objednávky chodí, ale Nastavení → Technické
→ E-maily je plné zpráv ve stavu **Výjimka** s důvodem `111 Connection
refused`. Když není nastavený žádný odchozí server, Odoo zkouší poslat poštu
přes localhost, kde nikdo neposlouchá. Na samotném modulu to nepoznáte —
texty i adresy jsou v pořádku, jen se nemají kudy odeslat.

## A8. Ověřit, že to jede

1. `/rozvoz` se načte ve vzhledu webu, v hlavičce je logo.
2. Složit objednávku, napsat **skutečnou karlovarskou adresu** — pod polem se
   musí objevit název zóny a cena dopravy.
3. Odeslat. Musí přijít **číslo objednávky** na stránce.
4. Odoo → Rozvoz → Objednávky: přibyla karta s obsahem objednávky.
5. Nastavení → Technické → E-maily: dvě zprávy ve stavu **Odesláno**, jedna
   zákazníkovi, jedna do obchodu. Otevřít je a zkontrolovat, že v textu nejsou
   vidět `{{ }}` a že jsou česky.
6. Přetáhnout kartu do **Na cestě** — zákazníkovi odejde další e-mail.
7. Zkusit adresu mimo zóny (třeba pražskou). Musí ji odmítnout.
8. Rozvoz → Zákazníci: objednávající se tam objevil právě jednou.
9. Projít zbytek webu — musí vypadat pořád stejně.
10. Testovací objednávky a zákazníky smazat.

---

# Část B — celý web od nuly

**Jen na prázdné databázi.** Na běžícím webu nic z téhle části.

## B1. Moduly na server

```
extra-addons/
├── gelato_delivery/
├── gelato_flavors/
├── gelato_tracking/
└── theme_gelato/
```

```bash
scp -r gelato_* theme_gelato root@SERVER:/cesta/extra-addons/
ssh root@SERVER 'docker restart NAZEV_KONTEJNERU'
```

## B2. Instalace

```bash
docker exec -it NAZEV_KONTEJNERU odoo \
  -d NAZEV_DB \
  --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons \
  -i theme_gelato,gelato_flavors,gelato_delivery,gelato_tracking \
  --load-language=cs_CZ --without-demo=all --stop-after-init
docker restart NAZEV_KONTEJNERU
```

## B3. Téma přiřadit webu

Samotná instalace tématu nic nezobrazí, Odoo ho musí přiřadit webu.
V Odoo: **Web → Vzhled → Vybrat téma → Gelato**.

Nebo z příkazové řádky:

```bash
docker exec -i NAZEV_KONTEJNERU odoo shell -d NAZEV_DB --no-http <<'PYTHON'
w = env["website"].search([], limit=1)
t = env["ir.module.module"].search([("name", "=", "theme_gelato")], limit=1)
w.theme_id = t.id
t._theme_load(w)
env.cr.commit()
PYTHON
docker restart NAZEV_KONTEJNERU
```

Pokud po tom `/` ukazuje prázdnou stránku, leží na té adrese ještě původní
prázdná `website.homepage`. Smazat ji a **restartovat** (bez restartu hodí
`MissingError` ze staré mezipaměti):

```bash
docker exec -i NAZEV_KONTEJNERU odoo shell -d NAZEV_DB --no-http <<'PYTHON'
for p in env["website.page"].search([("url", "=", "/")]):
    if p.view_id.key == "website.homepage":
        p.unlink()
env.cr.commit()
PYTHON
```

## B4. Zbytek

Odchozí pošta, zóny, sloupce boardu a ověření jsou stejné jako v části A —
viz A6, A7 a A8.

Navíc u kompletního webu:

| Kde | Co |
|---|---|
| Nastavení → Firmy | název, adresa, telefon, e-mail, měna **CZK** |
| Nastavení → Jazyky | jen **čeština**, angličtinu nechat neaktivní |
| Web → Nastavení → Lišta cookies | **zapnout** (jinak se GTM ani Pixel nespustí) |
| Web → Nastavení → GTM / Meta Pixel | vyplnit ID; dokud jsou prázdná, neměří se nic |

---

# Na co si dát pozor

**Heslo pro správu databází.** V `config/odoo.conf` je `admin_passwd =
zmente-me`. Před zveřejněním změnit.

**Přihlášení admina.** Odoo ho zakládá s výchozími údaji, nastavit vlastní
heslo.

**Sloupce boardu posílají zákazníkům e-maily.** Než se pustí ostrý provoz, dát
si pozor, aby v boardu nezůstaly testovací objednávky se skutečnými adresami.

**Druhé `-i` na ostré databázi přepíše výchozí data.** Aktualizuje se vždy
přes `-u`.
