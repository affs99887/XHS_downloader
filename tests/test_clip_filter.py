import unittest

from spider.clip_filter import PROMPTS, decide_from_scores


class ClipDecisionTest(unittest.TestCase):
    def scores(self, **values):
        result = dict.fromkeys(PROMPTS, .05)
        result.update(values)
        return result

    def test_stockings_requires_person_leg_evidence(self):
        # A package with stockings pictured on it is not a worn garment.
        result = decide_from_scores(self.scores(black_hosiery=.3, product=.4))
        self.assertEqual(result.action, "discard")
        self.assertIsNone(result.confidence)  # similarities are not probabilities

    def test_black_stockings_are_compared_with_black_pants_and_bare_legs(self):
        result = decide_from_scores(self.scores(black_hosiery=.3, black_pants=.299))
        self.assertEqual(result.action, "review")
        result = decide_from_scores(self.scores(black_hosiery=.3, bare_legs=.31))
        self.assertEqual(result.action, "review")
        result = decide_from_scores(self.scores(black_hosiery=.3, black_pants=.4))
        self.assertEqual(result.action, "discard")

    def test_clear_black_and_white_hosiery_take_different_paths(self):
        result = decide_from_scores(self.scores(black_hosiery=.3, nude_hosiery=.27),
                                    backend="marqo-fashionSigLIP-int8")
        self.assertEqual(result.action, "keep")
        result = decide_from_scores(self.scores(black_hosiery=.2, white_hosiery=.35),
                                    backend="marqo-fashionSigLIP-int8")
        self.assertEqual(result.action, "discard")

    def test_leg_closeups_are_eligible_and_uncertain_scores_go_to_review(self):
        result = decide_from_scores(self.scores(visible_legs=.3, portrait=.2), mode="legs")
        self.assertEqual(result.action, "keep")
        result = decide_from_scores(self.scores(visible_legs=.21, portrait=.2), mode="legs")
        self.assertEqual(result.action, "review")


if __name__ == "__main__":
    unittest.main()
