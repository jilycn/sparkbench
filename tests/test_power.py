from power_sample import phase_energy_wh


def test_phase_energy_integrates_one_hz_samples():
    samples = [{"ts": 0, "watts": 100}, {"ts": 1, "watts": 100}, {"ts": 2, "watts": 100}]
    assert phase_energy_wh(samples, 0, 2) == round(200 / 3600, 6)
