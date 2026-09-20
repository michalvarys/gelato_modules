# Jak přepnout, co dnes máme

Krátký návod pro pobočku. Nic se nemůže rozbít, všechno jde vrátit zpátky.

---

## Ráno: nastavit dnešní příchutě

1. Otevřete Odoo a nahoře klikněte na **Gelato**.
2. Klikněte na **Dnešní nabídka**.

Uvidíte dlaždice se všemi příchutěmi, rozdělené na Zmrzliny, Sorbety a Sezónní.

- **Zelená dlaždice s nápisem DNES TOČÍME** = příchuť je na webu vidět.
- **Šedá dlaždice s nápisem VYPNUTO** = příchuť na webu není.

**Přepnete ji jedním kliknutím na ten barevný pruh.** Nic dalšího se nemusí
ukládat, změna je na webu okamžitě.

> Co jste vypnuli, si zákazník na webu nemůže objednat. I kdyby měl stránku
> otevřenou od rána, systém mu to při odeslání nepustí a napíše mu to.

---

## Když chcete něco dělat, co v seznamu není

Napište to **správci** — příchutě zakládá on v **Gelato → Nastavení → Příchutě**.

Příchuť, kterou už nikdy dělat nebudete, **nemažte**. Otevřete ji a dejte
*Archivovat*. Zmizí ze seznamu i z webu, ale zůstane u starých objednávek.

---

## Objednávky z webu

**Rozvoz → Board objednávek.**

Nová objednávka spadne do prvního sloupce **Přijatá** a hned:

- zákazníkovi odejde potvrzení, že objednávku máte
- vám přijde e-mail s celou objednávkou
- na boardu se objeví karta

Na kartě vidíte všechno podstatné, aniž byste ji museli otevírat: jméno,
částku, číslo objednávky, termín, adresu, velikost boxu a telefon.

**Objednávku posouváte přetažením karty** do dalšího sloupce:

```
Přijatá → Potvrzená → Na cestě → Doručená
                                  Zrušená
```

Sloupce nejsou pevně dané. V **Nastavení → Sloupce boardu** si je
přejmenujete, přeházíte nebo přidáte vlastní.

### E-mail zákazníkovi z libovolného sloupce

U každého sloupce jde zapnout **Poslat e-mail zákazníkovi** a napsat, co se
má poslat. Pak stačí kartu přetáhnout a e-mail odejde sám — třeba „už jsme
vyjeli" ve sloupci *Na cestě*.

Do předmětu i textu můžete vložit zástupné texty, které se vyplní samy:

| Napíšete | Vyplní se |
|---|---|
| `{{ object.name }}` | číslo objednávky |
| `{{ object.customer_name }}` | jméno zákazníka |
| `{{ object.delivery_address }}` | adresa |
| `{{ object.amount_total }}` | celková částka |

> E-mail odejde **jednou za sloupec**. Když kartu přetáhnete pryč a zase
> zpátky, zákazníkovi nic dalšího nepřijde.

Zákazník, který nevyplnil e-mail, žádný nedostane — objednávka projde
normálně dál.

---

## Sezónní věci (vaječňák)

Vaječňák je připravený ve dvou místech a obojí se zapíná stejně — přepínačem:

1. **Jako příchuť** — Gelato → Dnešní nabídka, dlaždice *Vaječňák*.
   Pokud ji tam nevidíte, je archivovaná; řekněte správci.
2. **Jako doplněk k rozvozu (láhev)** — Gelato → Nastavení → Doplňky,
   přepínač **V nabídce** u řádku *Vaječňák*.

Mimo sezónu to zase vypněte. Nemažte to.

---

## Balíčky (Dolce Vita, Festa)

Balíček je termobox a láhev dohromady za lepší cenu. Najdete ho v
**Gelato → Nastavení → Doplňky**.

U balíčku se vyplňuje **celková cena i s termoboxem** — tedy ta, kterou máte
na letáku. Například Dolce Vita = 799 Kč. Políčko *Příplatek k boxu* si Odoo
dopočítá samo, do toho nesahejte.

> Když zdražíte termobox, příplatek se přepočítá sám a cena na letáku zůstane
> sedět. Nemusíte na to myslet.

Balíček jde objednat jen s tím termoboxem, který je u něj vybraný. Když si ho
zákazník na webu přidá, web mu box rovnou přepne. Dva balíčky najednou objednat
nejdou — objednávka má jeden box.

---

## DPH

Sazba se nastavuje **u každého produktu zvlášť** — u termoboxů a u doplňků.
Doprava má vlastní sazbu ve **Web → Nastavení**.

Výchozí nastavení:

| | Sazba |
|---|---|
| Termoboxy (zmrzlina) | 12 % |
| Prosecco a balíčky | 21 % |
| Doprava | 21 % |

**Ceny se zadávají tak, jak je vidí zákazník — tedy včetně DPH.** Tak se
v Česku musí ceny lidem ukazovat a tak to na webu zůstane. DPH se z nich
dopočítá zpátky, nepřičítá se navrch.

Na objednávce pak vidíte **Bez DPH** a **DPH**, a v e-mailu je rozpad po
sazbách zvlášť — účetní si to přebere.

Pokud nejste plátci DPH, zadejte všude **0**.

---

## Slevový kód

**Gelato → Nastavení → Slevové kódy.**

Je tam připravený kód **ZIMA10** (sleva 10 %), zatím vypnutý.
Zapnete ho přepínačem **Platí** v prvním sloupci.

U kódu se dá nastavit:

- **Sleva (%)** — kolik se odečte.
- **Platí od / Platí do** — necháte prázdné, pokud má platit pořád.
- **Limit použití** — kolikrát se smí použít celkem. `0` = neomezeně.

Zákazník kód napíše ve formuláři na webu a dá *Uplatnit*. Web si ho ověří sám
a rovnou mu ukáže cenu se slevou. Na velikosti písmen nezáleží.

Ve sloupci **Použito** vidíte, kolikrát ho kdo použil.
