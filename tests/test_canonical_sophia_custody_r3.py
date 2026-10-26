import copy
import hashlib
import unittest

from adapters.sophia.canonical_sources import load_service
verify_custody = load_service("sophia_custody").verify_custody


def digest(data):
    return hashlib.sha256(data).hexdigest()


class CustodyR3Tests(unittest.TestCase):
    def setUp(self):
        self.manuscript = b"[P1] Sample manuscript."
        self.rubric = b'{"criteria":[]}'
        self.zpd = b'{"status":"HEURISTIC_NOT_LEARNING_PROOF"}'
        self.prompt = "Review [P1]."
        self.response = "The claim in [P1] needs supporting evidence."
        self.model = "granite3.3:2b"

        self.expected = {
            "manuscript": digest(self.manuscript),
            "rubric": digest(self.rubric),
            "zpd_guidance": digest(self.zpd),
            "prompt": digest(self.prompt.encode()),
            "response": digest(self.response.encode()),
        }

        self.receipt = {
            "schema": "dio.sophia.response-evidence.v1",
            "authority": "DIAGNOSTIC_ONLY_NOT_CONSTITUTIONAL_APPROVAL",
            "prompt_sha256": self.expected["prompt"],
            "response_sha256": self.expected["response"],
            "model": self.model,
            "academic_evidence": {"passed": True},
            "mandos_judgment": {
                "passed": False,
                "response_sha256": self.expected["response"],
            },
            "article_conformity": {
                "summary": {"all_passed": False},
                "response_sha256": self.expected["response"],
            },
        }

    def verify(self, **overrides):
        kwargs = dict(
            manuscript=self.manuscript,
            rubric=self.rubric,
            zpd_guidance=self.zpd,
            prompt=self.prompt,
            response=self.response,
            requested_model=self.model,
            actual_model=self.model,
            receipt=copy.deepcopy(self.receipt),
            expected_digests=copy.deepcopy(self.expected),
        )
        kwargs.update(overrides)
        return verify_custody(**kwargs)

    def test_intact_artifacts_pass_custody_only(self):
        result = self.verify()
        self.assertTrue(result["passed"])
        self.assertFalse(result["constitutional_release_authorized"])

    def test_substituted_manuscript_refuses(self):
        self.assertFalse(
            self.verify(manuscript=b"Different manuscript")["passed"]
        )

    def test_changed_response_refuses(self):
        self.assertFalse(
            self.verify(response="Altered academic judgment")["passed"]
        )

    def test_model_substitution_refuses(self):
        self.assertFalse(
            self.verify(actual_model="qwen3:4b")["passed"]
        )

    def test_missing_expected_digest_refuses(self):
        expected = copy.deepcopy(self.expected)
        del expected["rubric"]
        self.assertFalse(
            self.verify(expected_digests=expected)["passed"]
        )

    def test_fabricated_genesis_approval_refuses(self):
        receipt = copy.deepcopy(self.receipt)
        receipt["article_conformity"]["summary"]["all_passed"] = True
        self.assertFalse(
            self.verify(receipt=receipt)["passed"]
        )


if __name__ == "__main__":
    unittest.main()
