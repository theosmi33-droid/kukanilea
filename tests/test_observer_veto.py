from pydantic import BaseModel
from typing import Optional
from app.agents.observer import ObserverAgent

class Material(BaseModel):
    name: str
    price: float

def test_observer_veto():
    observer = ObserverAgent()
    
    call_count = 0
    def mock_generator(prompt: str, temp: float) -> Optional[str]:
        nonlocal call_count
        call_count += 1
        if temp > 0.0:
            return '{"name": "Kabel", "price": "invalid"}' # Fail validation
        else:
            return '{"name": "Kabel", "price": 10.0}' # Succeed validation
            
    result = observer.veto_and_retry("dummy prompt", Material, mock_generator)
    
    assert result is not None
    assert result.price == 10.0
    assert call_count == 2 # Issued veto and retried
    
    print("Observer Veto Test: PASS")

if __name__ == "__main__":
    test_observer_veto()
