import numpy as np
import json
import os
from sentence_transformers import SentenceTransformer
from openai import OpenAI
from dotenv import load_dotenv

# The OpenAI API key is read from the environment (or from a local .env file).
load_dotenv()

client = OpenAI()

# ── Placeholder limits. These are NOT the SIA 2032 or Minergie-ECO limit values,
#    which apply to a whole building per m² and year. See README. ──────────────
MINERGIE_ECO_LIMIT_GWP = 10.0    # kg CO₂eq / m² EBF per year
MINERGIE_ECO_LIMIT_PE  = 50.0    # kWh oil-eq / m² EBF per year

def load_database():
    print("Loading KBOB database...")
    with open("data/kbob_materials.json", encoding="utf-8") as f:
        materials = json.load(f)
    embeddings = np.load("data/kbob_embeddings.npy")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    print(f"Loaded {len(materials)} materials.")
    return materials, embeddings, model


def find_material(query_text, materials, embeddings, model, top_k=3):
    """Semantic search — find closest KBOB materials to the query."""
    query_embedding = model.encode([query_text])
    
    # Cosine similarity
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    normed = embeddings / (norms + 1e-10)
    query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-10)
    scores = normed @ query_norm.T
    scores = scores.flatten()
    
    top_indices = np.argsort(scores)[::-1][:top_k]
    results = []
    for idx in top_indices:
        results.append({
            "material": materials[idx],
            "score": float(scores[idx])
        })
    return results


def calculate_impact(material, quantity):
    """Calculate environmental impact for a given quantity."""
    gwp = material.get("gwp_total_kg_co2eq")
    ubp = material.get("ubp_total")
    pe  = material.get("primary_energy_kwh")
    unit = material.get("unit", "")
    
    result = {
        "material_name": material["name_de"],
        "unit": unit,
        "quantity": quantity,
        "gwp_total_kg_co2eq": round(gwp * quantity, 3) if gwp else None,
        "ubp_total": round(ubp * quantity, 0) if ubp else None,
        "primary_energy_kwh": round(pe * quantity, 2) if pe else None,
    }
    return result


def check_minergie(gwp_per_m2, pe_per_m2):
    """Check against Minergie-ECO thresholds."""
    gwp_ok = gwp_per_m2 <= MINERGIE_ECO_LIMIT_GWP if gwp_per_m2 else None
    pe_ok  = pe_per_m2  <= MINERGIE_ECO_LIMIT_PE  if pe_per_m2  else None
    return {
        "gwp_per_m2": gwp_per_m2,
        "gwp_limit": MINERGIE_ECO_LIMIT_GWP,
        "gwp_compliant": gwp_ok,
        "pe_per_m2": pe_per_m2,
        "pe_limit": MINERGIE_ECO_LIMIT_PE,
        "pe_compliant": pe_ok
    }


def generate_report(query, matches, impact, minergie):
    """Use GPT-4o to write a professional Graue Energie report."""
    
    material_context = json.dumps(matches[0]["material"], indent=2, ensure_ascii=False)
    impact_context   = json.dumps(impact, indent=2, ensure_ascii=False)
    minergie_context = json.dumps(minergie, indent=2, ensure_ascii=False)
    
    prompt = f"""You are a Swiss building sustainability expert specialising in 
Graue Energie (embodied carbon) assessment per SIA 2032 standard.

A Swiss engineer submitted this query:
"{query}"

Best matching KBOB material found:
{material_context}

Calculated environmental impact:
{impact_context}

Minergie-ECO threshold check:
{minergie_context}

Write a concise professional report in English that:
1. Confirms which KBOB material was matched and why
2. States the GWP total (kg CO₂eq), UBP total, and Primary Energy
3. States whether the result is within Minergie-ECO limits
4. Gives a practical recommendation for the engineer
5. Cites the KBOB version (2009/1:2022, version 8.0) as the data source

Keep it under 200 words. Use professional engineering language."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return response.choices[0].message.content


def run_query(user_query, quantity, floor_area_m2=None):
    """Full pipeline: search → calculate → check → report."""
    
    print(f"\n{'='*60}")
    print(f"QUERY: {user_query}")
    print(f"Quantity: {quantity}")
    print(f"{'='*60}")
    
    # Step 1 — Find material
    materials, embeddings, model = load_database()
    matches = find_material(user_query, materials, embeddings, model)
    
    print(f"\nTop KBOB matches:")
    for i, m in enumerate(matches):
        print(f"  {i+1}. [{m['score']:.3f}] {m['material']['name_de']} ({m['material']['unit']})")
    
    best = matches[0]["material"]
    
    # Step 2 — Calculate impact
    impact = calculate_impact(best, quantity)
    print(f"\nCalculated Impact:")
    print(f"  GWP:  {impact['gwp_total_kg_co2eq']} kg CO₂eq")
    print(f"  UBP:  {impact['ubp_total']}")
    print(f"  PE:   {impact['primary_energy_kwh']} kWh oil-eq")
    
    # Step 3 — Minergie check (if floor area provided)
    minergie = None
    if floor_area_m2 and impact["gwp_total_kg_co2eq"]:
        gwp_per_m2 = round(impact["gwp_total_kg_co2eq"] / floor_area_m2, 3)
        pe_per_m2  = round(impact["primary_energy_kwh"] / floor_area_m2, 3) if impact["primary_energy_kwh"] else None
        minergie = check_minergie(gwp_per_m2, pe_per_m2)
        print(f"\nMinergie-ECO Check (per m² EBF):")
        print(f"  GWP: {gwp_per_m2} kg CO₂eq/m² — {'✓ COMPLIANT' if minergie['gwp_compliant'] else '✗ EXCEEDS LIMIT'}")
        print(f"  PE:  {pe_per_m2} kWh/m²        — {'✓ COMPLIANT' if minergie['pe_compliant'] else '✗ EXCEEDS LIMIT'}")
    
    # Step 4 — Generate report
    print(f"\nGenerating professional report...")
    report = generate_report(user_query, matches, impact, minergie)
    print(f"\n--- GRAUE ENERGIE REPORT ---\n{report}")
    
    return report


# ── Test queries ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    
    # Query 1 — Concrete slab
    run_query(
        user_query="Beton Stahlbeton Bodenplatte",
        quantity=15000,
        floor_area_m2=200
    )

    # Query 2 — Timber
    run_query(
        user_query="Brettsperrholz CLT Holzdecke",
        quantity=5000,
        floor_area_m2=200
    )

    # Query 3 — Insulation
    run_query(
        user_query="Wärmedämmung Mineralwolle Aussenwand",
        quantity=800,
        floor_area_m2=200
    )