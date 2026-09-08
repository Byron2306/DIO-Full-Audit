import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


integration = load_module("dio_marketing_integration_activation", "scripts/run_dio_marketing_integration.py")


class InvestorActivationTests(unittest.TestCase):
    def test_dio_capital_has_a_product_layer_before_activation(self):
        config = integration.load_json(ROOT / "config/dio_marketing_integration.json")
        capital = config["product_lines"]["DIO_CAPITAL"]
        layers = integration.product_layers()

        self.assertNotIn("DIO_CAPITAL", config["active_product_lines"])
        self.assertEqual("REGISTERED_DORMANT_UNTIL_INVESTOR_REGISTRY", capital["activation_state"])
        self.assertIn("dio_capital", layers)
        self.assertEqual("capital_diligence", layers["dio_capital"]["category"])
        self.assertIn("CapitalRoom", layers["dio_capital"]["proof_asset"])


if __name__ == "__main__":
    unittest.main()
