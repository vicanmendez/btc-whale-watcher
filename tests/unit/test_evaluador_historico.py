from btc_whale_intelligence.analisis.evaluador_historico import calcular_brier_score


def test_calcular_brier_score():
    # Predicción perfecta para ALCISTA
    brier_perfecto = calcular_brier_score(1.0, 0.0, 0.0, "ALCISTA")
    assert brier_perfecto == 0.0

    # Predicción completamente errónea (predijo BAJISTA 100% y fue ALCISTA)
    brier_peor = calcular_brier_score(0.0, 1.0, 0.0, "ALCISTA")
    assert brier_peor == 2.0  # (0-1)^2 + (1-0)^2 + (0-0)^2 = 2.0

    # Predicción uniforme (1/3 cada una)
    brier_uniforme = calcular_brier_score(1 / 3, 1 / 3, 1 / 3, "NEUTRAL")
    # (1/3 - 0)^2 + (1/3 - 0)^2 + (1/3 - 1)^2 = 1/9 + 1/9 + 4/9 = 6/9 ~ 0.6667
    assert abs(brier_uniforme - 2 / 3) < 1e-4
