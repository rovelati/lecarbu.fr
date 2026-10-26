#!/usr/bin/env python3
"""
build-fr-database.py — LeCarbu.fr
Ingests official French Government Fuel Data (data.economie.gouv.fr / roulez-eco.fr),
enriches with French communes and departments, and generates high-performance
static JSON datasets for ~19,000 programmatic SEO pages.
"""

import urllib.request
import json
import os
import re
import unicodedata
import zipfile
import io
import xml.etree.ElementTree as ET

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
SRC_DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'src', 'data')
PUBLIC_DIR = os.path.join(os.path.dirname(__file__), '..', 'public')

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SRC_DATA_DIR, exist_ok=True)
os.makedirs(PUBLIC_DIR, exist_ok=True)

GOV_JSON_URL = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/prix-des-carburants-en-france-flux-instantane-v2/exports/json"
ROULEZ_ECO_ZIP_URL = "https://donnees.roulez-eco.fr/opendata/instantane"
CITIES_JSON_URL = "https://raw.githubusercontent.com/lutangar/cities.json/master/cities.json"

def slugify(text):
    if not text:
        return ""
    text = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '-', text)

import gzip

def download_fuel_data():
    cache_file = os.path.join(DATA_DIR, 'prix_carburants_fr.json')
    # Try fetching JSON from data.economie.gouv.fr
    print("[1/5] Downloading French Government Open Fuel Data...")
    try:
        req = urllib.request.Request(GOV_JSON_URL, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept-Encoding": "gzip, deflate"
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            if content[:2] == b'\x1f\x8b':
                content = gzip.decompress(content)
            data = json.loads(content.decode('utf-8'))
            print(f"Downloaded {len(data)} stations from data.economie.gouv.fr")
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f)
            return data
    except Exception as e:
        print(f"Failed to fetch JSON ({e}), trying fallback ZIP from roulez-eco.fr...")
        
    try:
        req = urllib.request.Request(ROULEZ_ECO_ZIP_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=40) as resp:
            zf = zipfile.ZipFile(io.BytesIO(resp.read()))
            xml_data = zf.read(zf.namelist()[0])
            root = ET.fromstring(xml_data)
            data = []
            for s in root:
                sid = s.attrib.get('id', '')
                lat = float(s.attrib.get('latitude', 0)) / 100000.0 if s.attrib.get('latitude') else 0.0
                lng = float(s.attrib.get('longitude', 0)) / 100000.0 if s.attrib.get('longitude') else 0.0
                cp = s.attrib.get('cp', '')
                addr = s.find('adresse').text if s.find('adresse') is not None else ''
                ville = s.find('ville').text if s.find('ville') is not None else ''
                
                prices = {}
                for p in s.findall('prix'):
                    nom = p.attrib.get('nom', '').lower()
                    val = float(p.attrib.get('valeur', 0)) if p.attrib.get('valeur') else None
                    if 'gazole' in nom:
                        prices['gazole_prix'] = val
                    elif 'e10' in nom:
                        prices['e10_prix'] = val
                    elif 'sp98' in nom:
                        prices['sp98_prix'] = val
                    elif 'e85' in nom:
                        prices['e85_prix'] = val
                    elif 'sp95' in nom:
                        prices['sp95_prix'] = val
                    elif 'gpl' in nom:
                        prices['gplc_prix'] = val
                
                data.append({
                    "id": sid,
                    "cp": cp,
                    "adresse": addr,
                    "ville": ville,
                    "geom": {"lat": lat, "lon": lng},
                    "horaires_automate_24_24": "Oui" if s.find('horaires') is not None and s.find('horaires').attrib.get('automate-24-24') == '1' else "Non",
                    "code_departement": cp[:2] if len(cp) >= 2 else "",
                    **prices
                })
            print(f"Parsed {len(data)} stations from roulez-eco.fr XML")
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f)
            return data
    except Exception as e2:
        print(f"Fallback also failed: {e2}")
        if os.path.exists(cache_file):
            print("Loading from local cache...")
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        raise e2

def detect_brand(addr, ville):
    text = f"{addr or ''} {ville or ''}".upper()
    if any(k in text for k in ['LECLERC', 'E.LECLERC']):
        return 'E.Leclerc', 'leclerc'
    if any(k in text for k in ['TOTAL', 'TOTALENERGIES', 'ACCESS']):
        return 'TotalEnergies', 'totalenergies'
    if any(k in text for k in ['CARREFOUR', 'MARKET']):
        return 'Carrefour', 'carrefour'
    if any(k in text for k in ['INTERMARCHE', 'INTERMARCHÉ']):
        return 'Intermarché', 'intermarche'
    if any(k in text for k in ['SYSTEME U', 'SUPER U', 'HYPER U', 'U EXPRESS']):
        return 'Système U', 'systeme-u'
    if 'AUCHAN' in text:
        return 'Auchan', 'auchan'
    if any(k in text for k in ['ESSO', 'ESSO EXPRESS']):
        return 'Esso', 'esso'
    if 'BP' in text:
        return 'BP', 'bp'
    if 'AVIA' in text:
        return 'Avia', 'avia'
    if 'SHELL' in text:
        return 'Shell', 'shell'
    if 'CASINO' in text:
        return 'Casino', 'casino'
    return 'Station Indépendante', 'independant'

def download_french_cities():
    cities_file = os.path.join(DATA_DIR, 'french_cities_ref.json')
    if os.path.exists(cities_file):
        with open(cities_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    print("[2/5] Downloading French settlements reference database...")
    req = urllib.request.Request(CITIES_JSON_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        all_cities = json.load(resp)
        fr_cities = [c for c in all_cities if c.get('country') == 'FR']
        with open(cities_file, 'w', encoding='utf-8') as f:
            json.dump(fr_cities, f)
        return fr_cities

def main():
    raw_stations = download_fuel_data()
    fr_cities_ref = download_french_cities()

    # Known French Departments Mapping
    dept_map = {
        "01": ("Ain", "Auvergne-Rhône-Alpes"),
        "02": ("Aisne", "Hauts-de-France"),
        "03": ("Allier", "Auvergne-Rhône-Alpes"),
        "04": ("Alpes-de-Haute-Provence", "Provence-Alpes-Côte d'Azur"),
        "05": ("Hautes-Alpes", "Provence-Alpes-Côte d'Azur"),
        "06": ("Alpes-Maritimes", "Provence-Alpes-Côte d'Azur"),
        "07": ("Ardèche", "Auvergne-Rhône-Alpes"),
        "08": ("Ardennes", "Grand Est"),
        "09": ("Ariège", "Occitanie"),
        "10": ("Aube", "Grand Est"),
        "11": ("Aude", "Occitanie"),
        "12": ("Aveyron", "Occitanie"),
        "13": ("Bouches-du-Rhône", "Provence-Alpes-Côte d'Azur"),
        "14": ("Calvados", "Normandie"),
        "15": ("Cantal", "Auvergne-Rhône-Alpes"),
        "16": ("Charente", "Nouvelle-Aquitaine"),
        "17": ("Charente-Maritime", "Nouvelle-Aquitaine"),
        "18": ("Cher", "Centre-Val de Loire"),
        "19": ("Corrèze", "Nouvelle-Aquitaine"),
        "2A": ("Corse-du-Sud", "Corse"),
        "2B": ("Haute-Corse", "Corse"),
        "21": ("Côte-d'Or", "Bourgogne-Franche-Comté"),
        "22": ("Côtes-d'Armor", "Bretagne"),
        "23": ("Creuse", "Nouvelle-Aquitaine"),
        "24": ("Dordogne", "Nouvelle-Aquitaine"),
        "25": ("Doubs", "Bourgogne-Franche-Comté"),
        "26": ("Drôme", "Auvergne-Rhône-Alpes"),
        "27": ("Eure", "Normandie"),
        "28": ("Eure-et-Loir", "Centre-Val de Loire"),
        "29": ("Finistère", "Bretagne"),
        "30": ("Gard", "Occitanie"),
        "31": ("Haute-Garonne", "Occitanie"),
        "32": ("Gers", "Occitanie"),
        "33": ("Gironde", "Nouvelle-Aquitaine"),
        "34": ("Hérault", "Occitanie"),
        "35": ("Ille-et-Vilaine", "Bretagne"),
        "36": ("Indre", "Centre-Val de Loire"),
        "37": ("Indre-et-Loire", "Centre-Val de Loire"),
        "38": ("Isère", "Auvergne-Rhône-Alpes"),
        "39": ("Jura", "Bourgogne-Franche-Comté"),
        "40": ("Landes", "Nouvelle-Aquitaine"),
        "41": ("Loir-et-Cher", "Centre-Val de Loire"),
        "42": ("Loire", "Auvergne-Rhône-Alpes"),
        "43": ("Haute-Loire", "Auvergne-Rhône-Alpes"),
        "44": ("Loire-Atlantique", "Pays de la Loire"),
        "45": ("Loiret", "Centre-Val de Loire"),
        "46": ("Lot", "Occitanie"),
        "47": ("Lot-et-Garonne", "Nouvelle-Aquitaine"),
        "48": ("Lozère", "Occitanie"),
        "49": ("Maine-et-Loire", "Pays de la Loire"),
        "50": ("Manche", "Normandie"),
        "51": ("Marne", "Grand Est"),
        "52": ("Haute-Marne", "Grand Est"),
        "53": ("Mayenne", "Pays de la Loire"),
        "54": ("Meurthe-et-Moselle", "Grand Est"),
        "55": ("Meuse", "Grand Est"),
        "56": ("Morbihan", "Bretagne"),
        "57": ("Moselle", "Grand Est"),
        "58": ("Nièvre", "Bourgogne-Franche-Comté"),
        "59": ("Nord", "Hauts-de-France"),
        "60": ("Oise", "Hauts-de-France"),
        "61": ("Orne", "Normandie"),
        "62": ("Pas-de-Calais", "Hauts-de-France"),
        "63": ("Puy-de-Dôme", "Auvergne-Rhône-Alpes"),
        "64": ("Pyrénées-Atlantiques", "Nouvelle-Aquitaine"),
        "65": ("Hautes-Pyrénées", "Occitanie"),
        "66": ("Pyrénées-Orientales", "Occitanie"),
        "67": ("Bas-Rhin", "Grand Est"),
        "68": ("Haut-Rhin", "Grand Est"),
        "69": ("Rhône", "Auvergne-Rhône-Alpes"),
        "70": ("Haute-Saône", "Bourgogne-Franche-Comté"),
        "71": ("Saône-et-Loire", "Bourgogne-Franche-Comté"),
        "72": ("Sarthe", "Pays de la Loire"),
        "73": ("Savoie", "Auvergne-Rhône-Alpes"),
        "74": ("Haute-Savoie", "Auvergne-Rhône-Alpes"),
        "75": ("Paris", "Île-de-France"),
        "76": ("Seine-Maritime", "Normandie"),
        "77": ("Seine-et-Marne", "Île-de-France"),
        "78": ("Yvelines", "Île-de-France"),
        "79": ("Deux-Sèvres", "Nouvelle-Aquitaine"),
        "80": ("Somme", "Hauts-de-France"),
        "81": ("Tarn", "Occitanie"),
        "82": ("Tarn-et-Garonne", "Occitanie"),
        "83": ("Var", "Provence-Alpes-Côte d'Azur"),
        "84": ("Vaucluse", "Provence-Alpes-Côte d'Azur"),
        "85": ("Vendée", "Pays de la Loire"),
        "86": ("Vienne", "Nouvelle-Aquitaine"),
        "87": ("Haute-Vienne", "Nouvelle-Aquitaine"),
        "88": ("Vosges", "Grand Est"),
        "89": ("Yonne", "Bourgogne-Franche-Comté"),
        "90": ("Territoire de Belfort", "Bourgogne-Franche-Comté"),
        "91": ("Essonne", "Île-de-France"),
        "92": ("Hauts-de-Seine", "Île-de-France"),
        "93": ("Seine-Saint-Denis", "Île-de-France"),
        "94": ("Val-de-Marne", "Île-de-France"),
        "95": ("Val-d'Oise", "Île-de-France"),
    }

    # Process and clean all active stations
    clean_stations = []
    city_stations_map = {}

    for s in raw_stations:
        lat = s.get('geom', {}).get('lat') if s.get('geom') else None
        lng = s.get('geom', {}).get('lon') if s.get('geom') else None
        if not lat or not lng:
            continue
        
        ville = (s.get('ville') or '').strip().title()
        if not ville:
            continue
        city_slug = slugify(ville)

        dept_code = str(s.get('code_departement') or '').zfill(2)
        if not dept_code and s.get('cp'):
            dept_code = str(s.get('cp'))[:2]
        
        dept_name, region_name = dept_map.get(dept_code, (s.get('departement') or "France", s.get('region') or "France"))
        brand_name, brand_slug = detect_brand(s.get('adresse'), s.get('ville'))

        station_obj = {
            "id": str(s.get('id')),
            "name": f"{brand_name} {ville}",
            "brand": brand_name,
            "brandSlug": brand_slug,
            "address": (s.get('adresse') or '').strip(),
            "city": ville,
            "citySlug": city_slug,
            "cp": str(s.get('cp') or ''),
            "deptCode": dept_code,
            "deptName": dept_name,
            "regionName": region_name,
            "lat": round(float(lat), 5),
            "lng": round(float(lng), 5),
            "prices": {
                "gazole": float(s['gazole_prix']) if s.get('gazole_prix') else None,
                "e10": float(s['e10_prix']) if s.get('e10_prix') else None,
                "sp98": float(s['sp98_prix']) if s.get('sp98_prix') else None,
                "e85": float(s['e85_prix']) if s.get('e85_prix') else None,
                "sp95": float(s['sp95_prix']) if s.get('sp95_prix') else None,
                "gplc": float(s['gplc_prix']) if s.get('gplc_prix') else None,
            },
            "services": s.get('services_service') if isinstance(s.get('services_service'), list) else [],
            "automate24": s.get('horaires_automate_24_24') == "Oui"
        }

        clean_stations.append(station_obj)

        if city_slug not in city_stations_map:
            city_stations_map[city_slug] = {
                "slug": city_slug,
                "name": ville,
                "deptCode": dept_code,
                "deptName": dept_name,
                "regionName": region_name,
                "lat": station_obj['lat'],
                "lng": station_obj['lng'],
                "stationCount": 0,
                "minGazole": 999.0,
                "minE10": 999.0,
                "minSP98": 999.0,
                "minE85": 999.0,
            }
        
        c_entry = city_stations_map[city_slug]
        c_entry['stationCount'] += 1
        if station_obj['prices']['gazole']:
            c_entry['minGazole'] = min(c_entry['minGazole'], station_obj['prices']['gazole'])
        if station_obj['prices']['e10']:
            c_entry['minE10'] = min(c_entry['minE10'], station_obj['prices']['e10'])
        if station_obj['prices']['sp98']:
            c_entry['minSP98'] = min(c_entry['minSP98'], station_obj['prices']['sp98'])
        if station_obj['prices']['e85']:
            c_entry['minE85'] = min(c_entry['minE85'], station_obj['prices']['e85'])

    print(f"Parsed {len(clean_stations)} stations across {len(city_stations_map)} cities with forecourts.")

    # Sort cities by station count and popularity
    sorted_active_cities = sorted(city_stations_map.values(), key=lambda x: x['stationCount'], reverse=True)

    # Enrich from French settlements database to ensure top 3,000 cities
    final_cities = []
    seen_slugs = set()

    for c in sorted_active_cities:
        if c['minGazole'] == 999.0: c['minGazole'] = None
        if c['minE10'] == 999.0: c['minE10'] = None
        if c['minSP98'] == 999.0: c['minSP98'] = None
        if c['minE85'] == 999.0: c['minE85'] = None
        final_cities.append(c)
        seen_slugs.add(c['slug'])

    # Add remaining major communes if needed up to 3,000
    for fc in fr_cities_ref:
        c_name = fc.get('name', '').strip()
        c_slug = slugify(c_name)
        if c_slug not in seen_slugs and len(c_slug) > 2:
            d_code = str(fc.get('admin2') or '').zfill(2)
            d_name, r_name = dept_map.get(d_code, ("France", "France"))
            final_cities.append({
                "slug": c_slug,
                "name": c_name,
                "deptCode": d_code,
                "deptName": d_name,
                "regionName": r_name,
                "lat": round(float(fc.get('lat', 46.5)), 5),
                "lng": round(float(fc.get('lng', 2.5)), 5),
                "stationCount": 0,
                "minGazole": None,
                "minE10": None,
                "minSP98": None,
                "minE85": None
            })
            seen_slugs.add(c_slug)
        if len(final_cities) >= 3000:
            break

    final_cities = final_cities[:3000]
    print(f"Selected {len(final_cities)} French cities for programmatic SEO engine.")

    # Brands configuration
    fr_brands = [
        {"slug": "leclerc", "name": "E.Leclerc", "color": "#005ea8", "searchVolume": 165000, "category": "Supermarché"},
        {"slug": "totalenergies", "name": "TotalEnergies", "color": "#ed1c24", "searchVolume": 135000, "category": "Pétrolier"},
        {"slug": "carrefour", "name": "Carrefour", "color": "#004e9a", "searchVolume": 90000, "category": "Supermarché"},
        {"slug": "intermarche", "name": "Intermarché", "color": "#e2001a", "searchVolume": 74000, "category": "Supermarché"},
        {"slug": "systeme-u", "name": "Système U", "color": "#0088ce", "searchVolume": 49000, "category": "Supermarché"},
        {"slug": "auchan", "name": "Auchan", "color": "#d52b1e", "searchVolume": 40500, "category": "Supermarché"},
        {"slug": "esso", "name": "Esso", "color": "#e01a22", "searchVolume": 33000, "category": "Pétrolier"},
        {"slug": "bp", "name": "BP", "color": "#007a3d", "searchVolume": 27000, "category": "Pétrolier"}
    ]

    # Generate Brand x City combinations (8 brands x top 850 cities = 6,800 pages)
    brand_city_pairs = []
    top_cities_for_brand = final_cities[:850]
    for b in fr_brands:
        for c in top_cities_for_brand:
            brand_city_pairs.append({
                "brandSlug": b['slug'],
                "brandName": b['name'],
                "citySlug": c['slug'],
                "cityName": c['name'],
                "deptCode": c['deptCode'],
                "deptName": c['deptName'],
                "regionName": c['regionName'],
                "lat": c['lat'],
                "lng": c['lng']
            })

    # Generate Departments list
    departments_list = []
    for code, (name, reg) in sorted(dept_map.items()):
        d_stations = [s for s in clean_stations if s['deptCode'] == code]
        min_gazole = min([s['prices']['gazole'] for s in d_stations if s['prices']['gazole']], default=None)
        min_e10 = min([s['prices']['e10'] for s in d_stations if s['prices']['e10']], default=None)
        departments_list.append({
            "code": code,
            "name": name,
            "slug": slugify(f"{code}-{name}"),
            "region": reg,
            "stationCount": len(d_stations),
            "minGazole": min_gazole,
            "minE10": min_e10
        })

    # Regions list
    regions_set = set([r for _, r in dept_map.values()])
    regions_list = [{"name": r, "slug": slugify(r)} for r in sorted(regions_set)]

    print("[3/5] Saving datasets to src/data/...")
    with open(os.path.join(SRC_DATA_DIR, 'fr_cities.json'), 'w', encoding='utf-8') as f:
        json.dump(final_cities, f, ensure_ascii=False)

    with open(os.path.join(SRC_DATA_DIR, 'fr_brands.json'), 'w', encoding='utf-8') as f:
        json.dump(fr_brands, f, ensure_ascii=False, indent=2)

    with open(os.path.join(SRC_DATA_DIR, 'brand_cities.json'), 'w', encoding='utf-8') as f:
        json.dump(brand_city_pairs, f, ensure_ascii=False)

    with open(os.path.join(SRC_DATA_DIR, 'fr_departements.json'), 'w', encoding='utf-8') as f:
        json.dump(departments_list, f, ensure_ascii=False, indent=2)

    with open(os.path.join(SRC_DATA_DIR, 'fr_regions.json'), 'w', encoding='utf-8') as f:
        json.dump(regions_list, f, ensure_ascii=False, indent=2)

    print("[4/5] Saving client-side stations index to public/fr_stations_index.json...")
    compact_stations = []
    for s in clean_stations:
        compact_stations.append({
            "i": s['id'],
            "n": s['name'],
            "b": s['brandSlug'],
            "a": s['address'],
            "v": s['city'],
            "c": s['citySlug'],
            "cp": s['cp'],
            "d": s['deptCode'],
            "lt": s['lat'],
            "lg": s['lng'],
            "p": {
                "g": s['prices']['gazole'],
                "e": s['prices']['e10'],
                "s": s['prices']['sp98'],
                "e85": s['prices']['e85']
            },
            "aut": 1 if s['automate24'] else 0
        })

    with open(os.path.join(PUBLIC_DIR, 'fr_stations_index.json'), 'w', encoding='utf-8') as f:
        json.dump(compact_stations, f, separators=(',', ':'))

    total_static_pages = (
        len(final_cities) * 4 +  # overview, gazole, e10, sp98
        len(brand_city_pairs) +  # 6,800
        len(departments_list) +  # 96
        len(regions_list) +      # 13
        len(fr_brands) +         # 8
        15                       # pillars & legal
    )
    print("[5/5] LeCarbu.fr Data Engine build complete!")
    print(f"Total programmatic pages planned: {total_static_pages} (well under 20,000 Cloudflare Pages limit)")

if __name__ == '__main__':
    main()
