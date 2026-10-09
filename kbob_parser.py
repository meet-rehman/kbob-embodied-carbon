import pandas as pd
import numpy as np
import json
import os

# Column positions in the sheet "Baumaterialien Matériaux" (KBOB version 8.0), counted from 0.
# Checked against the header rows of the spreadsheet.
COL_UBP_TOTAL = 7        # UBP'21, total
COL_PE_TOTAL = 10        # primary energy, total, kWh oil-eq
COL_GWP_TOTAL = 25       # greenhouse gas emissions, total, kg CO2-eq
COL_GWP_PRODUCTION = 26  # greenhouse gas emissions, production, kg CO2-eq
COL_BIOGENIC_C = 28      # biogenic carbon in the product, kg C

def parse_kbob(filepath="data/kbob_v8.xlsx"):
    """Parse KBOB Excel and return clean list of material records."""
    
    print("Parsing KBOB v8.0 database...")
    
    df = pd.read_excel(
        filepath,
        sheet_name="Baumaterialien Matériaux",
        header=None
    )
    
    materials = []
    current_category = "Unknown"
    
    for idx, row in df.iterrows():
        # Skip header rows (first 9 rows)
        if idx < 9:
            continue
        
        id_num = str(row[0]).strip() if pd.notna(row[0]) else ""
        
        # Detect category header rows (e.g. "00", "01", "02"...)
        if id_num and len(id_num) <= 2 and id_num.replace(".", "").isdigit():
            current_category = str(row[2]).strip() if pd.notna(row[2]) else current_category
            continue
        
        # Skip rows without a proper ID number
        if not id_num or id_num == "nan" or "." not in id_num:
            continue
        
        # Keep generic entries (ID like 10.001) and manufacturer-specific
        # entries (ID like 10.001.02). Anything else is not a material row.
        parts = id_num.split(".")
        if len(parts) not in (2, 3):
            continue
        is_generic = len(parts) == 2
        
        name_de = str(row[2]).strip() if pd.notna(row[2]) else ""
        uuid = str(row[1]).strip() if pd.notna(row[1]) else ""
        unit = str(row[6]).strip() if pd.notna(row[6]) else ""
        
        # Core environmental values
        try:
            ubp_total = float(row[COL_UBP_TOTAL]) if pd.notna(row[COL_UBP_TOTAL]) else None
        except:
            ubp_total = None
            
        try:
            primary_energy = float(row[COL_PE_TOTAL]) if pd.notna(row[COL_PE_TOTAL]) else None
        except:
            primary_energy = None
            
        try:
            gwp_total = float(row[COL_GWP_TOTAL]) if pd.notna(row[COL_GWP_TOTAL]) else None
        except:
            gwp_total = None
            
        try:
            gwp_production = float(row[COL_GWP_PRODUCTION]) if pd.notna(row[COL_GWP_PRODUCTION]) else None
        except:
            gwp_production = None
            
        try:
            biogenic_carbon = float(row[COL_BIOGENIC_C]) if pd.notna(row[COL_BIOGENIC_C]) else None
        except:
            biogenic_carbon = None

        if not name_de or name_de == "nan":
            continue

        materials.append({
            "id": id_num,
            "uuid": uuid,
            "category": current_category,
            "is_generic": is_generic,
            "name_de": name_de,
            "unit": unit,
            "ubp_total": ubp_total,
            "primary_energy_kwh": primary_energy,
            "gwp_total_kg_co2eq": gwp_total,
            "gwp_production_kg_co2eq": gwp_production,
            "biogenic_carbon_kg_c": biogenic_carbon,
            # Text used for semantic search
            "search_text": f"{name_de} {current_category} {id_num} {unit}"
        })
    
    print(f"Parsed {len(materials)} materials successfully.")
    return materials


def build_embeddings(materials):
    """Create semantic embeddings for material name search."""
    
    print("Building embeddings (this takes ~1 minute)...")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")
    
    texts = [m["search_text"] for m in materials]
    embeddings = model.encode(texts, show_progress_bar=True)
    
    print(f"Embeddings built: {embeddings.shape}")
    return embeddings


def save_database(materials, embeddings, out_dir="data"):
    """Save parsed materials and embeddings to disk."""
    
    # Save materials as JSON
    json_path = os.path.join(out_dir, "kbob_materials.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(materials, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(materials)} materials to {json_path}")
    
    # Save embeddings as numpy array
    emb_path = os.path.join(out_dir, "kbob_embeddings.npy")
    np.save(emb_path, embeddings)
    print(f"Saved embeddings to {emb_path}")


if __name__ == "__main__":
    materials = parse_kbob()
    
    # Preview first 3 materials
    print("\n--- Sample materials ---")
    for m in materials[:3]:
        print(f"\n{m['id']} | {m['name_de']}")
        print(f"  Unit: {m['unit']}")
        print(f"  GWP:  {m['gwp_total_kg_co2eq']} kg CO₂eq")
        print(f"  UBP:  {m['ubp_total']}")
        print(f"  PE:   {m['primary_energy_kwh']} kWh oil-eq")
    
    embeddings = build_embeddings(materials)
    save_database(materials, embeddings)
    
    print("\nKBOB database ready.")