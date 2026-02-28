from pydantic import BaseModel
from app.core.validator import AIResponseValidator

class Material(BaseModel):
    name: str
    price: float
    unit: str

def test_validation():
    valid_json = '{"name": "Kabel", "price": 12.50, "unit": "m"}'
    result = AIResponseValidator.validate(valid_json, Material)
    assert result is not None
    assert result.name == "Kabel"
    assert result.price == 12.50
    
    invalid_json = '{"name": "Kabel", "price": "expensive", "unit": "m"}'
    result = AIResponseValidator.validate(invalid_json, Material)
    assert result is None
    
    markdown_json = """Hier ist das Ergebnis:
```json
{"name": "Rohr", "price": 5.0, "unit": "stk"}
```"""
    result = AIResponseValidator.validate(markdown_json, Material)
    assert result is not None
    assert result.name == "Rohr"

    print("Validator Test: PASS")

if __name__ == "__main__":
    test_validation()
