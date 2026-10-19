"""Small, traceable property calculation, not a general water-property library.

Source: IAPWS SR6-08(2011), pp. 3-5, Eq. (1), Tables 1 and 2.
https://iapws.org/technical-guidance/release/LiquidWater.download
Only cp at 0.1 MPa is implemented; the hydraulic model uses rounded constants.
"""


def water_cp_at_0p1_MPa(temperature_K):
    """Specific isobaric heat capacity in J/(kg K), 253.15 <= T <= 383.15 K."""
    T = temperature_K
    if not 253.15 <= T <= 383.15:
        raise ValueError("Temperature outside IAPWS correlation range")
    R, T_R, T_a, T_b = 461.51805, 10.0, 593.0, 232.0
    tau, alpha, beta = T / T_R, T_R / (T_a - T), T_R / (T - T_b)
    a = [-1.661470539e5, 2.708781640e6, -1.557191544e8]
    n = [4, 5, 7]
    b = [-0.8237426256, 1.908956353, -2.017597384, 0.8546361348]
    m = [2, 3, 4, 5]
    c3 = -8.983025854
    alpha_sum = sum(i * (i + 1) * c * alpha ** (i + 2) for i, c in zip(n, a))
    beta_sum = sum(i * (i + 1) * c * beta ** (i + 2) for i, c in zip(m, b))
    return -R * (c3 + tau * (alpha_sum + beta_sum))
