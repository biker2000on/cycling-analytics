# Test Fixtures

Place real `.fit` files in this directory for integration testing.

## Expected files

| File | Description | Source |
|------|-------------|--------|
| `outdoor_ride.fit` | Outdoor cycling ride with GPS, power, HR | Garmin Edge device |
| `indoor_ride.fit` | Indoor trainer ride (no GPS, no speed) | Wahoo KICKR / Garmin |
| `run.fit` | Running activity (no power, has GPS) | Garmin Forerunner |
| `multi_lap.fit` | Activity with multiple manual laps | Any device |

## How to obtain test files

1. **Export from Garmin Connect:** Activities > select activity > gear icon > Export Original
2. **Export from Wahoo:** Wahoo app > activity > share > export FIT
3. **Strava:** Download from activity page (original file)

## Privacy note

Strip personal data before committing. GPS coordinates in test files
will be visible in the repository. Consider using files from public
routes or synthetic data.

## Usage in tests

```python
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"

def test_real_outdoor_ride():
    fit_path = FIXTURES / "outdoor_ride.fit"
    if not fit_path.exists():
        pytest.skip("outdoor_ride.fit not available")
    result = parse_fit_file(fit_path)
    assert result.activity.sport_type is not None
```
