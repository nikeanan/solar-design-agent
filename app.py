import streamlit as st

from solar_design_agent.model import Site
from solar_design_agent.optimize import DesignConstraints, optimize_fixed_tilt


st.set_page_config(page_title="Solar Design Agent", page_icon="Sun", layout="wide")
st.title("Solar Design Agent")
st.caption("Physics-based photovoltaic array layout optimization")

with st.sidebar:
    st.header("Site and constraints")
    latitude = st.number_input("Latitude", value=28.6, min_value=-90.0, max_value=90.0)
    longitude = st.number_input("Longitude", value=-81.4, min_value=-180.0, max_value=180.0)
    days = st.number_input("Simulation days", value=365, min_value=1, max_value=365, step=1)
    objective = st.selectbox("Objective", ("energy", "value", "npv"))
    max_land_area = st.number_input("Maximum land area (m²)", value=250.0, min_value=0.0)
    max_budget = st.number_input("Maximum budget (USD)", value=30000.0, min_value=0.0)
    price = st.number_input("Electricity price (USD/kWh)", value=0.10, min_value=0.0, format="%.3f")
    run = st.button("Run optimization", type="primary", use_container_width=True)


def run_optimization() -> dict:
    site = Site(latitude_deg=latitude, longitude_deg=longitude, days=int(days))
    constraints = DesignConstraints(
        objective=objective,
        max_land_area_m2=max_land_area,
        max_budget_usd=max_budget,
        electricity_price_usd_per_kwh=price,
    )
    return optimize_fixed_tilt(site, constraints=constraints)


if run or "result" not in st.session_state:
    with st.spinner("Evaluating candidate designs..."):
        st.session_state.result = run_optimization()

result = st.session_state.result
baseline = result["baseline"]
best = result["best"]
best_result = best["result"]
best_economics = best["economics"]

energy_change = 100 * (best_result["annual_energy_kwh"] / baseline["result"]["annual_energy_kwh"] - 1)
metrics = st.columns(4)
metrics[0].metric("Annual energy", f"{best_result['annual_energy_kwh']:,.0f} kWh")
metrics[1].metric("Energy vs baseline", f"{energy_change:+.1f}%")
metrics[2].metric("Capital cost", f"${best_economics['capital_cost_usd']:,.0f}")
metrics[3].metric("Land area", f"{best_economics['land_area_m2']:,.1f} m²")

left, right = st.columns(2)
with left:
    st.subheader("Recommended design")
    st.dataframe(
        {
            "Parameter": ["Tilt", "Azimuth", "Row spacing", "Module count"],
            "Value": [
                f"{best['design'].tilt_deg:.1f}°",
                f"{best['design'].azimuth_deg:.1f}°",
                f"{best['design'].row_spacing_m:.1f} m",
                str(best["design"].modules),
            ],
        },
        hide_index=True,
        use_container_width=True,
    )
with right:
    st.subheader("Economics")
    st.dataframe(
        {
            "Measure": ["Annual revenue", "NPV", "LCOE", "Feasible designs"],
            "Value": [
                f"${best_economics['annual_revenue_usd']:,.0f}",
                f"${best_economics['npv_usd']:,.0f}",
                f"${best_economics['lcoe_usd_per_kwh']:.3f}/kWh",
                str(result["feasible_count"]),
            ],
        },
        hide_index=True,
        use_container_width=True,
    )

st.subheader("Baseline comparison")
st.write(
    f"Baseline energy: {baseline['result']['annual_energy_kwh']:,.0f} kWh | "
    f"Recommended energy: {best_result['annual_energy_kwh']:,.0f} kWh"
)