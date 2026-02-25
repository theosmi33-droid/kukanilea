import pandas as pd
import os

# Create a sample Excel file for license management
data = {
    "HardwareID": ["000000000000", "111122223333"],
    "CustomerName": ["Demo Kunde", "Elektro Müller"],
    "Plan": ["GOLD", "GOLD"],
    "ValidUntil": ["2030-12-31", "2027-01-01"],
    "IsActive": [True, True]
}

df = pd.DataFrame(data)
os.makedirs("Tophandwerk/kukanilea-git/license_server", exist_ok=True)
df.to_excel("Tophandwerk/kukanilea-git/license_server/licenses.xlsx", index=False)
print("licenses.xlsx generated successfully.")
