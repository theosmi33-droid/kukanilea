import datetime
import json
import os


def generate_provenance():
    """
    Generates a SLSA Provenance v1.0 attestation stub.
    Compliance: SLSA Supply Chain Levels.
    """
    provenance = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {"name": "kukanilea-binary", "digest": {"sha256": "abcdef1234567890"}}
        ],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "https://kukanilea.local/GenericPythonBuild@v1",
                "externalParameters": {
                    "source": "github.com/theosmi33-droid/kukanilea"
                },
            },
            "runDetails": {
                "builder": {"id": "https://kukanilea.local/local-builder"},
                "metadata": {
                    "invocationId": "inv-123",
                    "startedOn": datetime.datetime.utcnow().isoformat() + "Z",
                },
            },
        },
    }

    os.makedirs("dist/evidence", exist_ok=True)
    with open("dist/evidence/provenance.json", "w") as f:
        json.dump(provenance, f, indent=4)
    print("SUCCESS: SLSA Provenance generated at dist/evidence/provenance.json")


if __name__ == "__main__":
    generate_provenance()
