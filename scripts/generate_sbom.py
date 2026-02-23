import datetime
import json
import os
import uuid

def generate_sbom():
    """
    Generates a CycloneDX v1.7 compatible SBOM.
    Compliance: ECMA-424 / Supply Chain Security / EU CRA.
    """
    requirements_path = "requirements.txt"
    components = []
    
    if os.path.exists(requirements_path):
        with open(requirements_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    # Basic parsing: name[==version]
                    parts = line.split("==")
                    name = parts[0].strip()
                    version = parts[1].strip() if len(parts) > 1 else "latest"
                    components.append({
                        "name": name,
                        "version": version,
                        "type": "library",
                        "purl": f"pkg:pypi/{name}@{version}"
                    })

    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
            "component": {
                "name": "Kukanilea",
                "version": "1.0.0-rc1",
                "type": "application",
                "description": "Local-first AI Business OS for Craftsmen"
            },
            "authors": [
                {"name": "Tophandwerk Engineering"}
            ]
        },
        "components": components,
    }

    os.makedirs("dist/evidence", exist_ok=True)
    with open("dist/evidence/sbom.cdx.json", "w") as f:
        json.dump(sbom, f, indent=4)
    print(f"SUCCESS: CycloneDX SBOM with {len(components)} components generated at dist/evidence/sbom.cdx.json")

if __name__ == "__main__":
    generate_sbom()
