# Interjú-előkészítő – „Applied AI Engineer, Conversational Analytics" (ALDI)

**Ez a doksi neked szól, nem a bizottságnak.** Egy such doksi, amit az interjú előtt
ketszer elolvasol, az interjúban pedig lapozva használsz. Minden benne lévő mondat
úgy van megírva, hogy **szóban is elmondható** legyen: nincs benne félbeszakadt
gondolatmenet, nincs kód, és nincs olyan mondat, amit ne tudnál szóban is folytatni.

**Amit a doksi nem csinál:** nem ad meg egy szöveget, amit be kell olvasni. Ehelyett
megadja, **mit érdemes mondani** minden szokásos kérdésre — a hirdetés tételei
sorrendjében — plusz a technikai háttér magyarázatát (mi a DSPy, mi a GraphJin,
miért választottam ezeket), amit akkor tudsz előhúzni, ha rákérdeznek.

**Használat:** a 2. fejezet a fő forgatókönyv. A 3–8. fejezet a háttér, ha
„magyarázza el, hogyan működik" típusú kérdés jön. A 9. fejezet a saját
kérdéseid, amiket a végén te kérdezel.

---

## 1. Bemutatkozás (30 másodperc)

> „Egy beszélgetéses analitikai alkalmazást építettem: az üzleti felhasználó
> természetes nyelven kérdez az ITSM – helpdesk – adatbázisról, és olyan választ kap,
> ami **igazoltan a valós adatbázis eredményén** áll, és amit vissza is lehet
> ellenőrizni.
>
> A legfontosabb tervezési döntésem az volt, hogy **a modell soha nem kap hatalmat**.
> Nem ír SQL-t, nem éri el az adatbázist, és a jogosultságot nem a prompt
> határozza meg. A modell csak egy engedélyezett listán belül választ mezőket és
> műveleteket; utána egy determinisztikus réteg ellenőrzi, és a lekérdezést egy
> csak-olvasó réteg futtatja.
>
> A második fontos döntés az volt, hogy **mindent mérni kell**. Van egy 57 esetből
> álló, kiértékelésre tartott tesztkészletem, és egy olyan regressziós gate, amely
> **non-zero hibakóddal** bukik el, ha a minőség romlik, ha bármilyen tiltott
> adatbázis-hatás történik, vagy ha bármi kiszivárog. A jelenlegi eredmény:
> execution accuracy 1.0, nulla tiltott hatás, nulla adatszivárgás."

**Ha 2 perced van**, utána ezt mondd:

> „A rendszernek három része van. Egy **kormányozott hozzáférési réteg**, ami
> biztosítja, hogy a modell ne tudjon ártani. Egy **kérdés-válasz pipeline**, ami
> a természetes nyelvet lekérdezéssé alakítja, lefuttatja, és a bizonyítékból
> állítja elő a választ. És egy **értékelési eszközkészlet**, ami mér, és ami
> release előtt blokkol, ha valami romlott.
>
> A legnehezebb rész a tartalmi keresés volt: a felhasználó nem a jegyek mezőire
> kérdez, hanem arra, hogy **milyen tartalomról szólnak a jegyek**. Ehhez
> hibrid keresést építettem – szöveges és szemantikus találatok összevonása – és
> külön, kalibrált küszöbbel működő darabszám-számolást. A küszöböt nem becsléssel,
> hanem egy szisztematikus méréssel találtam meg."

---

## 2. Interjú-script: a hirdetés tételei, kérdés–válasz formában

### „Mondja el, mi a feladat."

> „Olyan LLM-alapú alkalmazásokat építeni, amelyekkel az üzleti felhasználók
> természetes nyelven tesznek fel kérdéseket a cég adatairól, és pontos, visszakereshető
> választ kapnak. Ehhez kell: Pythonban írt LLM-alkalmazások, szövegből
> lekérdezés-struktúrázás, dokumentumokon való keresés, értékelési pipeline-ok,
> és biztonság. Ezek mind megvannak a projektemben, és pont ezekre a pontokra
> koncentrálok most."

### „Mit takarít a 'conversational analytics'?"

> „Négy dolgot. Egy **kérdés-válasz felület**, ami természetes nyelven működik.
> Egy **kormányozott hozzáférési réteget**, ami alatt a modell nem tud adatbázis
> hatást okozni. Egy **bizonyíték-alapú válaszadást**, ami nem hallucinál, mert a
> válasz csak a lefuttatott lekérdezés eredményéből épül. És egy **mérési
> rendszert**, ami minden változásnál megmondja, javult-e vagy rontott."

### „Hogyan néz ki egy kérdés az Ön rendszerében?"

> „A felhasználó beír egy kérdést a demó felületen. A rendszer először osztályozza,
> hogy a kérdés **tartalmi** kérdés-e (valami a jegyek szövegéről szól) vagy
> **strukturált** kérdés (számlálás, csoportosítás, szűrés). Ezután a strukturált
> útvonalon egy tipizált kérés keletkezik – nem nyers SQL, hanem egy objektum:
> melyik entitás, melyik művelet, melyik mezők, milyen szűrők, milyen limit. Ezt egy
> determinisztikus validator ellenőrzi, majd egy csak-olvasó GraphQL réteg futtatja
> le. Végül a bizonyítékból áll össze a válasz, és kíséri egy tisztított nyomkövetés.
>
> A tartalmi kérdések más úton mennek: ott egy hibrid kereső csatorna fut – szöveges
> és szemantikus találatok –, és a 'hány jegy szól a bejelentkezésről' típusú
> kérdésre valódi darabszámot adok."

### „Mit takar a 'tipizált kérés'?"

> „Nem nyers SQL-t, hanem egy **előre definiált űrlapot**, amit a modell tölt ki. Az
> űrlap adott sémájú: melyik entitás, melyik művelet, melyik mezők, milyen szűrők,
> milyen aggregáció, mekkora limit. Ezt a rendszer géppel ellenőrzi, és a megadott
> mezőlistából nem lehet kiválni.
>
> Ennek négy előnye van. **Egy:** a forma ellenőrizhető – ha a modell nem létező
> mezőt, értelmezhetetlen műveletet vagy típusban nem odavaló szűrőértéket ad, az
> már **az adatbázis előtt** elhasal, és egyáltalán nem megy ki lekérdezés. **Kettő:**
> a lehetséges mezők és műveletek zárt listája egyetlen helyen van definiálva, és
> ugyanazt érvényesíti a validátor és a lekérdezési réteg is. **Három:** a modell
> nem SQL-t ír, hanem űrlapot tölt ki – így nincs is SQL-injekciós felület a modell
> oldalán. **Négy:** a kiértékelésben az elvárt eredmény is ugyanilyen űrlap, ezért a
> pontosság egyezéssel mérhető, nem becsléssel.”

**Ha rákérdeznek a határra (ez a legfontosabb árnyalat):**

> „Fontos különbséget teszek: a tipizálás a **jogutadást** kezeli, a mérés a
> **helyességet**.
>
> Amit a forma garantál: a modell **nem engedélyezett és nem jól formált kérést nem
> tud végrehajtatni** – az ilyen kérés a validátoron bukik, az adatbázishoz hozzá sem
> jut. A korábbi mondatom – hogy 'nem tud értelmetlen kérést kiadni' – pontatlan
> volt: kiadni tud, **végrehajtani nem**.
>
> Amit a forma **nem** garantál: hogy a kérés értelmes. A validator tudja, hogy a
> 'csat_score' számmező, és nem tudja, hogy egy 'P9' prioritás értelmetlen – az
> átmegy a formán, lefut, és nulla sort ad. Vagyis a *jól formált, engedélyezett,
> de szemantikailag értelmetlen* kérést a forma nem szűri ki. Ezt a mérés fogja meg:
> minden kiértékelési esetnek van elvárt eredménye, és ha a modell értelmetlen
> kérésre tér el, az execution accuracy-ben azonnal látszik.
>
> Röviden: a rossz kérés olcsón és pontosan kimutatható – előbb a forma, utána a
> mérés.”

### „Hogyan garantálja a pontosságot?"

> „Nem garantálom száz százaléktal, és nem is állítom, hogy bármi garantálható.
> Amit teszek: **mérhetővé** teszem. A válasz kizárólag a lefuttatott lekérdezés
> eredményéből épül, és van egy determinisztikus ellenőrzés, ami visszakeresi a
> válaszban szereplő minden számot és névértéket a bizonyítékban. Ami nincs benne,
> azt nem mondjuk ki – elutasítás lesz. És ezt méröm: 57 kiértékelési eset,
> execution accuracy 1.0, nulla kitalált adat."

### „Melyik rész a legbátrabb technikailag?"

> „A tartalmi keresés és a hozzá tartozó darabszám. A felhasználó gyakran nem a
> jegyek mezőire kérdez, hanem a **tartalmukra** – 'milyen jegyek említenek
> bankkártya-elutasítást'. Ehhez kellett egy vektoros index, egy szöveges index, és
> egy determinisztikus összevonás. A részlet, amit büszke vagyok: a szemantikus
> küszöböt, ami eldönti, mi számít 'témához tartozónak', nem becsléssel választottam
> ki, hanem egy szisztematikus méréssel – a fejlesztői eseteken végigfuttattam egy
> küszöbsöprönget, és ahol a pontosság 1.0 volt, ott 0.2 volt a szomszédos
> küszöbökön. A dev- és a kiértékelési esetek szigorúan el vannak választva, a
> kalibráció nem látott kiértékelési adatot."

### „Milyen LLM-applikációkat épített valaha?"

> „Egyet, nagyon komolyan: ezt. De a fejlesztés során több offline pipeline-t is
> írtam – a jegyek szövegének generálását, az embeddingek kiszámítását, az
> adatbázis-importot, a küszöb-kalibrációt, és az optimalizálást. Ezek mind ugyanazt
> a fegyelmet követik: checkpoint/resume, determinisztikus ellenőrzés, verziózott
> kimenet."

### „Milyen értékelési pipeline-okat használt?"

> „Négy darabot. Az első a kiértékelési esetkészlet: külön fejlesztői és külön
> kiértékelési fájl, stabil azonosítókkal, és a kód maga tiltja, hogy a kiértékelési
> azonosító optimalizálásba kerüljön. A második a metrikakészlet, és itt fontos
> részlet: **minden metrika determinisztikus és modellmentes**. Nincs „hasonlónak
> tűnik-e a válasz" típusú becslés a release-gate-ben. A harmadik a regressziós
> összehasonlítás, ami nem-nulla hibakóddal bukik el minőségromlásra, tiltott
> adatbázis-hatásra vagy szivárgásra. A negyedik a biztonsági runner, ami **az
> adatbázis állapotát** hasonlítja össze minden eset előtt és után – így egy
> esetleges írás akkor is kiderülne, ha a válasz szépen úgy tenné, mintha minden
> rendben volna.
>
> A latencyot mérjük, de **nem** használjuk minőségi kapuként – ezt külön rögzítettem,
> mert a gyorsaság és a pontosság nem ugyanaz a dolog."

### „Milyen prompt injection védelem van?"

> „Négy réteg, és egyik sem a modell. Az első egy típus-szintű engedélyezési lista:
> a modell csak ismert mezőket és műveleteket választhat. A második egy
> determinisztikus validátor – tiszta függvény, nincs benne modellhívás, tehát
> ugyanaz a bemenet mindig ugyanazt a döntést adja. A harmadik az adatbázis rétegének
> szabályai: a lekérdezés csak explicit engedélyezett entitásokon mehet, és a
> limit le van szabva. A negyedik a **PostgreSQL jogosultság**: a futásidejű szerepk
> csak SELECT-et tud, és van rajta lekérdezés-időkorlát.
>
> Van egy injekció-osztályozóm is, de az **csak telemetria**, a nyomkövetésbe kerül –
> soha nem dönt engedélyezésről vagy tiltásról. Aki azt mondja, hogy egy
> prompt-injection-detektor védi a rendszert, az általában nem védi semmit. A
> védelem ott van, ahol a határ ténylegesen húzódik: az adatbázis és a
> lekérdezési réteg.
>
> És a biztonságot itt **hatás-alapon** mérjük, nem elutasítás-szöveg alapján."

### „És az adatvédelem, GDPR?"

> „A projekt adata szintetikus: egy MIT-licencelt, commit-pinned, ellenőrzött
> hash-ekkel rendelkező nyilvános helpdesk-adatkészlet. Nincs benne valós személyes
> adat. A nyomkövetésben nincs teljes prompt, nincs hitelesítő adat, és nincs a
> privát modell-endpoint címe. A válaszokhoz eleve nincs szükség valós
> személyes adatra.
>
> A GDPR igazi kihívásai itt a retention, a törlési kérelmek és az audit log
> lennének – ezek üzleti folyamatok, amelyeket a pipeline-ba kell beépíteni, nem
> LLM-problémák."

### „Hogyan monitoroznád a pontosságot és a költséget?"

> „A pontosságot a leírt regressziós gate-tel: baseline-ot rögzítünk, aztán minden
> változás – prompt, modell, adat, paraméter – után lefuttatjuk a változatlan
> kiértékelési eseteket, és a gate hasonlít. A baseline-nál mérjük a zajt is, több
> futással, hogy ne mondhassam, hogy javulás van, ha a sávok fedik egymást.
>
> A költséget a modellválasztás kezeli: a projekt egy fixen pinelt, saját gépen futó
> modellt használ, tehát a futtatás költsége nem API-díjak. Ahol van költség,
> ott batch feldolgozás és checkpoint/resume fut. A modellcseréhez nem kell
> architekturális újraírás: minden modellhívás egy OpenAI-kompatibilis kliensen
> megy át, tehát a provider cseréje adapter-rész."

### „Többnyelvű támogatás?"

> „Ez a legnagyobb hiányosság, amit a projektben ma el kell mondanom. A demó
> angol adaton fut, és a pipeline nyelve nem konfigurálható. Amit tennék: a
> kérdés nyelvének felismerése, azon felül a válasz nyelvének megválasztása a
> kérdés alapján, és a relevanciarangsorban a beágyazások nyelvi egyenértékűségének
> kezelése. Fontos, hogy a biztonsági és jogosultsági rétegek nyelvfüggetlenek –
> ezeket nem érinti."

### „Adatmodellezés, szemantikus réteg?"

> „A projektnek van egy központi definíciója az entitásokról, mezőkről és
> kapcsolatokról – ez a szerződés, amit a validátor és az adatbázis-policy is
> használ, tehát egy helyen van definiálva, és több réteg ugyanazt érvényesíti.
> Metrikák is vannak: darabszám, átlag, összeg, arány. Ami hiányzik, az egy
> verziózott **üzleti szótár**: a természetes nyelvű metrikadefiníciók és a
> mező-leképezések külön rétege. Ez a következő lépés, mert üzleti kollégáknál
> ez a legnagyobb belépési akadály."

### „Milyen adatbázis és hozzáférési modell?"

> „PostgreSQL, egy elválasztott sémával, táblákkal és indexekkel. Két szerepk van:
> az egyik a setup-hoz és az importhoz, a másik – ez a futásidejű – **csak
> SELECT-et tud**, lekérdezés-időkorlátal. A hozzáférés nem közvetlen SQL, hanem
> egy GraphQL-szerű réteg, explicit engedélyezési listával, alapértelmezés szerint
> **zárt** beállítással: ami nincs explicit engedélyezve, az blokkolt."

### „Mi a legnagyobb tanulság?"

> „Hogy a **mérés nem a végén jön, hanem előbb**. Az első verzióimban voltak olyan
> kérdések, amikre a rendszer 0-t adott, és amit sok mérnök „jó, hát a strukturált
> adat nincs ilyen oszlopban" alakban elintézett. Ehelyett kimértem, és kiderült,
> hogy nem hiba, hanem **hiányzó képesség** – ez külön, saját specifikációval,
> saját kapuval és külön kalibrációval készült feature lett. Ugyanez a minta
> ismétlődött a routing pontossággal: ott nem 1.0-t értünk el, hanem 0.9-et, és
> ehhez külön mérőszámot vezettem be – a hibás útvonal arányát –, hogy ne
> lehessen más értékekkel elfedni.
>
> A második tanulság: **a biztonságot nem a modellre kell bízni**. Amikor a
> prompt-alapú védelmet használtam, az csak látszatbiztonság volt. Amikor a
> határt a validátorba, a lekérdezési rétegbe és a jogosultságokba tettem, onnantól
> a védelem **mérhető** lett, és ezt tesztekkel tudtam bizonyítani."

### „Van Databricks Genie, Fabric vagy Joule tapasztalata?"

> „Nincs, és nem is fogom úgy tálalni, mintha lenne. Amit tudok mondani, hogy a
> projekt ugyanazokat az építőelemeket használja, amik ezekben a rendszerekben
> is vannak: szövegből structured query, entitás-allowlist, jogosultság a
> lekérdezési rétegben, értékelési és regressziós pipeline. Ezeket a mintákat
> tudom átülteni egy adott platformra – a konkrét platform API-ját meg kell
> tanulni, de a mögöttes tervezésem ott is ugyanaz."

---

## 3. Mi a DSPy? (ha rákérdeznek – beszélt nyelven)

**A legrövidebb válasz:**

> „A DSPy egy Python könyvtár, ahol nem promptokat írsz, hanem **deklarálod, mit
> akarsz** – milyen bemenetből milyen kimenetet –, és utána egy optimalizáló
> megtanítja neki a feladatot. A kódod nem változik, a betanított program cserélődik.
> Kicsit úgy, mint a unit tesztek helyett tanítóanyag: a program maga ugyanaz,
> de jobb becomes.**

**Miért ezt választottam a sima promptok helyett?**

1. „A pipeline **szignatúrákra** épül, nem szövegre. Van egy osztályozó
   szignatúra, egy tervező szignatúra és egy válaszadó szignatúra. Ha egy promptot
   módosítok, az egy verziózott döntés, nem egy ad-hoc szövegmódosítás."
2. „A legfontosabb: **mérhető, objektív metrikát** adok hozzá. Az optimalizáló csak
   akkor fogad el egy példát, ha *minden* feltétel teljesül – a kérés átmegy a
   validátoron, a lekérdezés lefut, az eredmény egyezik a várhatóval, és nincs
   tiltott hatás. Ez egy igen/nem metrika, nem egy becslés. Ha ez a metrika
   becslés lenne, akkor az optimalizálás egybecsüléseket optimalizálna."
3. „A **fejlesztői és a kiértékelési esetek el vannak választva**, és a kód
   megakadályozza, hogy a kiértékelési esetek optimalizálásba kerüljenek. Ezt a
   fegyelmet ténylegesen betartottam."
4. „Az optimalizálás **verziózott és reprodukálható**: futtatás után van egy fájl,
   amiben benne van, milyen bemenetekkel futott, melyik példákat fogadta el, milyen
   konfigurációval, mi volt a kimenet és a hash-e."
5. „Amit **nem** használtam: reflektív optimalizálókat és finomhangolást. Nem azért,
   mert rosszak, hanem mert a feladat determinisztikus, bináris metrikát ad – és
> ha később reflexív optimalizálást vezetnék be, az a metrika kifejezetten alkalmas
> rá."

**Fontos, amit érdemes hozzátenni:**

> „A DSPy itt **nem biztonsági határ**. Bármit a modell kiad, átmegy a
> determinisztikus validátoron, és a jogosultságot a GraphJin policy és a
> PostgreSQL szerepk adja. Az optimalizálás a pontosságot javítja, a biztonságot nem
> szabad függővé tenni tőle."

**A verziozás-történet, ha kell (feature 006):**

> „A DSPy-t 3.2.1-ről 3.4.0-ra frissítettem, és ezt nem csak „feltettem és működik"
> stílusban csináltam: a régi artifactokat byte-azonos módon megtartottam, csináltam
> új baseline-t, újraoptimalizáltam, és készítettem egy **cross-version összehasonlítást**,
> ami kimutatta, hogy a verzióváltás nem mozgatott egyetlen minőségi metrikát sem.
> Ez a fajta változáskezelés kell egy éles környezetben."

---

## 4. Mi a GraphJin? (ha rákérdeznek – beszélt nyelven)

**A legrövidebb válasz:**

> „A GraphJin egy GraphQL-szerű réteg, ami a PostgreSQL fölé kerül, és a
> **kormányozott hozzáférési határ** a projektben. A modell nem SQL-t ír, hanem
> mezőket és műveleteket választ egy engedélyezési listán belül; ezt a réteg
> alakítja lekérdezéssé, és a szabályok – mely entitás, mely mező, mely művelet,
> mekkora limit, mennyi idő – **kódban vannak, nem a promptban**.”

**Miért ezt választottam?**

1. „**A modell nem kap szabadságot.** Bármilyen mezőt választ, a réteg csak azt
   engedi át, ami explicit engedélyezett. Alapértelmezés szerint **zárt** a rendszer:
>   ami nincs felsorolva, az blokkolt. Ez a fail-closed szemlélet."
2. „**Két független határ.** Ha a policy-réteg valamiért megbukna, a
   PostgreSQL-szerepk akkor is csak SELECT-et tud. Bármelyik réteg hiányzik, a másik
   még mindig véd."
3. „**Könnyen tesztelhető és auditálható.** A biztonsági tesztek konkrétan
   kimutatják, hogy az INSERT, UPDATE, DELETE, TRUNCATE, CREATE, ALTER és DROP
   mind elbukik, és hogy az adatbázisban nulla változás történik."
4. „**A modell nem lát SQL-t**, tehát nincs SQL-injekciós felület sem a modell oldalán.”

**Amit a GraphJin nem tudott – és ez nagyon jó interjúpont:**

> „A GraphJin szemantikus keresése katalógus-szintű, nem jegy-szintű. A felhasználó
> viszont azt kérdezi: 'milyen jegyek szólnak a bankkártya-elutasításról' – ez
> jegy-szintű találatokat jelent. Ezt a projekt **döntéssel** kezelte: a tartalmi
> keresés külön, alkalmazás-oldali, kormányozott csatorna lett, fix paraméterezett
> lekérdezésekkel, explicit mező-listával, ugyanazzal a csak-olvasó szerepkkel és
> limittel. Fontos, hogy ez **nem** egy SQL-bypass: ugyanaz a szerepk, ugyanaz a
> mező-allowlist, más úton.
>
> Egy másik korlát: a csoportosítás utáni szűrés – a HAVING – a GraphJin verziójában
> nincs natívan, ezért azt a már lefuttatott sorokon, tiszta függvényként alkalmazom,
> ahol az ellenőrzés már megtörtént.”

---

## 5. Hogyan működik a projekt – ha végig akarod járni (folyamatban)

**A strukturált útvonal (számlálás, csoportosítás, szűrés):**

> „Kérdés → injekció-telemetria → DSPy osztályozás és tervezés → determinisztikus
> validátor → GraphJin GraphQL lekérdezés → PostgreSQL (csak olvasás) → eredmény
> normalizálás → csoportszűrés → grounding-ellenőrzés → determinisztikus redakció →
> válasz + tisztított nyomkövetés.
>
> Minden lépés hibája stabil, értelmes hibakódot ad – nem kitalált választ.”

**A tartalmi útvonal (keresés a jegyek szövegében):**

> „Kérdés → osztályozó kimondja, hogy tartalmi kérdés → a témát beágyazom →
> szöveges és szemantikus találatok lekérése → determinisztikus összevonás (RRF) →
> limit és szerepk kikötése → bizonyíték alapú válasz.
>
> A 'hány jegy szól X-ről' kérdés külön kategória: ott **valódi darabszámot** adok,
> limit nélkül, mert a keresési limit nem korlátozhatja a számlálást, és a
> nyomkövetésben megadok öt példa jegyazonosítót, hogy a szám ellenőrizhető legyen.”

**Az offline pipeline (a „komolyan veszem" rész):**

> „A jegyek szövegeit a pinelt modell generálja, offline módban, batchenként,
> checkpointtal, hogy félbeszakadás után folytatható legyen. Ezután egy determinisztikus
> validáció ellenőrzi: a séma, a teljes lefedettség, a hosszhatárok, a nyelv, a
> kategóriakonzisztencia és a NULL-szabály. Ezután emberi adatminőségi ellenőrzés
> kategóriánként. Végül a beágyazások készülnek, és **egy tranzakcióban** megy be
> minden az adatbázisba – a sorok, a szövegek és a vektorok együtt, atomikusan.”

---

## 6. A biztonság, ha bővebben rákérdeznek

> „A rendszer védelme négy réteg, és egyik sem a modell:
>
> 1. **Típus-szintű engedélyezési lista** – a modell csak ismert entitást, mezőt és
>    műveletet választhat.
> 2. **Determinisztikus validátor** – tiszta függvény, nincs benne modellhívás és
>    nincs I/O. Ugyanaz a bemenet mindig ugyanazt a döntést adja. Ez tipikushibákat is
>    elkap: ha a szűrő értéke nem fér össze a mező típusával, a kérés már itt
>    elhasal, és **egyáltalán nem** megy ki adatbázis-hívás.
> 3. **Lekérdezési réteg policy** – zárt alapértelmezés, limit, időkorlát.
> 4. **Adatbázis-szerepk** – csak SELECT, lekérdezés-időkorlát.
>
> Ezek **független** egymástól: az adatbázis-időkorlát, a teljes kérés-biztonsági
> időkorlát és a maximális eredményméret külön-külön is működik.
>
> A prompt injekciót az injekció-osztályozó csak **jelzi** – ez nyomkövetési adat.
> A védelem az első három rétegből jön. Teszt-csapokkal ellenőrzöm, hogy egy
> titok soha nem kerülhet vissza a válaszba, a nyomkövetésbe vagy a hibaüzenetbe.
>
> És a túlblokkolást is mérjük: ha egy jogos kérdést elutasítunk, az is hiba. A
> jelenlegi érték egy eset az ötvenhétszeresből, azaz körülbelül 2.4% – ezt nem
> rejtem el, hanem mérnöm.”

---

## 7. A mérés, ha bővebben rákérdeznek

> „A fegyelem a következő: az esetkészletek **fizikailag** el vannak választva –
> fejlesztői és kiértévelési fájl külön, plusz egy külön biztonsági fájl. A
> baseline-t **mérés előtt** rögzítem: rögzített verziók, nulla hőmérséklet, kikapcsolt
> cache, és több futás a zaj meghatározására. Csak ezután jön az optimalizálás, és
> csak a fejlesztői eseteken. Utána a **változatlan** kiértékelési esetkészlet fut
> újra, és a regressziós kapu hasonlít.
>
> A kapu nem-nulla hibakóddal bukik el, ha a minőség a küszöb alá esik, ha az
> execution accuracy több mint öt százalékpontot romlik, ha bármilyen tiltott
> adatbázis-hatás történt, vagy ha bármi jogosulatlanul kiszivárgott. A latency
> **csak** megfigyelt érték, nem kapu.
>
> A számok, amiket érdemes fejből tudni: 57 kiértékelési eset, ebből 16 biztonsági.
> Strukturális érvényesség 1.0, execution accuracy 1.0, nulla tiltott hatás, nulla
> szivárgás, routing pontosság 0.9 hibás routing arány 0.0, darabszám pontosság 1.0.
> Latency: medián 4.7 másodperc, kilencvenedik percentilis 11.1 másodperc, maximum
> 16.5 másodperc – ezek megfigyelési adatok.
>
> A teljes tesztkészlet 664 teszt, és minden feature-nek saját, ember által jóváhagyott
> kapuja van.”

---

## 8. Amit nem fogok eltitkolni (a legjobb pillanat erre a kérdésre)

> „Nincs minden, amit a hirdetés kér, a projektben kész. Ezeket érdemes előre tudni:
>
> - **LLM-as-a-judge nincs.** A metrikáim teljesen determinisztikusak, és ez erős
>   oldal, de ahol a helyesség nem programozható – például a válasz érthetősége,
>   hangneme –, ott LLM-bíró kellene. Calibrált ember-címkékkel és egyezési aránnyal
>   mérném, és csak kiegészítő mérésként használnám, nem kapuként.
> - **Többnyelvűség nincs.** A demó angol adaton fut.
> - **LLM-alapú újrarangsorolás nincs.** A jelenlegi alap a determinisztikus
>   összevonás. Egy LLM, ami tényleg elolvassa a kérdést és a találatokat,
>   pontosabb lehetne, de nem-determinisztikus, és minden találatra egy modellhívás.
>   Ezért mérném előbb, nem bevezetném vakon.
> - **Üzleti szótár réteg nincs** – a mezők és metrikák definiálva vannak, de
>   természetes nyelvű, verziózott leírásban nem.
> - **Kereső-újrarangsorolás mezőszinten** – most egy vektor van jegyenként, a három
>   szövegmező összefűzve. Ha egy kérdés egy konkrét mezőre célozna – 'hogyan
>   oldották meg' –, ez nem működne jól.
> - **Csoportosított darabszám tartalomra** – a 'hány jegy szól róla kategóriánként'
>   kérdés nincs meg.
> - **False refusal 2.4%** – egy legitim kérdés elutasítva. Ez is hiba, és mérjük.
> - **Szemantikus értelmetlenség nincs külön detektálva futásidőben.** A forma és a
>   validator a *jogutadást* kezeli; a *helyességet* a mérés. Egy jól formált,
>   engedélyezett, de értelmetlen kérés (pl. nem létező prioritásérték) lefut és nulla
>   sort ad – ezt ma csak utólag, a kiértékelésben látom. A következő lépés egy
>   „értelmetlen eredmény" detektor lenne: ha a szűrő nagyon szűk és az eredmény üres,
>   a rendszer magyarázatot kérne a felhasználótól, ahelyett hogy üres eredményt adna
>   vissza.
>
> Mindegyikre van konkrét tervem, és mindegyik a hirdetés egy-egy területéhez
> kapcsolódik.”

---

## 9. Kérdések, amiket te kérdezel a végén

1. „Nálatok a beszélgetéses analitika a **munkatársakon** belül van, vagy
> külső ügyfelekhez is? Milyen adatkörnyezetben fut – belső, valódi ITSM?
   Mert a projektem pont egy valódi helpdesk-adatmodellre épül, és ott a
   jogosultságkezelés és a szöveges tartalom a legnehezebb rész.”
2. „Milyen a **nyelv** a kérdések és a válaszok között? Magyar, angol, vegyes?
   Mert az embedding és a routing pont a nyelvfüggésben szokott elhasalni, és
   ezen a projekten pont ezt mértem.”
3. „A **mérés** a csapatban hogyan van működtetve? Van release-gate, vagy inkább
   manuális jóváhagyás? Én egy exit kódos regressziós gate-et építettem, ami
   tiltott adatbázis-hatásra is bukik – ez átvehető?”
4. „A modellek **hogyan vannak kiválasztva** – van egy jóváhagyott modelllista, vagy
   a csapat dönt? Én a modellt pineltem, és megtiltottam a fallbacket, mert a
   „temporarily another model" gyakorlat csendes minőségromlást okoz.”
5. „Van **GDPR / DPA** környezet, ahol érzékeny személyes adatok is érintettek?
   Mert a projektem egész biztonsági modellje arról szól, hogy a modell ne kapjon
   jogot; ha az érzékeny adatok a lekérdezési réteg alatt maradnak, ugyanez a modell
   működik, és a legkisebb kockázatú helyzet az, ha a modell egyáltalán nem látja őket.”

6. „Milyen a **csapatméret és a fejlesztési ritmus**? Én egy csapatban, kis
   léptékben, feature-szinten tudtam mindent dokumentálni és kapuzni – ha nálatok
   gyorsabb a ritmus, akkor a mérési fegyelem a legelső teendő, nem az utolsó.”

---

## 10. Puskák (egy lapon)

- **Projekt neve:** Governed Conversational Analytics
- **Adat:** szintetikus ITSM helpdesk, MIT-licenc, pinelt commit, 2057 ticket
- **Modellek:** Qwen3 27B (Q4_K_M) chat + EmbeddingGemma-2 (768 dim) külön instance-en
- **Verziók:** Python 3.14.4, DSPy 3.4.0, PostgreSQL 16 + pgvector 0.8.7, GraphJin v3
- **Kiértékelés:** 57 case (16 biztonsági), execution accuracy 1.0, 0 tiltott hatás,
  0 szivárgás, routing 0.9, count accuracy 1.0, latency median 4.7s / p90 11.1s / max 16.5s
- **Tesztek:** 664, minden feature-nek saját jóváhagyott kapu
- **Négy védelmi réteg:** allowlist → determinisztikus validátor → lekérdezési policy →
  csak-olvasó DB-szerepk
- **Injekció-osztályozó:** csak telemetria, soha nem dönt
- **A legjobb mondatod:** „A modell nem biztonsági határ. A határ ott van, ahol
  a rendszer ténylegesen korlátozva van, és ott mérhető is.”
- **A legjobb kérdésed:** „Milyen a mérés a csapatban – release-gate, vagy manuális
  jóváhagyás?”
