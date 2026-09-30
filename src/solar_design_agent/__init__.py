"""Physics-based solar array design optimization."""

from .model import ArrayDesign, Site, simulate_design
from .optimize import optimize_fixed_tilt
from .engine import DesignEvaluation, DesignProblem, optimize_problem
from .weather import load_pvgis_tmy, load_weather_csv, simulate_weather_design, validate_weather
from .bracket import BracketConstraints, BracketDesign, BracketProblem, optimize_bracket
from .fem import cantilever_tip_deflection_fem
from .finance import FinanceAssumptions, calculate_project_finance
from .thermal import ThermalResult, solve_steady_1d_fin
from .thermo import ThermoMechanicalConstraints, ThermoMechanicalBracketProblem, optimize_thermomechanical_bracket

__all__ = [
	"ArrayDesign",
	"Site",
	"simulate_design",
	"optimize_fixed_tilt",
	"DesignEvaluation",
	"DesignProblem",
	"optimize_problem",
	"load_weather_csv",
	"load_pvgis_tmy",
	"simulate_weather_design",
	"validate_weather",
	"BracketConstraints",
	"BracketDesign",
	"BracketProblem",
	"optimize_bracket",
	"cantilever_tip_deflection_fem",
	"FinanceAssumptions",
	"calculate_project_finance",
	"ThermalResult",
	"solve_steady_1d_fin",
	"ThermoMechanicalConstraints",
	"ThermoMechanicalBracketProblem",
	"optimize_thermomechanical_bracket",
]
