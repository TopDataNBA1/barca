# -*- coding: utf-8 -*-
"""
barca_monitor.py - Monitor en temps real FC Barcelona
"""

import json, time, threading, re, os, random, shutil
from copy import deepcopy
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
try:
    from PIL import Image
    PIL_DISPONIBLE = True
except ImportError:
    PIL_DISPONIBLE = False
    print("AVÍS: Pillow no instal·lat. Els collages no es generaran. Executa: pip install Pillow")

# ============================================================
# CONFIGURACIO -- editar abans de cada partit
# ============================================================

CARPETA       = r"C:\Users\USUARIO\Desktop\Top Data Barça"
BASELINE_FILE = os.path.join(CARPETA, "baseline.json")
DATA_FILE     = os.path.join(CARPETA, "data.json")
FOTOS_DIR     = os.path.join(CARPETA, "fotos_definitives")
COLLAGES_DIR  = os.path.join(CARPETA, "collages")
os.makedirs(COLLAGES_DIR, exist_ok=True)

INTERVAL   = 30

# URL i competició llegides del fitxer config.json
_config_path = os.path.join(CARPETA, "config.json")
if os.path.exists(_config_path):
    with open(_config_path, 'r', encoding='utf-8') as _f:
        _cfg = json.load(_f)
    PARTIT_URL = _cfg.get("url", "")
    # Detectar si la URL és un amistós/Gamper per sobreescriure el camp competicio
    _url_l = PARTIT_URL.lower()
    if any(x in _url_l for x in ('amistosos', 'amistoso', 'friendly')):
        COMPETICIO = 'Amistós'
    elif any(x in _url_l for x in ('gamper', 'trofeu', 'trophy')):
        COMPETICIO = 'Amistós (Gamper)'
    else:
        COMPETICIO = _cfg.get("competicio", "Liga")
else:
    PARTIT_URL = ""
    COMPETICIO = "Liga"

# Límit per mostrar la cua (si hi ha més, s'omet aquella part)
# Sense límit: sempre es notifica tota la cua

# ============================================================
# NORMALITZACIO DE NOMS: fcbarcelona.cat -> nom complet exacte del baseline.json
# ============================================================

NOM_MAP = {
    # Porters
    "Wojciech Szczesny":  "Wojciech Tomasz Szczęsny",
    "Szczesny":           "Wojciech Tomasz Szczęsny",
    "Wojciech Szczęsny":  "Wojciech Tomasz Szczęsny",
    "Iñaki Peña":         "Ignacio Peña Sotorres",
    "Joan García":        "Joan Garcia Pons",
    "Joan Garcia":        "Joan Garcia Pons",
    # Defenses
    "Ronald Araujo":      "Ronald Federico Araújo da Silva",
    "Ronald Araújo":      "Ronald Federico Araújo da Silva",
    "Jules Kounde":       "Jules Olivier Koundé",
    "Jules Koundé":       "Jules Olivier Koundé",
    "Pau Cubarsi":        "Pau Cubarsí Paredes",
    "Pau Cubarsí":        "Pau Cubarsí Paredes",
    "Eric García":        "Eric Garcia Martret",
    "Eric Garcia":        "Eric Garcia Martret",
    "Alejandro Balde":    "Alejandro Balde Martínez",
    "Iñigo Martínez":     "Iñigo Martínez",
    "Inigo Martinez":     "Iñigo Martínez",
    "Héctor Fort":        "Héctor Fort Gasull",
    "Hector Fort":        "Héctor Fort Gasull",
    "Gerard Martín":      "Gerard Martín Langreo",
    "Gerard Martin":      "Gerard Martín Langreo",
    "João Cancelo":       "João Pedro Cavaco Cancelo",
    "Joao Cancelo":       "João Pedro Cavaco Cancelo",
    "Ronald Araújo":      "Ronald Federico Araújo da Silva",
    # Migcampistes
    "Frenkie de Jong":    "Frenkie de Jong",
    "de Jong":            "Frenkie de Jong",
    "De Jong":            "Frenkie de Jong",
    "Frenkie De Jong":    "Frenkie de Jong",
    "Pedri":              "Pedro González López",
    "Gavi":               "Pablo Martín Páez Gavira",
    "Marc Casadó":        "Marc Casadó Torras",
    "Marc Casado":        "Marc Casadó Torras",
    "Marc Bernal":        "Marc Bernal Casas",
    "Dani Olmo":          "Daniel Olmo Carvajal",
    "Pablo Torre":        "Pablo Torre Carral",
    "Fermín López":       "Fermín López Marín",
    "Fermin Lopez":       "Fermín López Marín",
    # Davanters
    "Robert Lewandowski": "Robert Lewandowski",
    "Raphinha":           "Raphael Dias Belloli",
    "Lamine Yamal":       "Lamine Yamal Nasraoui Ebana",
    "Ferran Torres":     "Ferran Torres García",
    "Ansu Fati":          "Anssumane Fati Vieira",
    "Marcus Rashford":    "Marcus Rashford",
    "Roony Bardghji":     "Roony Bardghji",
    "Bardghji":           "Roony Bardghji",
    # Variants curtes (timeline substitucions)
    "Torres":             "Ferran Torres García",
    "López":              "Fermín López Marín",
    "Lopez":              "Fermín López Marín",
    "Pedri":              "Pedro González López",
    "Araujo":             "Ronald Federico Araújo da Silva",
    "Araújo":             "Ronald Federico Araújo da Silva",
    "Olmo":               "Daniel Olmo Carvajal",
    "Bernal":             "Marc Bernal Casas",
    "Gavi":               "Pablo Martín Páez Gavira",
    "Casado":             "Marc Casadó Torras",
    "Casadó":             "Marc Casadó Torras",
    "Fermín":             "Fermín López Marín",
    "Lewandowski":        "Robert Lewandowski",
    "Raphinha":           "Raphael Dias Belloli",
    "Yamal":              "Lamine Yamal Nasraoui Ebana",
    "Cancelo":            "João Pedro Cavaco Cancelo",
    "Koundé":             "Jules Olivier Koundé",
    "Kounde":             "Jules Olivier Koundé",
    "Cubarsí":            "Pau Cubarsí Paredes",
    "Cubarsi":            "Pau Cubarsí Paredes",
    "Balde":              "Alejandro Balde Martínez",
    "Fort":               "Héctor Fort Gasull",
    "Szczęsny":           "Wojciech Tomasz Szczęsny",
    "Szczesny":           "Wojciech Tomasz Szczęsny",
    "Rashford":           "Marcus Rashford",
    "Dani Rodríguez":   "Daniel Rodríguez Crespo",
    # Jugadors nous temporada 2026-27
    "Karim Adeyemi":         "Karim-David Adeyemi",
    "Adeyemi":              "Karim-David Adeyemi",
    "Anthony Gordon":      "Anthony Michael Gordon",
    "Gordon":              "Anthony Michael Gordon",
    "Rodrigo":            "Rodrigo Hernández Cascante",
    "Rodri":              "Rodrigo Hernández Cascante",
    "Rodrigo Hernández":  "Rodrigo Hernández Cascante",
    "Jesse Bisiwu":       "Jesse Bisiwu",
    "Bisiwu":             "Jesse Bisiwu",
    "Selim":              "Hamza Mohamed Abdelkarim Selim",
    "Hamza Abdelkarim":   "Hamza Mohamed Abdelkarim Selim",
    "Hamza":              "Hamza Mohamed Abdelkarim Selim",
}

# ============================================================
# ORDINALS EN CATALA
# ============================================================

def ordinal_cat(n):
    n = int(n)
    if n == 1: return "1r"
    if n == 2: return "2n"
    if n == 3: return "3r"
    if n == 4: return "4t"
    return f"{n}è"

# ============================================================
# BASELINE
# ============================================================

def carregar_baseline():
    """Indexa el baseline PER NOM COMPLET. Cap àlies, cap duplicat possible."""
    with open(BASELINE_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    indexat = {}
    for comp, jugadors in data.items():
        indexat[comp] = {}
        for j in jugadors:
            nom_complet = j['nom'].strip()
            if not nom_complet:
                continue
            indexat[comp][nom_complet] = {
                'alias': j.get('alias', '').strip(),
                'pj':    int(j.get('pj', 0) or 0),
                'g':     int(j.get('g',  0) or 0),
                'inici': j.get('inici', ''),
                'final': j.get('final', ''),
            }
    return indexat

# Index global àlies→nom_complet per a jugadors actius (final == any actual)
# Es construeix un cop carregat el baseline
_ALIAS_ACTIUS = {}  # àlies normalitzat → nom_complet

def construir_index_actius(baseline_raw_path=None):
    """Construeix un índex àlies→nom_complet NOMÉS per jugadors actius (final == any actual)."""
    global _ALIAS_ACTIUS
    import datetime
    any_actual = str(datetime.date.today().year)
    any_seguent = str(datetime.date.today().year + 1)
    path = baseline_raw_path or BASELINE_FILE
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    _ALIAS_ACTIUS = {}
    for j in data.get('Total', []):
        if str(j.get('final', '')) in (any_actual, any_seguent):
            alias = j.get('alias', '').strip()
            nom   = j.get('nom', '').strip()
            if alias and nom:
                _ALIAS_ACTIUS[alias.lower()] = nom
                # També indexem per paraules del nom (per variants curtes)
                for paraula in alias.split():
                    if len(paraula) > 3:
                        k = paraula.lower()
                        if k not in _ALIAS_ACTIUS:
                            _ALIAS_ACTIUS[k] = nom

def obtenir_stats(baseline, nom_complet, comp):
    """Cerca SEMPRE per nom complet. nom_complet ve de NOM_MAP o de normalitzar_nom."""
    buit = {'pj': 0, 'g': 0, 'inici': '', 'final': ''}
    return baseline.get(comp, {}).get(nom_complet, buit).copy()

def normalitzar_nom(nom_web):
    """Retorna el nom complet del baseline.
    Prioritat:
    1. NOM_MAP explícit
    2. Index d'actius (final == any actual) per àlies o paraula clau
    3. Nom tal qual (debutant o jugador no identificat)
    """
    # 1) NOM_MAP explícit
    if nom_web in NOM_MAP:
        nom = NOM_MAP[nom_web]
        # Verificació: si el nom apunta a un jugador no actiu però hi ha
        # un actiu amb el mateix àlies, usem l'actiu
        import datetime
        any_actual = str(datetime.date.today().year)
        nom_lower = nom_web.lower()
        if nom_lower in _ALIAS_ACTIUS:
            return _ALIAS_ACTIUS[nom_lower]
        return nom

    # 2) Index d'actius
    nom_lower = nom_web.lower()
    if nom_lower in _ALIAS_ACTIUS:
        return _ALIAS_ACTIUS[nom_lower]
    # Prova per cada paraula del nom_web
    for paraula in nom_web.split():
        if len(paraula) > 3 and paraula.lower() in _ALIAS_ACTIUS:
            return _ALIAS_ACTIUS[paraula.lower()]

    # 3) Retorna el nom tal qual (debutant)
    return nom_web

# ============================================================
# LOGICA DE NOTIFICACIONS
# ============================================================

def ranking_stat(baseline, comp, stat, baseline_total=None):
    bt = baseline_total or baseline
    jugadors = []
    for nom_complet, s in baseline.get(comp, {}).items():
        v = s.get(stat, 0)
        display = s.get('alias', '') or nom_complet
        pj = bt.get(comp, {}).get(nom_complet, {}).get('pj', 0)
        jugadors.append({'nom': display, 'nom_complet': nom_complet, 'valor': v, 'pj': pj, 'inici': s.get('inici',''), 'final': s.get('final','')})
    def sort_key_pj(x):
        return (-x['valor'], int(x['inici'] or 9999), -int(x['final'] or 0))
    def sort_key_g(x):
        # gols: valor desc, partits asc, inici asc, final desc
        pj = 0
        if stat == 'g':
            nc = x.get('nom_complet', x['nom'])
            entry = baseline.get('Total', {}).get(nc, {})
            pj = entry.get('pj', 0)
        return (-x['valor'], pj, int(x['inici'] or 9999), -int(x['final'] or 0))
    jugadors.sort(key=sort_key_g if stat == 'g' else sort_key_pj)
    return jugadors

def _fmt_noms(jugadors):
    def fmt(j):
        anys = f"{j['inici']}-{j['final']}" if j['inici'] and j['final'] else ""
        return f"{j['nom']} ({anys})" if anys else j['nom']
    ents = [fmt(j) for j in jugadors]
    if len(ents) == 1: return ents[0]
    return ", ".join(ents[:-1]) + f" i {ents[-1]}"

# Jugadors que ja han processat el seu PJ en aquest cicle
_JUGADORS_PARTIT_ACTUAL = set()  # tots els que han jugat
_TITULARS_ACTUALS = set()        # els 11 titulars (sumen simultàniament)

def reset_jugadors_partit():
    global _JUGADORS_PARTIT_ACTUAL, _TITULARS_ACTUALS
    _JUGADORS_PARTIT_ACTUAL = set()
    _TITULARS_ACTUALS = set()

def afegir_jugador_partit(nom_complet, titular=False):
    global _JUGADORS_PARTIT_ACTUAL, _TITULARS_ACTUALS
    # Usar l'àlies (clau del baseline_viu) en lloc del nom complet
    alias = _ALIAS_ACTIUS.get(nom_complet.lower(), nom_complet)
    # Intentar trobar l'àlies real del baseline_viu
    alias_curt = alias.split()[0] if ' ' in alias else alias
    _JUGADORS_PARTIT_ACTUAL.add(alias)
    if titular:
        _TITULARS_ACTUALS.add(alias)

def calcular_cua(baseline, baseline_viu, alias, comp, stat, valor_nou):
    alias_nc = alias if isinstance(alias, str) else str(alias)
    # Buscar nom complet
    nc = None
    for d in [baseline_viu.get('Total', {}), baseline.get('Total', {})]:
        if alias_nc in d:
            nc = d[alias_nc].get('alias_nc', alias_nc)
            break
    alias_nc_full = _ALIAS_ACTIUS.get(alias_nc.lower(), alias_nc)

    def ordre(j):
        return (int(j['inici'] or 9999), -int(j['final'] or 0))

    rk_hist = ranking_stat(baseline, comp, stat)
    rk_viu  = ranking_stat(baseline_viu, comp, stat)
    noms_viu = {j['nom_complet'] for j in rk_viu}
    rk_complet = list(rk_viu)
    for j in rk_hist:
        if j['nom_complet'] not in noms_viu:
            rk_complet.append(j)

    if valor_nou <= 1:
        superats = []
    else:
        superats = sorted([j for j in rk_complet if j['nom_complet'] != alias_nc_full and j['valor'] == valor_nou - 1], key=ordre)
    empatats = sorted([j for j in rk_complet if j['nom_complet'] != alias_nc_full and j['valor'] == valor_nou], key=ordre)

    if stat == 'pj' and alias_nc_full in _TITULARS_ACTUALS:
        # Comparar per 'nom' (àlies, clau del baseline_viu) en lloc de 'nom_complet'
        superats = [j for j in superats if j['nom'] not in _TITULARS_ACTUALS and j['nom_complet'] not in _TITULARS_ACTUALS]
        empatats = [j for j in empatats if j['nom'] not in _TITULARS_ACTUALS and j['nom_complet'] not in _TITULARS_ACTUALS]

    lloc = sum(1 for j in rk_hist if j['valor'] > valor_nou) + 1
    parts = []
    if superats:
        parts.append(f"Supera {_fmt_noms(superats)}")
    if empatats:
        parts.append(f"Empata amb {_fmt_noms(empatats)}")
    # Sempre afegir LLOC perquè la notificació es generi
    parts.append(f"__LLOC__{lloc}")

    noms_superats = [j['nom_complet'] for j in superats]
    noms_empatats = [j['nom_complet'] for j in empatats]
    return parts, noms_superats, noms_empatats


def es_milestone(v):
    return v > 0 and v % 100 == 0

def posicio_milestone(baseline, alias, comp, stat, valor):
    rk = ranking_stat(baseline, comp, stat)
    return sum(1 for j in rk if j['valor'] >= valor or j['nom'] == alias)

def text_comp(comp):
    return {"Liga": "Lliga", "Champions": "Lliga de Campions", "Copa": "Copa", "Supercopa": "Supercopa"}.get(comp, comp)


def _actualitzar_baseline(baseline, alias, comp, stat):
    """Actualitza el baseline_viu en memòria després de processar un jugador."""
    for c in ['Total', comp]:
        if alias in baseline.get(c, {}):
            baseline[c][alias][stat] = baseline[c][alias].get(stat, 0) + 1

def _construir_text_cua(parts_cua, comp_label):
    """Construeix el text final de la cua a partir de les parts retornades per calcular_cua."""
    lloc = None
    parts_text = []
    for p in parts_cua:
        if p.startswith("__LLOC__"):
            lloc = int(p.replace("__LLOC__", ""))
        else:
            parts_text.append(p)
    te_superats = any('Supera' in p for p in parts_text)
    te_empatats = any('Empata' in p for p in parts_text)
    text = ". ".join(parts_text)
    if lloc:
        if te_empatats:
            text += f" en el ➡️ {ordinal_cat(lloc)} lloc històric del club{comp_label}."
        elif te_superats:
            text += f" i ara ocupa el ➡️ {ordinal_cat(lloc)} lloc històric del club{comp_label}."
        else:
            text += f". Ocupa el ➡️ {ordinal_cat(lloc)} lloc històric del club{comp_label}."
    elif parts_text:
        text += "."
    return text

def generar_notificacions_partits(baseline, baseline_viu, nom_web, comp, pj_total_ant, pj_comp_ant):
    """Notificacions de partits jugats (total i competicio)."""
    alias = normalitzar_nom(nom_web)
    stats_display = obtenir_stats(baseline_viu, alias, "Total")
    display = stats_display.get('alias', '') or alias
    tc    = text_comp(comp)
    notifs = []

    for (comp_bd, valor, desc, comp_label) in [
        ("Total", pj_total_ant + 1, "partit oficial", ""),
        (comp,    pj_comp_ant  + 1, f"partit de {tc}", f" a la {tc}"),
    ]:
        parts_cua, noms_sup, noms_emp = calcular_cua(baseline, baseline_viu, alias, comp_bd, "pj", valor)
        cua_text  = _construir_text_cua(parts_cua, comp_label)
        milestone = es_milestone(valor)
        if not cua_text and not milestone:
            continue
        text = f"{ordinal_cat(valor)} {desc} per a {display} amb el Barça"
        if cua_text:
            text += f". {cua_text}"
        if milestone:
            pos = posicio_milestone(baseline, alias, comp_bd, "pj", valor)
            text += f". {display} es converteix en el {ordinal_cat(pos)} jugador que arriba als {valor} {desc}s amb el Barça."
        collage = collage_per_notif(baseline_viu, alias, noms_sup, noms_emp)
        notifs.append({'text': text, 'collage': collage})

    return notifs

def generar_notificacio_gol(baseline, baseline_viu, nom_web, comp, g_tot_ant, g_com_ant):
    """Notificacions de gol (total i competició)."""
    alias = normalitzar_nom(nom_web)
    stats_display = obtenir_stats(baseline_viu, alias, "Total")
    display = stats_display.get('alias', '') or alias
    tc    = text_comp(comp)
    notifs = []

    for (comp_bd, valor, scope, comp_label) in [
        ("Total", g_tot_ant + 1, "amb el Barça", ""),
        (comp,    g_com_ant + 1, f"a la {tc} amb el Barça", f" a la {tc}"),
    ]:
        parts_cua, noms_sup, noms_emp = calcular_cua(baseline, baseline_viu, alias, comp_bd, "g", valor)
        cua_text  = _construir_text_cua(parts_cua, comp_label)
        milestone = es_milestone(valor)
        if not cua_text and not milestone:
            continue
        text = f"⚽ {ordinal_cat(valor)} gol de {display} {scope}"
        if cua_text:
            text += f". {cua_text}"
        if milestone:
            pos = posicio_milestone(baseline, alias, comp_bd, "g", valor)
            text += f". {display} es converteix en el {ordinal_cat(pos)} jugador que arriba als {valor} gols {scope}."
        collage = collage_per_notif(baseline_viu, alias, noms_sup, noms_emp)
        notifs.append({'text': text, 'collage': collage})

    return notifs

# ============================================================
# FOTOS I COLLAGES
# ============================================================

def trobar_foto(nom_complet):
    """Retorna el path de la foto o None si no existeix."""
    if not PIL_DISPONIBLE:
        return None
    for ext in ('.jpg', '.png'):
        path = os.path.join(FOTOS_DIR, f"{nom_complet}{ext}")
        if os.path.exists(path):
            return path
    return None

def resize_foto(img, target_w, target_h):
    """Redimensiona i recorta centrant la imatge."""
    ratio = max(target_w / img.width, target_h / img.height)
    new_w = int(img.width * ratio)
    new_h = int(img.height * ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top  = int((new_h - target_h) * 0.25)  # lleugerament cap amunt per centrar la cara
    top  = max(0, min(top, new_h - target_h))
    return img.crop((left, top, left + target_w, top + target_h))

def crear_collage(foto_actual, fotos_empatats, fotos_superats):
    """
    Crea un collage amb:
    - foto_actual: path de la foto del jugador actual (sempre primer)
    - fotos_empatats: llista de paths dels empatats
    - fotos_superats: llista de paths dels superats
    Ordre: actual → empatats → superats
    Màxim 8 fotos. Si n'hi ha més, tria aleatòriament entre empatats+superats.
    """
    if not PIL_DISPONIBLE:
        return None

    # Construïm la llista ordenada
    altres = fotos_empatats + fotos_superats
    if len(altres) > 7:
        altres = random.sample(altres, 7)
    fotos = ([foto_actual] if foto_actual else []) + altres
    fotos = [f for f in fotos if f and os.path.exists(f)]

    if not fotos:
        return None

    n = len(fotos)
    canvas = Image.new('RGBA', (1200, 800), (0, 0, 0, 0))

    if n == 1:
        targets   = [(1000, 800)]
        positions = [(100, 0)]
    elif n == 2:
        targets   = [(600, 800), (600, 800)]
        positions = [(0, 0), (600, 0)]
    elif n == 3:
        targets   = [(600, 800), (600, 400), (600, 400)]
        positions = [(0, 0), (600, 0), (600, 400)]
    elif n == 4:
        targets   = [(600, 400), (600, 400), (600, 400), (600, 400)]
        positions = [(0, 0), (600, 0), (0, 400), (600, 400)]
    elif n == 5:
        targets   = [(600, 400), (600, 400), (600, 400), (300, 400), (300, 400)]
        positions = [(0, 0), (600, 0), (0, 400), (600, 400), (900, 400)]
    elif n == 6:
        targets   = [(600, 400), (600, 400), (300, 400), (300, 400), (300, 400), (300, 400)]
        positions = [(0, 0), (600, 0), (0, 400), (300, 400), (600, 400), (900, 400)]
    elif n == 7:
        targets   = [(600, 400), (300, 400), (300, 400), (300, 400), (300, 400), (300, 400), (300, 400)]
        positions = [(0, 0), (600, 0), (900, 0), (0, 400), (300, 400), (600, 400), (900, 400)]
    else:  # 8
        targets   = [(300, 400)] * 8
        positions = [(0,0),(300,0),(600,0),(900,0),(0,400),(300,400),(600,400),(900,400)]

    for i, path in enumerate(fotos[:len(targets)]):
        try:
            img = Image.open(path).convert('RGBA')
            img = resize_foto(img, targets[i][0], targets[i][1])
            canvas.paste(img, positions[i], img)
        except Exception as e:
            print(f"Error processant foto {path}: {e}")

    uid = f"{int(time.time() * 1000000)}"
    out = os.path.join(COLLAGES_DIR, f"collage_{uid}.webp")
    canvas.save(out, 'WEBP', quality=85)
    return f"collages/{os.path.basename(out)}"

def collage_per_notif(baseline_viu, alias_nc, superats_noms, empatats_noms):
    """
    Prepara i crea el collage per a una notificació.
    alias_nc: nom complet del jugador actual
    superats_noms / empatats_noms: llistes de noms complets
    """
    foto_actual   = trobar_foto(alias_nc)
    fotos_emp     = [f for f in (trobar_foto(n) for n in empatats_noms) if f]
    fotos_sup     = [f for f in (trobar_foto(n) for n in superats_noms) if f]
    return crear_collage(foto_actual, fotos_emp, fotos_sup)

# ============================================================
# SCRAPING FCBARCELONA.CAT
# ============================================================

def init_driver():
    opts = Options()
    opts.add_argument('--headless')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    return webdriver.Chrome(options=opts)

def scrape_partit(driver, url):
    driver.get(url)
    time.sleep(6)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    estat = {'xi_barca': [], 'canvis': [], 'gols_barca': [], 'finalitzat': False, 'fixture_status': 'U'}

    # XI inicial del Barça
    for div in soup.find_all('div', class_='team-line-up--starting'):
        nom_eq = div.find('div', class_='team-line-up__team-name')
        if not nom_eq or 'Barcelona' not in nom_eq.get_text():
            continue
        for p in div.find_all('div', class_='team-line-up__player'):
            el = p.find('div', class_='team-line-up__player-name')
            if el:
                estat['xi_barca'].append(el.get_text(strip=True))

    # Canvis del Barça - via timeline
    # Cada event --sub té 2 jugadors: [0]=surt, [1]=entra
    for ev in soup.find_all('div', class_='timeline__event'):
        cls = ev.get('class', [])
        if 'timeline__event-barca' not in cls or 'timeline__event--sub' not in cls:
            continue
        jugs = ev.find_all('div', class_='timeline-eo__player-name')
        if len(jugs) >= 2:
            nom_entra = jugs[1].get_text(strip=True)  # segon = el que entra
            nom_surt  = jugs[0].get_text(strip=True)  # primer = el que surt
            estat['canvis'].append({'entra': nom_entra, 'surt': nom_surt})

    # Gols del Barça
    for ev in soup.find_all('div', class_='timeline__event'):
        cls = ev.get('class', [])
        if 'timeline__event-barca' not in cls or 'timeline__event--goal' not in cls:
            continue
        jug = ev.find('div', class_='timeline-eo__player-name')
        if jug:
            estat['gols_barca'].append({'jugador': jug.get_text(strip=True)})

    # Estat del partit via data-fixture-status:
    # U = Upcoming, L = Live, F = Finished
    status_tag = soup.find(attrs={'data-fixture-status': True})
    if status_tag:
        fixture_status = status_tag['data-fixture-status']
        estat['fixture_status'] = fixture_status
        if fixture_status in ('F', 'C'):  # F=Finished, C=Completed
            estat['finalitzat'] = True
    else:
        estat['fixture_status'] = 'U'
        estat['finalitzat'] = False

    # Compte enrere (si fixture_status == 'U')
    # Enviem el timestamp Unix de quan comença el partit
    # Així la web sempre calcula correctament independentment de quan s'actualitza
    dies = soup.find('span', class_='js-countdown-days')
    hores = soup.find('span', class_='js-countdown-hours')
    mins  = soup.find('span', class_='js-countdown-minutes')
    segs  = soup.find('span', class_='js-countdown-seconds')
    if dies and hores and mins:
        import time as _time
        d = int(dies.get_text(strip=True) or 0)
        h = int(hores.get_text(strip=True) or 0)
        m = int(mins.get_text(strip=True) or 0)
        s = int(segs.get_text(strip=True) or 0) if segs else 0
        total_segs = d*86400 + h*3600 + m*60 + s
        estat['kickoff_ts'] = int(_time.time()) + total_segs
        estat['compte_enrere'] = f"{d}d {h}h {m}m {s}s"
    else:
        estat['kickoff_ts'] = None
        estat['compte_enrere'] = None

    return estat

# Lock global per evitar escriptures concurrents al data.json
import threading
_json_lock = threading.Lock()

# ============================================================
# COLA DE NOTIFICACIONS
# ============================================================

class ColaNotificacions:
    def __init__(self):
        self.programada  = []
        self.prioritaria = []
        self.lock    = threading.Lock()
        self.running = True
        self.thread  = threading.Thread(target=self._consumir, daemon=True)
        self.thread.start()

    def afegir_programada(self, notif):
        """notif pot ser un string o un dict {'text':..., 'collage':...}"""
        with self.lock:
            if isinstance(notif, str):
                notif = {'text': notif}
            notif.update({'tipus': 'programada', 'ts': datetime.now().isoformat()})
            self.programada.append(notif)

    def afegir_prioritaria(self, notif):
        """notif pot ser un string o un dict {'text':..., 'collage':...}"""
        with self.lock:
            if isinstance(notif, str):
                notif = {'text': notif}
            notif.update({'tipus': 'prioritaria', 'ts': datetime.now().isoformat()})
            self.prioritaria.append(notif)

    def _consumir(self):
        while self.running:
            notif = None
            with self.lock:
                if self.prioritaria:
                    notif = self.prioritaria.pop(0)
                elif self.programada:
                    notif = self.programada.pop(0)
            if notif:
                self._publicar(notif)
                time.sleep(60 if notif['tipus'] == 'programada' else 2)
            else:
                time.sleep(5)

    def _publicar(self, notif):
        hora = datetime.now().strftime('%H:%M')
        print(f"[{notif['tipus'].upper()}] {hora} | {notif['text']}")
        _guardar_notificacio(notif)

    def stop(self):
        self.running = False

def _guardar_notificacio(notif):
    with _json_lock:
        data = {}
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        entrada = {
            'text':  notif['text'],
            'tipus': notif['tipus'],
            'hora':  datetime.now().strftime('%H:%M'),
            'ts':    notif['ts'],
        }
        if notif.get('collage'):
            entrada['collage'] = notif['collage']
        data.setdefault('notificacions', []).append(entrada)
        data['ultima_actualitzacio'] = datetime.now().strftime('%H:%M:%S')
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def _restar_baseline(baseline, alias, comp, stat):
    """Resta 1 al stat d'un jugador al baseline_viu."""
    for c in ['Total', comp]:
        if alias in baseline.get(c, {}):
            val = baseline[c][alias].get(stat, 0)
            if val > 0:
                baseline[c][alias][stat] = val - 1

def _esborrar_notificacions_gol(alias, comp):
    """Esborra les notificacions de gol més recents d'un jugador del data.json."""
    with _json_lock:
        if not os.path.exists(DATA_FILE):
            return
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        import re as _re
        notifs = data.get('notificacions', [])
        # Trobar i esborrar les 2 últimes notificacions de gol d'aquest jugador (Total i comp)
        esborrats = 0
        for i in range(len(notifs)-1, -1, -1):
            t = _re.sub(r'<[^>]+>', '', notifs[i].get('text', '')).strip()
            if f'gol de' in t.lower() and alias.lower() in t.lower() and esborrats < 2:
                print(f"  Esborrant gol rectificat: {t[:60]}")
                del notifs[i]
                esborrats += 1
            if esborrats >= 2:
                break
        data['notificacions'] = notifs
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def guardar_baseline_a_data(baseline):
    """Escriu el baseline al data.json perque la web pugui mostrar els ranquings."""
    with _json_lock:
        data = {}
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        # Conservar final='2027' a Champions i Copa del baseline existent
        bl_existent = data.get('baseline', {})
        data['baseline'] = baseline
        for comp in ['Champions', 'Copa']:
            if comp in bl_existent and comp in data['baseline']:
                for nom, s in data['baseline'][comp].items():
                    if nom in bl_existent[comp] and str(bl_existent[comp][nom].get('final','')) == '2027':
                        s['final'] = '2027'
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

SESSIO_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sessio_actual.json')

def _guardar_sessio(xi_fet, gols_processats, canvis_processats):
    """Guarda l'estat de la sessió en fitxer separat per permetre reinicis sense duplicats."""
    with open(SESSIO_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            'xi_fet': xi_fet,
            'gols': list(gols_processats),
            'canvis': list(canvis_processats),
        }, f, ensure_ascii=False, indent=2)

def guardar_estat_partit(status, comp='', rival='', proper_partit=None):
    """Escriu l'estat del partit al data.json perque la web el mostre."""
    with _json_lock:
        data = {}
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        data['match_status'] = status  # U, L, F
        data['match_comp']   = comp
        data['match_rival']  = rival
        if proper_partit:
            data['proper_partit'] = proper_partit
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

# ============================================================
# BUCLE PRINCIPAL
# ============================================================

BDFUTBOL_URLS = {
    "Total":     "https://www.bdfutbol.com/e/egols1.html",
    "Liga":      "https://www.bdfutbol.com/e/e1a1.html",
    "Champions": "https://www.bdfutbol.com/e/echa1.html",
    "Copa":      "https://www.bdfutbol.com/e/ecop1.html",
}

def sincronitzar_baseline_bdfutbol(driver):
    """Scraping de bdfutbol i actualitzacio de baseline.json.
    Detecta els indexos per capcalera per ser robust a canvis d'estructura."""
    print("Sincronitzant baseline amb bdfutbol...")
    baseline_nou = {}
    for comp, url in BDFUTBOL_URLS.items():
        print(f"  {comp}: {url}")
        try:
            driver.get(url)
            time.sleep(6)
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            tablas = soup.find_all('table')
            jugadors = []
            for tabla in reversed(tablas):
                rows = tabla.find_all('tr')
                if len(rows) < 5:
                    continue
                cabecera = [td.get_text(strip=True) for td in rows[0].find_all(['th','td'])]
                if 'PJ' not in cabecera:
                    continue

                # Indexos fixos per posicio (estables a bdfutbol)
                I_ALIAS = 3
                I_NOM   = 4

                # Indexos per capcalera (normalitzant a majuscules)
                cab_norm = [c.strip().upper() for c in cabecera]
                def idx(nom):
                    try: return cab_norm.index(nom.strip().upper())
                    except ValueError: return None

                i_pj = idx('PJ')
                i_pt = idx('PT')
                i_pc = idx('PC')
                i_ps = idx('PS')
                i_g  = idx('G')

                if i_pj is None or i_g is None:
                    continue

                # Detectar inici i final per anys de 4 digits
                i_inici = None
                i_final = None
                if len(rows) > 1:
                    cel_p = [td.get_text(strip=True) for td in rows[1].find_all(['th','td'])]
                    anys = [(j, c) for j, c in enumerate(cel_p)
                            if c.strip().isdigit() and len(c.strip()) == 4
                            and 1900 <= int(c.strip()) <= 2030]
                    if len(anys) >= 2:
                        i_inici = anys[-2][0]
                        i_final = anys[-1][0]
                    elif len(anys) == 1:
                        i_inici = anys[0][0]

                for row in rows[1:]:
                    cel = [td.get_text(strip=True) for td in row.find_all(['th','td'])]
                    if len(cel) <= max(x for x in [I_NOM, i_pj, i_g] if x is not None):
                        continue

                    def get(i):
                        if i is None or i >= len(cel): return ''
                        return cel[i].strip()

                    alias = get(I_ALIAS)
                    nom   = get(I_NOM)
                    if not nom and not alias:
                        continue
                    jugadors.append({
                        'alias': alias, 'nom': nom,
                        'inici': get(i_inici),
                        'final': get(i_final),
                        'pj':    get(i_pj),
                        'pt':    get(i_pt),
                        'pc':    get(i_pc),
                        'ps':    get(i_ps),
                        'g':     get(i_g),
                    })
                print(f"    {len(jugadors)} jugadors")
                actuals = [j for j in jugadors if j.get('final') == '2026']
                print(f"    Actuals (2026): {len(actuals)}")
                if actuals:
                    print(f"    Mostra: {actuals[0]['alias']} PJ={actuals[0]['pj']} G={actuals[0]['g']}")
                break
            baseline_nou[comp] = jugadors
        except Exception as e:
            print(f"  Error {comp}: {e}")
            baseline_nou[comp] = []

    if all(len(v) > 100 for v in baseline_nou.values()):
        # Conservar final='2027' del baseline local
        if os.path.exists(BASELINE_FILE):
            try:
                with open(BASELINE_FILE, 'r', encoding='utf-8') as f:
                    bl_local = json.load(f)
                noms_2027 = set()
                for comp_l, jugadors_l in bl_local.items():
                    if not isinstance(jugadors_l, list): continue
                    for j in jugadors_l:
                        if str(j.get('final','')) == '2027':
                            noms_2027.add(j.get('nom',''))
                for comp_n, jugadors_n in baseline_nou.items():
                    if not isinstance(jugadors_n, list): continue
                    for j in jugadors_n:
                        if j.get('nom','') in noms_2027:
                            j['final'] = '2027'
                        # Conservar àlies del local
                        for jl in bl_local.get(comp_n, []) if isinstance(bl_local.get(comp_n), list) else []:
                            if jl.get('nom') == j.get('nom') and jl.get('alias'):
                                j['alias'] = jl['alias']
                                break
            except Exception as e:
                print(f"  Avís conservar 2027: {e}")
        with open(BASELINE_FILE, 'w', encoding='utf-8') as f:
            json.dump(baseline_nou, f, ensure_ascii=False, indent=2)
        print("baseline.json actualitzat des de bdfutbol.")
        return True
    else:
        print("AVIS: Dades incompletes de bdfutbol, es mante baseline.json existent.")
        return False

def _ordinal_val(t):
    import re as _re
    m = _re.search(r'(\d+)[èrnt]', t)
    return int(m.group(1)) if m else None

def _ranking_stat_bl(bl, comp, stat):
    jugadors = []
    for nom, s in bl.get(comp, {}).items():
        jugadors.append({'nom_complet': nom, 'valor': s.get(stat,0),
                        'inici': s.get('inici',''), 'final': s.get('final',''),
                        'pj': bl.get('Total',{}).get(nom,{}).get('pj',0)})
    def sort_key(x):
        if stat == 'g':
            return (-x['valor'], x['pj'], int(x['inici'] or 9999), -int(x['final'] or 0))
        return (-x['valor'], int(x['inici'] or 9999), -int(x['final'] or 0))
    jugadors.sort(key=sort_key)
    return jugadors

def _lloc_esperat_bl(bl, nom_complet, comp, stat, valor):
    rk = _ranking_stat_bl(bl, comp, stat)
    return sum(1 for j in rk if j['valor'] > valor) + 1

def corregir_notificacions_data(baseline):
    """Comprova i corregeix els llocs de totes les notificacions del data.json."""
    import re as _re
    if not os.path.exists(DATA_FILE):
        return
    with _json_lock:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

    ALIAS_NOTIF = {
        'Joan Garcia': 'Joan Garcia Pons',
        'Balde': 'Alejandro Balde Martínez',
        'Gerard Martín': 'Gerard Martín Langreo',
        'Cubarsí': 'Pau Cubarsí Paredes',
        'Araújo': 'Ronald Federico Araújo da Silva',
        'Eric Garcia': 'Eric Garcia Martret',
        'Fermín': 'Fermín López Marín',
        'Gavi': 'Pablo Martín Páez Gavira',
        'Lamine Yamal': 'Lamine Yamal Nasraoui Ebana',
        'Ferran Torres': 'Ferran Torres García',
        'Casadó': 'Marc Casadó Torras',
        'Rashford': 'Marcus Rashford',
        'Dani Olmo': 'Daniel Olmo Carvajal',
        'De Jong': 'Frenkie de Jong',
        'Lewandowski': 'Robert Lewandowski',
        'Koundé': 'Jules Olivier Koundé',
        'Bardghji': 'Roony Bardghji',
        'João Cancelo': 'João Pedro Cavaco Cancelo',
        'Pedri': 'Pedro González López',
        'Raphinha': 'Raphael Dias Belloli',
        'Ter Stegen': 'Marc-André ter Stegen',
        'Christensen': 'Andreas Bødtker Christensen',
        'Iñaki Peña': 'Ignacio Peña Sotorres',
        'Szczęsny': 'Wojciech Tomasz Szczęsny',
        'Bernal': 'Marc Bernal Casas',
    }

    def norm_txt(t):
        return _re.sub(r'<[^>]+>', '', t).strip()

    corregides = 0
    for i, notif in enumerate(data.get('notificacions', [])):
        text_html = notif.get('text', '')
        t = norm_txt(text_html)
        if t.startswith('📋'):
            continue

        is_gol = t.startswith('⚽')

        if is_gol:
            m_jug = _re.search(r'gol de ([^\s]+(?:\s[^\s]+)?)\s', t)
        else:
            m_jug = _re.search(r'per a ([^a-z][^\s.]+(?:\s[^\s.]+)?)', t)
        if not m_jug:
            continue
        alias_raw = m_jug.group(1).strip().rstrip('.')
        nom_complet = ALIAS_NOTIF.get(alias_raw)
        if not nom_complet:
            continue

        valor = _ordinal_val(t)
        if not valor:
            continue

        if is_gol:
            if 'Lliga de Campions' in t:
                comp_bd = 'Champions'
            elif 'Lliga' in t and 'Campions' not in t:
                comp_bd = 'Liga'
            elif 'Copa' in t:
                comp_bd = 'Copa'
            else:
                comp_bd = 'Total'
        else:
            if 'Lliga de Campions' in t:
                comp_bd = 'Champions'
            elif 'de Lliga' in t and 'Campions' not in t:
                comp_bd = 'Liga'
            elif 'de Copa' in t:
                comp_bd = 'Copa'
            else:
                comp_bd = 'Total'

        m_lloc = _re.search(r'➡️\s*(\d+)è', text_html)
        if not m_lloc:
            continue
        lloc_text = int(m_lloc.group(1))
        lloc_calc = _lloc_esperat_bl(baseline, nom_complet, comp_bd,
                                     'g' if is_gol else 'pj', valor)

        if lloc_text != lloc_calc:
            nou_html = _re.sub(r'➡️\s*\d+è', f'➡️ {ordinal_cat(lloc_calc)}', text_html)
            data['notificacions'][i]['text'] = nou_html
            corregides += 1

    if corregides:
        with _json_lock:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Notificacions corregides: {corregides}")
    else:
        print("Totes les notificacions son correctes.")

COMPETICIONS_NO_COMPUTEN = {
    'amistosos', 'amistoso', 'friendly', 'trofeu', 'trophy',
    'gamper', 'supercopa', 'supercup', 'international champions cup', 'icc',
}

def detectar_competicio_url(url):
    url_l = url.lower()
    if 'amistosos' in url_l or 'amistoso' in url_l or 'friendly' in url_l:
        return 'Amistós', False
    if 'gamper' in url_l or 'trofeu' in url_l or 'trophy' in url_l:
        return 'Amistós (Gamper)', False
    if 'supercopa' in url_l or 'supercup' in url_l:
        return 'Supercopa', False
    if 'champions' in url_l or 'lliga-de-campions' in url_l:
        return 'Champions', True
    if 'copa' in url_l:
        return 'Copa', True
    if 'la-liga' in url_l or 'liga' in url_l:
        return 'Liga', True
    return 'Desconeguda', False

def mostrar_propers_partits(driver):
    """Mostra els 5 propers partits per consola amb competicio i si computa."""
    CALENDARI_URL = "https://www.fcbarcelona.cat/ca/futbol/primer-equip/calendari"
    driver.get(CALENDARI_URL)
    time.sleep(6)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    vistos = set()
    propers = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if not re.search(r'/ca/partits/\d+/', href):
            continue
        url = href if href.startswith('http') else 'https://www.fcbarcelona.cat' + href
        if url in vistos:
            continue

        # Buscar status al contenidor
        contenidor = a
        status = None
        for _ in range(8):
            contenidor = contenidor.find_parent()
            if contenidor is None:
                break
            s = contenidor.get('data-fixture-status') or contenidor.get('data-status')
            if s:
                status = s
                break

        if status not in ('U', None):
            continue

        vistos.add(url)
        comp, computa = detectar_competicio_url(url)

        # Extreure rival de la URL
        m = re.search(r'fc-barcelona-(.+?)-(?:la-liga|copa|champions|amistosos|supercopa|lliga|gamper|trofeu)', url)
        if m:
            rival = m.group(1).replace('-', ' ').title()
            barca_fora = False
        else:
            m2 = re.search(r'/\d+/(.+?)-fc-barcelona', url)
            rival = m2.group(1).replace('-', ' ').title() if m2 else url
            barca_fora = True

        propers.append({'url': url, 'comp': comp, 'computa': computa,
                        'rival': rival, 'fora': barca_fora})

        if len(propers) >= 5:
            break

    print("Propers partits:")
    for i, p in enumerate(propers):
        fora_txt = " (fora)" if p['fora'] else ""
        computa_txt = "✓" if p['computa'] else "✗ NO COMPUTA"
        print(f"  {i+1}. {p['comp']}{fora_txt} · {p['rival']} [{computa_txt}]")
        print(f"     {p['url']}")

    # Tornar a la URL del partit actual
    driver.get(PARTIT_URL)
    time.sleep(3)

    # Retornar el primer partit oficial per al compte enrere web
    for p in propers:
        if p['computa']:
            return p
    return None

def recuperar_partits_passats(driver, baseline, baseline_viu):
    """Detecta partits oficials finalitzats no processats i genera les notificacions."""
    import re as _re
    from datetime import datetime as _dt

    # Carregar URLs ja processades del data.json
    # Usem url_partit quan existeix, i els títols 📋 com a fallback
    urls_processades = set()
    rivals_processats = set()  # per als títols sense url_partit
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for n in data.get('notificacions', []):
                if n.get('url_partit'):
                    urls_processades.add(n['url_partit'])
                t = _re.sub(r'<[^>]+>', '', n.get('text', '')).strip()
                if t.startswith('📋'):
                    # Extreure rival del títol per comparar amb URLs
                    # Format: 📋 DD/MM/YYYY · COMP · BARÇA - RIVAL o RIVAL - BARÇA
                    parts = t.split('·')
                    if len(parts) >= 3:
                        rival_part = parts[-1].strip()
                        rival_part = rival_part.replace('BARÇA - ', '').replace(' - BARÇA', '').strip().lower()
                        rivals_processats.add(rival_part)
        except Exception:
            pass

    print(f"URLs processades: {len(urls_processades)} | Rivals processats: {len(rivals_processats)}")

    # Scraping de la pàgina de resultats (partits jugats)
    RESULTATS_URL = "https://www.fcbarcelona.cat/ca/futbol/primer-equip/resultats"
    driver.get(RESULTATS_URL)
    time.sleep(6)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    totes_urls = []
    vistos = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        if not _re.search(r'/ca/partits/\d+/', href):
            continue
        url = href if href.startswith('http') else 'https://www.fcbarcelona.cat' + href
        if url in vistos:
            continue
        vistos.add(url)
        totes_urls.append(url)

    print(f"Partits a la pàgina de resultats: {len(totes_urls)}")

    # Filtrar per competicions oficials i no processades
    nous = []
    for url in totes_urls:
        comp, computa = detectar_competicio_url(url)
        if not computa:
            continue
        if url in urls_processades:
            continue
        # Comprovar per rival (fallback per notificacions sense url_partit)
        _m_rival = _re.search(r'/\d+/(?:fc-barcelona-)?(.+?)-(?:fc-barcelona-)?(?:la-liga|copa|champions|lliga)', url)
        if _m_rival:
            rival_url = _m_rival.group(1).replace('-', ' ').lower()
            if any(rival_url in r or r in rival_url for r in rivals_processats):
                continue
        nous.append({'url': url, 'comp': comp})

    print(f"Partits oficials passats nous: {len(nous)}")

    for p in nous:
        url = p['url']
        comp = p['comp']
        print(f"\nProcessant: {comp} · {url.split('/')[-1][:50]}")
        try:
            estat = scrape_partit(driver, url)
        except Exception as e:
            print(f"  Error scraping: {e}")
            continue

        # Verificar que és realment finalitzat
        if estat['fixture_status'] not in ('F', 'C'):
            print(f"  Estat: {estat['fixture_status']} — salt.")
            continue

        if not estat['xi_barca']:
            print("  Sense XI — salt.")
            continue

        print(f"  XI: {estat['xi_barca']}")
        print(f"  Gols: {[g['jugador'] for g in estat['gols_barca']]}")
        print(f"  Canvis: {[c['entra'] for c in estat['canvis']]}")

        # Extreure rival
        _m = _re.search(r'fc-barcelona-(.+?)-(?:la-liga|copa|champions|lliga)', url)
        if _m:
            rival = _m.group(1).replace('-', ' ').title()
            barca_fora_p = False
        else:
            _m2 = _re.search(r'/\d+/(.+?)-fc-barcelona', url)
            rival = _m2.group(1).replace('-', ' ').title() if _m2 else url
            barca_fora_p = True

        comp_label_p = text_comp(comp)
        cola_local = []

        # Titulars — stats PREVIS al partit (baseline_viu ABANS d'actualitzar)
        stats_previs = {}
        for nom_web in estat['xi_barca']:
            alias = normalitzar_nom(nom_web)
            stats_previs[nom_web] = {
                'pj_tot': obtenir_stats(baseline_viu, alias, "Total")['pj'],
                'pj_com': obtenir_stats(baseline_viu, alias, comp)['pj'],
            }
        # Actualitzar baseline_viu per a tots els titulars
        for nom_web in estat['xi_barca']:
            alias = normalitzar_nom(nom_web)
            _actualitzar_baseline(baseline_viu, alias, comp, 'pj')
        # Generar notificacions amb baseline PRE i POST
        for nom_web in estat['xi_barca']:
            for n in generar_notificacions_partits(baseline_viu, baseline_viu, nom_web, comp,
                                                   stats_previs[nom_web]['pj_tot'],
                                                   stats_previs[nom_web]['pj_com']):
                cola_local.append(('programada', n))

        # Gols
        for gol in estat['gols_barca']:
            alias = normalitzar_nom(gol['jugador'])
            g_tot = obtenir_stats(baseline_viu, alias, "Total").get('g', 0)
            g_com = obtenir_stats(baseline_viu, alias, comp).get('g', 0)
            for n in generar_notificacio_gol(baseline, baseline_viu, gol['jugador'], comp, g_tot, g_com):
                cola_local.append(('prioritaria', n))
            _actualitzar_baseline(baseline_viu, alias, comp, 'g')

        # Canvis
        for canvi in estat['canvis']:
            alias = normalitzar_nom(canvi['entra'])
            pj_tot = obtenir_stats(baseline_viu, alias, "Total")['pj']
            pj_com = obtenir_stats(baseline_viu, alias, comp)['pj']
            _actualitzar_baseline(baseline_viu, alias, comp, 'pj')
            for n in generar_notificacions_partits(baseline_viu, baseline_viu, canvi['entra'], comp, pj_tot, pj_com):
                cola_local.append(('programada', n))

        # Títol
        data_str = _dt.now().strftime('%d/%m/%Y')
        if estat.get('data_partit'):
            data_str = estat['data_partit']
        titol = f"📋 {data_str} · {comp_label_p.upper()} · {'BARÇA - ' if not barca_fora_p else ''}{rival.upper()}{' - BARÇA' if barca_fora_p else ''}"
        cola_local.append(('prioritaria', titol))

        # Guardar al data.json
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {'notificacions': []}

        ts = _dt.now().isoformat()
        for tipus, notif in cola_local:
            if isinstance(notif, str):
                entry = {'text': notif, 'tipus': tipus, 'ts': ts, 'url_partit': url}
            else:
                notif['url_partit'] = url
                entry = notif
            data['notificacions'].append(entry)

        data['baseline'] = baseline_viu
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"  {len(cola_local)} notificacions generades.")

    driver.get(PARTIT_URL)
    time.sleep(3)
    print("Recuperació completada.")


def descarregar_fotos_jugadors(driver):
    """Descarrega les fotos dels jugadors actuals de fcbarcelona.cat."""
    import urllib.request
    os.makedirs(FOTOS_DIR, exist_ok=True)
    JUGADORS_URL = "https://www.fcbarcelona.cat/ca/futbol/primer-equip/jugadors"
    print("Descarregant fotos de jugadors...")
    try:
        driver.set_page_load_timeout(20)
        driver.get(JUGADORS_URL)
    except Exception:
        pass
    finally:
        driver.set_page_load_timeout(30)
    time.sleep(6)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    descarregades = 0
    for card in soup.find_all(['article','div','li'], class_=re.compile(r'player|jugador', re.I)):
        nom_el = card.find(['h2','h3','h4','span'], class_=re.compile(r'name|nom', re.I))
        img_el = card.find('img', src=True)
        if not nom_el or not img_el:
            continue
        nom_web = nom_el.get_text(strip=True)
        nom_complet = normalitzar_nom(nom_web)
        if not nom_complet:
            continue
        src = img_el['src']
        if not src.startswith('http'):
            src = 'https://www.fcbarcelona.cat' + src
        path = os.path.join(FOTOS_DIR, f"{nom_complet}.jpg")
        try:
            urllib.request.urlretrieve(src, path)
            descarregades += 1
        except Exception as e:
            print(f"  Error foto {nom_complet}: {e}")

    print(f"  {descarregades} fotos descarregades/actualitzades.")
    driver.get(PARTIT_URL)
    time.sleep(3)

def main():
    print("Carregant baseline...")
    baseline = carregar_baseline()
    construir_index_actius()
    print(f"Baseline OK: {sum(len(v) for v in baseline.values())} registres")

    # Carregar baseline_viu des del data.json si ja existeix (conserva dades del partit anterior)
    baseline_viu = deepcopy(baseline)
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data_existent = json.load(f)
            if 'baseline' in data_existent:
                baseline_viu = data_existent['baseline']
                print("baseline_viu carregat des de data.json (dades acumulades)")
            else:
                guardar_baseline_a_data(baseline_viu)
                print("Baseline escrit a data.json")
        except Exception:
            guardar_baseline_a_data(baseline_viu)
            print("Baseline escrit a data.json")
    else:
        guardar_baseline_a_data(baseline_viu)
        print("Baseline escrit a data.json")
    
    print("Iniciant Chrome...")
    driver = init_driver()

    # fotos gestionades manualment
    cola   = ColaNotificacions()

    xi_fet            = False
    final_fet         = False
    sincronitzat      = False  # Evitar sincronitzar més d'una vegada per sessió

    # Carregar sets processats des de data.json per evitar duplicats en reinici
    _estat_sessio = {}
    if os.path.exists(SESSIO_FILE):
        try:
            with open(SESSIO_FILE, 'r', encoding='utf-8') as f:
                _estat_sessio = json.load(f)
            print("Sessió anterior trobada - recuperant estat...")
        except Exception:
            _estat_sessio = {}

    canvis_processats = set(_estat_sessio.get('canvis', []))
    gols_processats   = set(_estat_sessio.get('gols', []))
    if _estat_sessio.get('xi_fet'):
        xi_fet = True
        print("Reinici detectat: XI ja processat, canvis i gols recuperats.")

    print(f"Competicio: {COMPETICIO}")
    print(f"URL: {PARTIT_URL}")
    print("---")

    # Mostrar els propers partits i guardar el primer oficial
    proper_oficial = None
    proper_oficial_kickoff_ts = None
    try:
        proper_oficial = mostrar_propers_partits(driver)
        if proper_oficial:
            print(f"Proper oficial: {proper_oficial['comp']} · {proper_oficial['rival']}")
            # Scrapejar kickoff_ts del proper oficial una sola vegada
            try:
                _estat_oficial = scrape_partit(driver, proper_oficial['url'])
                proper_oficial_kickoff_ts = _estat_oficial.get('kickoff_ts')
                driver.get(PARTIT_URL)
                time.sleep(3)
                print(f"Kickoff proper oficial: {proper_oficial_kickoff_ts}")
            except Exception as e:
                print(f"No s'ha pogut obtenir kickoff del proper oficial: {e}")
    except Exception as e:
        print(f"No s'han pogut carregar els propers partits: {e}")
    print("---")

    # recuperar_partits_passats desactivat - gestió manual de partits passats

    # Extreure rival i competició per a notificacions i estat web
    import re as _re2
    _m_url = _re2.search(r'fc-barcelona-(.+?)-(?:la-liga|copa|la-copa|champions|supercopa|lliga-de-campions)', PARTIT_URL)
    if _m_url:
        rival_nom = _m_url.group(1).replace('-', ' ').title()
        barca_fora = False
    else:
        # Barça juga a fora: rival-fc-barcelona-...
        _m_url2 = _re2.search(r'/(\d+)/(.+?)-fc-barcelona', PARTIT_URL)
        rival_nom = _m_url2.group(2).replace('-', ' ').title() if _m_url2 else '?'
        barca_fora = True
    comp_label_web = text_comp(COMPETICIO)

    try:
        while True:
            # Reconexió automàtica si Chrome ha petat o ha estat tancat
            try:
                driver.title
            except Exception:
                print("Chrome no disponible. Reiniciant...")
                try:
                    driver.quit()
                except Exception:
                    pass
                time.sleep(3)
                driver = init_driver()
                print("Chrome reiniciat OK.")

            try:
                estat = scrape_partit(driver, PARTIT_URL)
            except Exception as e:
                print(f"Error scraping: {e} — reintentant en 30s")
                time.sleep(30)
                continue

            # --- Sincronitzacio bdfutbol 3h abans del partit ---
            if not sincronitzat and estat.get('kickoff_ts'):
                secs_restants = estat['kickoff_ts'] - time.time()
                if secs_restants <= 3 * 3600:
                    ok = sincronitzar_baseline_bdfutbol(driver)
                    if ok:
                        baseline = carregar_baseline()
                        construir_index_actius()
                        # baseline_viu parteix del baseline fresc, NO del data.json antic
                        baseline_viu = deepcopy(baseline)
                        guardar_baseline_a_data(baseline_viu)
                        corregir_notificacions_data(baseline)
                        sincronitzat = True
                    else:
                        print("Sincronitzacio fallida, es tornara a intentar al proper cicle.")

            # --- XI inicial: notificacions de partits per als titulars ---
            COMPUTA = COMPETICIO not in ('Amistós', 'Amistós (Gamper)', 'Supercopa')
            if estat['xi_barca'] and not xi_fet:
                xi_fet = True
                _guardar_sessio(xi_fet, gols_processats, canvis_processats)
                print(f"XI detectat: {estat['xi_barca']}")
                if not COMPUTA:
                    print(f"Competicio '{COMPETICIO}' no computa — sense notificacions.")

                # Reiniciar el conjunt de jugadors del partit
                reset_jugadors_partit()

                # Passada 1: recollim stats ABANS d'actualitzar cap jugador
                stats_previs = {}
                for nom_web in estat['xi_barca']:
                    alias = normalitzar_nom(nom_web)
                    stats_previs[nom_web] = {
                        'pj_tot': obtenir_stats(baseline, alias, "Total")['pj'],
                        'pj_com': obtenir_stats(baseline, alias, COMPETICIO)['pj'],
                    }

                # Passada 2: actualitzem el baseline_viu de TOTS els titulars (sempre)
                # i els marquem com a "ja processats" per excloure'ls de notificacions entre si
                for nom_web in estat['xi_barca']:
                    alias = normalitzar_nom(nom_web)
                    nom_complet = _ALIAS_ACTIUS.get(alias.lower(), alias)
                    _actualitzar_baseline(baseline_viu, alias, COMPETICIO, 'pj')
                    afegir_jugador_partit(nom_complet, titular=True)

                # Passada 3: generem les notificacions NOMÉS si computa
                if COMPUTA:
                    for nom_web in estat['xi_barca']:
                        for n in generar_notificacions_partits(baseline, baseline_viu, nom_web, COMPETICIO,
                                                               stats_previs[nom_web]['pj_tot'],
                                                               stats_previs[nom_web]['pj_com']):
                            cola.afegir_programada(n)

                guardar_baseline_a_data(baseline_viu)

            # --- Gols del Barça (PRIORITARIS: s'afegeixen al principi de la cua) ---
            # Detecció de gols rectificats: si la clau d'un gol processat ja no coincideix
            # amb la llista actual de gols, es considera rectificat
            for clau_proc in list(gols_processats):
                if not clau_proc.startswith('gol_'):
                    continue
                parts = clau_proc.split('_', 2)
                if len(parts) < 3:
                    continue
                idx_proc = int(parts[1])
                autor_proc = parts[2]
                # Comprovar si el gol en aquesta posició té ara un autor diferent
                if idx_proc < len(estat['gols_barca']):
                    autor_actual = estat['gols_barca'][idx_proc]['jugador']
                    if normalitzar_nom(autor_actual) != normalitzar_nom(autor_proc):
                        print(f"GOL RECTIFICAT: gol {idx_proc} era de {autor_proc}, ara de {autor_actual}")
                        # Esborrar notificacions de gol de l'autor original del data.json
                        if COMPUTA:
                            alias_orig = normalitzar_nom(autor_proc)
                            _esborrar_notificacions_gol(alias_orig, COMPETICIO)
                            # Restar gol al baseline_viu
                            _restar_baseline(baseline_viu, alias_orig, COMPETICIO, 'g')
                            guardar_baseline_a_data(baseline_viu)
                        # Treure la clau antiga i afegir la nova per processar
                        gols_processats.discard(clau_proc)
                        _guardar_sessio(xi_fet, gols_processats, canvis_processats)

            for i, gol in enumerate(estat['gols_barca']):
                clau = f"gol_{i}_{gol['jugador']}"
                if clau in gols_processats:
                    continue
                gols_processats.add(clau)
                _guardar_sessio(xi_fet, gols_processats, canvis_processats)
                print(f"Gol: {gol['jugador']}")
                if COMPUTA:
                    alias = normalitzar_nom(gol['jugador'])
                    g_tot = obtenir_stats(baseline_viu, alias, "Total").get('g', 0)
                    g_com = obtenir_stats(baseline_viu, alias, COMPETICIO).get('g', 0)
                    for n in generar_notificacio_gol(baseline, baseline_viu, gol['jugador'], COMPETICIO, g_tot, g_com):
                        cola.afegir_prioritaria(n)
                    _actualitzar_baseline(baseline_viu, alias, COMPETICIO, 'g')
                    guardar_baseline_a_data(baseline_viu)

            # --- Canvis: notificacions de partits per als que entren ---
            for canvi in estat['canvis']:
                clau = f"{canvi['entra']}|{canvi['surt']}"
                if clau in canvis_processats:
                    continue
                canvis_processats.add(clau)
                _guardar_sessio(xi_fet, gols_processats, canvis_processats)
                print(f"Canvi: entra {canvi['entra']}")
                alias = normalitzar_nom(canvi['entra'])
                nom_complet = _ALIAS_ACTIUS.get(alias.lower(), alias)
                # Recollim stats ABANS d'actualitzar
                pj_tot = obtenir_stats(baseline_viu, alias, "Total")['pj']
                pj_com = obtenir_stats(baseline_viu, alias, COMPETICIO)['pj']
                # Actualitzem el baseline_viu sempre
                _actualitzar_baseline(baseline_viu, alias, COMPETICIO, 'pj')
                # Generem notificacions NOMÉS si computa
                # El suplent SÍ pot superar/emparar titulars que ja han jugat
                if COMPUTA:
                    for n in generar_notificacions_partits(baseline, baseline_viu, canvi['entra'], COMPETICIO, pj_tot, pj_com):
                        cola.afegir_programada(n)
                    guardar_baseline_a_data(baseline_viu)
                # Afegir DESPRÉS de generar notificació (per si altres canvis posteriors l'han de superar)
                afegir_jugador_partit(nom_complet)

            # --- Guardar estat a data.json per a la web ---
            proper = None
            if not COMPUTA and proper_oficial and proper_oficial_kickoff_ts:
                # Amistós: compte enrere apunta al proper partit oficial
                secs = proper_oficial_kickoff_ts - time.time()
                if secs > 0:
                    dies = int(secs // 86400)
                    hores = int((secs % 86400) // 3600)
                    mins = int((secs % 3600) // 60)
                    segs = int(secs % 60)
                    compte = f"{dies}d {hores}h {mins}m {segs}s"
                else:
                    compte = "0d 0h 0m 0s"
                comp_oficial = text_comp(proper_oficial['comp'])
                rival_oficial = proper_oficial['rival']
                fora_oficial = proper_oficial['fora']
                descrip = f"{comp_oficial} · {'Barça - ' if not fora_oficial else ''}{rival_oficial}{' - Barça' if fora_oficial else ''}"
                proper = {
                    'descripcio': descrip,
                    'compte_enrere': compte,
                    'kickoff_ts': proper_oficial_kickoff_ts,
                }
            elif estat['fixture_status'] == 'U' and estat.get('kickoff_ts'):
                proper = {
                    'descripcio': f"{comp_label_web} · {'Barça - ' if not barca_fora else ''}{rival_nom}{' - Barça' if barca_fora else ''}",
                    'compte_enrere': estat['compte_enrere'],
                    'kickoff_ts': estat['kickoff_ts']
                }
            guardar_estat_partit(
                estat['fixture_status'],
                comp=comp_label_web,
                rival=rival_nom,
                proper_partit=proper
            )

            # --- Final ---
            print(f"Estat: {estat['fixture_status']}", end='\r')
            if estat['finalitzat'] and not final_fet:
                final_fet = True
                print("Partit finalitzat.")
                time.sleep(10)
                # Notificació títol de tancament només si computa
                if COMPUTA:
                    from datetime import date
                    data_avui = date.today().strftime('%d/%m/%Y')
                    comp_label = text_comp(COMPETICIO).upper()
                    titol = f"📋 {data_avui} · {comp_label} · {'BARÇA - ' if not barca_fora else ''}{rival_nom.upper()}{' - BARÇA' if barca_fora else ''}"
                    cola.afegir_prioritaria(titol)

                # Esborrar sessió actual (partit acabat)
                # Esborrar fitxer de sessió (partit acabat)
                if os.path.exists(SESSIO_FILE):
                    os.remove(SESSIO_FILE)
                    print("Sessió esborrada.")

                # Guardar baseline_viu al baseline.json per a propers partits
                try:
                    with open(BASELINE_FILE, 'r', encoding='utf-8') as f:
                        bl_data = json.load(f)
                    for comp_k, jugadors in bl_data.items():
                        for j in jugadors:
                            nom = j['nom'].strip()
                            if nom in baseline_viu.get(comp_k, {}):
                                j['pj'] = baseline_viu[comp_k][nom].get('pj', j.get('pj', 0))
                                j['g']  = baseline_viu[comp_k][nom].get('g',  j.get('g',  0))
                    with open(BASELINE_FILE, 'w', encoding='utf-8') as f:
                        json.dump(bl_data, f, ensure_ascii=False, indent=2)
                    print("baseline.json actualitzat amb les dades del partit.")
                except Exception as e:
                    print(f"Error guardant baseline: {e}")

                # Esperar que la cua es buide i cercar el proper partit
                print("Esperant que la cua de notificacions es buide...")
                while cola.prioritaria or cola.programada:
                    time.sleep(5)
                print("Cua buida. Cercant proper partit...")
                try:
                    import subprocess, sys
                    script = os.path.join(os.path.dirname(__file__), 'cerca_proper_partit.py')
                    subprocess.run([sys.executable, script], check=True)
                    print("Proper partit actualitzat a config.json")
                    # Llegir nou config per actualitzar rival i estat web
                    import re as _re3
                    with open(os.path.join(CARPETA, 'config.json'), encoding='utf-8') as _f:
                        _cfg = json.load(_f)
                    _nou_url = _cfg.get('url', '')
                    _m2 = _re3.search(r'fc-barcelona-(.+?)-(?:la-liga|copa|la-copa|champions|supercopa|lliga-de-campions)', _nou_url)
                    if _m2:
                        _nou_rival = _m2.group(1).replace('-', ' ').title()
                    else:
                        _m2b = _re3.search(r'/(\d+)/(.+?)-fc-barcelona', _nou_url)
                        _nou_rival = _m2b.group(2).replace('-', ' ').title() if _m2b else ''
                    _nou_comp = text_comp(_cfg.get('competicio', ''))
                    # Scrapejar kickoff_ts del proper partit
                    _nou_estat = scrape_partit(driver, _nou_url)
                    _proper_partit = {
                        'descripcio': f"{_nou_comp} · Barça - {_nou_rival}",
                        'compte_enrere': _nou_estat.get('compte_enrere'),
                        'kickoff_ts': _nou_estat.get('kickoff_ts'),
                    }
                    guardar_estat_partit('U', comp=_nou_comp, rival=_nou_rival, proper_partit=_proper_partit)
                    print(f"Proper partit guardat: {_nou_rival} | kickoff_ts={_nou_estat.get('kickoff_ts')}")
                except Exception as e:
                    print(f"Error cercant proper partit: {e}")
                    guardar_estat_partit('U', comp='', rival='')
                break

            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        print("\nAturat per l'usuari.")
    finally:
        driver.quit()
        cola.stop()
        print("Monitor aturat.")

if __name__ == "__main__":
    main()
